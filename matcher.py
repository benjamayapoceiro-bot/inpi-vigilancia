"""
Motor de matching: compara una lista de "marcas a vigilar" contra las
actas nuevas de un boletín, filtrando por clase y puntuando similitud
(texto para marcas denominativas, pHash para marcas mixtas/logos).
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher


def normalizar_fonetico(s: str) -> str:
    """Normalización simple para captar similitud fonética en español:
    saca acentos, agrupa sonidos equivalentes (b/v, s/c/z, y/ll, etc.)
    y colapsa letras repetidas."""
    s = s.upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    reemplazos = [
        ("QU", "K"), ("CU", "K"), ("C", "K"), ("Z", "S"),
        ("V", "B"), ("LL", "Y"), ("H", ""), ("Ñ", "N"),
        ("PH", "F"), ("W", "V"),
    ]
    for a, b in reemplazos:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)  # colapsar repetidas: "TT" -> "T"
    s = re.sub(r"[^A-Z]", "", s)
    return s


def similitud(a: str, b: str) -> dict:
    a_norm, b_norm = normalizar_fonetico(a), normalizar_fonetico(b)
    ortografica = SequenceMatcher(None, a.upper(), b.upper()).ratio()
    fonetica = SequenceMatcher(None, a_norm, b_norm).ratio()

    # Orden de palabras: "CASA CUMBRE" vs "CUMBRE CASA" son la misma marca
    # en la práctica, pero SequenceMatcher sobre la cadena completa las
    # penaliza fuerte por el orden. Se compara con las palabras ordenadas
    # alfabéticamente (y ya normalizadas fonéticamente) para neutralizar eso.
    palabras_a = sorted(normalizar_fonetico(w) for w in re.findall(r"\w+", a))
    palabras_b = sorted(normalizar_fonetico(w) for w in re.findall(r"\w+", b))
    orden = 0.0
    if len(palabras_a) > 1 or len(palabras_b) > 1:
        orden = SequenceMatcher(None, "".join(palabras_a), "".join(palabras_b)).ratio()

    # Contención: si una marca es el núcleo dominante de la otra (más larga),
    # el ratio de SequenceMatcher sobre las cadenas completas subestima el
    # riesgo real — caso típico: "AYUDIN" vs "AYUDIN ANTI-SPLASH", donde el
    # agregado busca justamente esquivar la comparación literal.
    contencion = 0.0
    if len(a_norm) >= 4 and len(b_norm) >= 4 and (a_norm in b_norm or b_norm in a_norm):
        corto, largo = (a_norm, b_norm) if len(a_norm) <= len(b_norm) else (b_norm, a_norm)
        contencion = round(0.75 + 0.25 * (len(corto) / len(largo)), 3)

    return {
        "ortografica": round(ortografica, 3),
        "fonetica": round(fonetica, 3),
        "orden": round(orden, 3),
        "contencion": contencion,
        "score": round(max(ortografica, fonetica, orden, contencion), 3),
    }


def distancia_hash(hash_a: str, hash_b: str) -> float:
    """Distancia de Hamming normalizada entre dos hashes hex de 64 bits.
    Devuelve score de similitud 0-1 (1 = idéntico)."""
    try:
        a, b = int(hash_a, 16), int(hash_b, 16)
    except (ValueError, TypeError):
        return 0.0
    xor = a ^ b
    bits_distintos = bin(xor).count("1")
    return round(1 - (bits_distintos / 64), 3)


def distancia_logo_combinada(vig: dict, acta: dict) -> float:
    scores = []
    if vig.get("logo_phash") and acta.get("logo_phash"):
        scores.append(distancia_hash(vig["logo_phash"], acta["logo_phash"]))
    if vig.get("logo_dhash") and acta.get("logo_dhash"):
        scores.append(distancia_hash(vig["logo_dhash"], acta["logo_dhash"]))
    if not scores:
        return 0.0
    if len(scores) == 2:
        ph, dh = scores[0], scores[1]
        if min(ph, dh) < 0.70:
            return round(min(ph, dh) * 0.92, 3)
        return round(ph * 0.55 + dh * 0.45, 3)
    return round(scores[0], 3)


UMBRAL_ATENCION = 0.85
UMBRAL_TEXTO = 0.60
UMBRAL_LOGO = 0.75

CLASES_AFINES = {
    9: [35, 38, 41, 42], 35: [9, 38, 41, 42], 42: [9, 35, 38, 41],
    25: [18, 26, 35], 18: [25, 26], 3: [5, 21, 44], 5: [3, 44],
    29: [30, 31, 32, 33, 43], 30: [29, 31, 32, 33, 43],
    36: [35, 37, 45], 37: [36, 45], 11: [7, 37], 7: [11, 37],
}


def relacion_clases(c1: int, c2: int) -> str:
    if c1 == c2:
        return "misma"
    if c2 in CLASES_AFINES.get(c1, []) or c1 in CLASES_AFINES.get(c2, []):
        return "afin"
    return "distinta"


def calcular_riesgo(score: float, relacion: str, tipo_match: str) -> dict:
    factor = {"misma": 1.0, "afin": 0.82, "distinta": 0.62}[relacion]
    score_ajustado = round(score * (0.72 + 0.28 * factor), 3)
    if relacion == "misma":
        if score >= 0.85:
            nivel = "alto"
        elif score >= 0.65:
            nivel = "medio"
        elif score >= 0.60:
            nivel = "bajo"
        else:
            nivel = "bajo"
    elif relacion == "afin":
        if score >= 0.88:
            nivel = "alto"
        elif score >= 0.72:
            nivel = "medio"
        else:
            nivel = "bajo"
    else:
        if score >= 0.92:
            nivel = "medio"
        elif score >= 0.72:
            nivel = "bajo"
        else:
            nivel = "bajo"
    return {"nivel": nivel, "score_ajustado": score_ajustado, "factor_clase": factor, "relacion": relacion}


def generar_borrador_oposicion(alerta: dict) -> str:
    """Borrador de oposición basado en template — SIEMPRE requiere revisión humana
    antes de presentarse. No se presenta nada automáticamente."""
    titulares = ", ".join(t["nombre"] for t in alerta["titular_nuevo"]) or "titular no identificado"
    motivo = (
        f"similitud fonética/ortográfica del {alerta['similitud']['score']*100:.0f}%"
        if alerta["tipo_match"] == "texto"
        else f"similitud visual del logo del {alerta['similitud']['score']*100:.0f}%"
    )
    return (
        f"BORRADOR — Oposición al registro de marca\n\n"
        f"Acta impugnada: {alerta['acta_nueva']}\n"
        f"Denominación: {alerta['denominacion_nueva'] or '(marca mixta/figurativa)'}\n"
        f"Clase: {alerta['clase']}\n"
        f"Titular solicitante: {titulares}\n\n"
        f"Marca opositora (vigilada): {alerta['marca_vigilada']}"
        f"{' — cliente: ' + alerta['cliente'] if alerta['cliente'] else ''}\n\n"
        f"Fundamento preliminar: se detecta {motivo} entre la marca solicitada "
        f"y la marca opositora, en la misma clase de Niza, lo que podría generar "
        f"confusión en el público consumidor (art. 3 inc. a y b, Ley 22.362).\n\n"
        f"[ESTE ES UN BORRADOR AUTOMÁTICO — revisar antecedentes, verificar vigencia "
        f"del derecho opositor, y completar fundamentos antes de presentar por TAD. "
        f"Plazo: 30 días hábiles desde la publicación.]"
    )


def buscar_coincidencias(marcas_vigiladas, actas_nuevas, umbral=0.60, umbral_logo=0.75):
    alertas = []
    for vig in marcas_vigiladas:
        for acta in actas_nuevas:
            if not acta.get("acta"):
                continue
            relacion = relacion_clases(vig["clase"], acta["clase"])
            umbral_efectivo = umbral if relacion == "misma" else (0.68 if relacion == "afin" else 0.72)
            umbral_logo_ef = umbral_logo if relacion == "misma" else (0.78 if relacion == "afin" else 0.82)

            if vig.get("tipo", "D") == "D" and acta["denominacion"]:
                if not vig.get("nombre"):
                    continue
                sim = similitud(vig["nombre"], acta["denominacion"])
                if sim["score"] >= umbral_efectivo:
                    riesgo = calcular_riesgo(sim["score"], relacion, "texto")
                    alertas.append({
                        "tipo_match": "texto",
                        "marca_vigilada_id": vig.get("id"),
                        "marca_vigilada": vig["nombre"], "cliente": vig.get("cliente", ""),
                        "clase": vig["clase"], "clase_acta": acta["clase"],
                        "relacion_clases": relacion,
                        "acta_nueva": acta["acta"],
                        "denominacion_nueva": acta["denominacion"],
                        "titular_nuevo": acta["titulares"], "similitud": sim,
                        "nivel_riesgo": riesgo["nivel"], "score_ajustado": riesgo["score_ajustado"],
                    })
            elif vig.get("tipo") in ("M", "F") and (vig.get("logo_phash") or vig.get("logo_dhash")):
                score_logo = distancia_logo_combinada(vig, acta)
                if score_logo >= umbral_logo_ef:
                    riesgo = calcular_riesgo(score_logo, relacion, "logo")
                    alertas.append({
                        "tipo_match": "logo",
                        "marca_vigilada_id": vig.get("id"),
                        "marca_vigilada": vig["nombre"] or "(logo sin texto)",
                        "cliente": vig.get("cliente", ""),
                        "clase": vig["clase"], "clase_acta": acta["clase"],
                        "relacion_clases": relacion,
                        "acta_nueva": acta["acta"],
                        "denominacion_nueva": acta["denominacion"],
                        "titular_nuevo": acta["titulares"],
                        "similitud": {"ortografica": 0, "fonetica": 0, "score": score_logo},
                        "nivel_riesgo": riesgo["nivel"], "score_ajustado": riesgo["score_ajustado"],
                    })

    alertas.sort(key=lambda x: (-{"alto": 3, "medio": 2, "bajo": 1}[x.get("nivel_riesgo", "bajo")], -x["similitud"]["score"], x["relacion_clases"] != "misma"))

    for al in alertas:
        misma = al.get("relacion_clases") == "misma"
        score = al["similitud"]["score"]
        necesita = (misma and score >= 0.85) or (al.get("relacion_clases") == "afin" and score >= 0.88) or (not misma and score >= 0.92)
        if necesita:
            al["requiere_atencion"] = True
            al["requiere_oposicion"] = True
            al["borrador_oposicion"] = generar_borrador_oposicion(al)
        elif al.get("nivel_riesgo") in ("alto", "medio"):
            al["requiere_atencion"] = True
            al["requiere_oposicion"] = score >= UMBRAL_ATENCION and misma
            al["borrador_oposicion"] = generar_borrador_oposicion(al) if al["requiere_oposicion"] else None
        else:
            al["requiere_atencion"] = False
            al["requiere_oposicion"] = False
            al["borrador_oposicion"] = None

    return alertas


if __name__ == "__main__":
    import sys

    actas = []
    for f in sys.argv[2:]:
        actas.extend(json.load(open(f)))

    # Ejemplo de cartera a vigilar — reemplazar por tus marcas + las de tus clientes
    marcas_vigiladas = json.loads(open(sys.argv[1]).read())

    alertas = buscar_coincidencias(marcas_vigiladas, actas)
    print(f"{len(actas)} actas analizadas, {len(alertas)} alertas (umbral 0.72)\n")
    for al in alertas[:30]:
        print(f"[{al['similitud']['score']}] '{al['marca_vigilada']}' (clase {al['clase']}, cliente: {al['cliente']}) "
              f"~ '{al['denominacion_nueva']}' (Acta {al['acta_nueva']}, titular: {al['titular_nuevo']})")
