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
    """Combina pHash (estructura de frecuencias, robusto a color/recortes) y
    dHash (gradientes de brillo, robusto a variaciones de contraste). Usar los
    dos algoritmos en simultáneo baja bastante los falsos positivos que da
    cualquiera de los dos por separado. Si a algún logo le falta uno de los
    dos hashes (ej. logos cargados antes de sumar dHash), cae a comparar
    solo con el que esté disponible."""
    scores = []
    if vig.get("logo_phash") and acta.get("logo_phash"):
        scores.append(distancia_hash(vig["logo_phash"], acta["logo_phash"]))
    if vig.get("logo_dhash") and acta.get("logo_dhash"):
        scores.append(distancia_hash(vig["logo_dhash"], acta["logo_dhash"]))
    if not scores:
        return 0.0
    return round(sum(scores) / len(scores), 3)


UMBRAL_ATENCION = 0.85  # a partir de acá, generamos borrador de oposición


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


def buscar_coincidencias(marcas_vigiladas, actas_nuevas, umbral=0.72, umbral_logo=0.80):
    """
    marcas_vigiladas: [{"nombre": "TORTE", "clase": 30, "cliente": "...",
                         "tipo": "D"|"M", "logo_phash": "..." (si tipo M)}, ...]
    actas_nuevas: output de parse_boletin.py, con logo_phash agregado por
                  extract_logos.py para las actas tipo M.
    """
    alertas = []
    for vig in marcas_vigiladas:
        for acta in actas_nuevas:
            if acta["clase"] != vig["clase"]:
                continue

            # --- Marca denominativa: comparación de texto ---
            if vig.get("tipo", "D") == "D" and acta["denominacion"]:
                sim = similitud(vig["nombre"], acta["denominacion"])
                if sim["score"] >= umbral:
                    alertas.append({
                        "tipo_match": "texto",
                        "marca_vigilada": vig["nombre"], "cliente": vig.get("cliente", ""),
                        "clase": vig["clase"], "acta_nueva": acta["acta"],
                        "denominacion_nueva": acta["denominacion"],
                        "titular_nuevo": acta["titulares"], "similitud": sim,
                    })

            # --- Marca mixta: comparación de logo por hash combinado (pHash + dHash) ---
            elif vig.get("tipo") == "M" and (vig.get("logo_phash") or vig.get("logo_dhash")):
                score_logo = distancia_logo_combinada(vig, acta)
                if score_logo >= umbral_logo:
                    alertas.append({
                        "tipo_match": "logo",
                        "marca_vigilada": vig["nombre"] or "(logo sin texto)",
                        "cliente": vig.get("cliente", ""),
                        "clase": vig["clase"], "acta_nueva": acta["acta"],
                        "denominacion_nueva": acta["denominacion"],
                        "titular_nuevo": acta["titulares"],
                        "similitud": {"ortografica": 0, "fonetica": 0, "score": score_logo},
                    })

    alertas.sort(key=lambda x: -x["similitud"]["score"])

    for al in alertas:
        if al["similitud"]["score"] >= UMBRAL_ATENCION:
            al["requiere_atencion"] = True
            al["borrador_oposicion"] = generar_borrador_oposicion(al)
        else:
            al["requiere_atencion"] = False
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
