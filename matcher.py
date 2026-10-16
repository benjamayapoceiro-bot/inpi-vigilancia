"""
Motor de matching: compara una lista de "marcas a vigilar" contra las
actas nuevas de un boletín, filtrando por clase y puntuando similitud
(texto para marcas denominativas, pHash para marcas mixtas/logos).
"""
import json
import re
import unicodedata
from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz as _rf_fuzz

    def _ratio(a: str, b: str) -> float:
        return _rf_fuzz.ratio(a, b) / 100.0
except ImportError:  # pragma: no cover - fallback sin rapidfuzz
    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


# Palabras vacías del español que no aportan a la identidad de la marca.
STOPWORDS = frozenset({
    "DE", "DEL", "LA", "EL", "LAS", "LOS", "Y", "E", "EN", "UN", "UNA",
    "UNOS", "UNAS", "AL", "CON", "POR", "PARA", "THE", "OF", "AND",
})


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalizar_fonetico(s: str) -> str:
    """Normalización para captar similitud fonética en español rioplatense:
    saca acentos, agrupa sonidos equivalentes (b/v, s/c/z, ll/y, etc.)
    y colapsa letras repetidas. Solo equivalencias seguras: NO colapsa
    vocales (e/i, o/u) ni r/l, que antes generaban falsos positivos."""
    s = _sin_acentos(s.upper()).replace("&", " Y ")
    reemplazos = [
        ("SHISHA", "YIYA"), ("QU", "K"), ("CU", "K"), ("C", "K"), ("Z", "S"),
        ("V", "B"), ("LL", "Y"), ("H", ""), ("Ñ", "N"),
        ("PH", "F"), ("W", "B"), ("SH", "Y"), ("CH", "Y"),
    ]
    for a, b in reemplazos:
        s = s.replace(a, b)
    s = re.sub(r"(.)\1+", r"\1", s)  # colapsar repetidas: "TT" -> "T"
    s = re.sub(r"[^A-Z0-9]", "", s)  # se conservan dígitos: 3M, 7UP, etc.
    return s


def singularizar(w: str) -> str:
    """Plural naive: CUMBRES -> CUMBRE. Solo quita S final en palabras
    de más de 4 letras que no terminen en ES (para no romper LUNES)."""
    if len(w) > 4 and w.endswith("S") and not w.endswith("ES"):
        return w[:-1]
    return w


def palabras_clave(s: str) -> list:
    """Palabras normalizadas, sin stopwords y singularizadas."""
    out = []
    for w in re.findall(r"[A-Z0-9]+", _sin_acentos(s.upper())):
        nw = singularizar(normalizar_fonetico(w))
        if nw and nw not in STOPWORDS:
            out.append(nw)
    return out


def token_set(a: str, b: str) -> float:
    """Dice sobre conjuntos de palabras clave: captura 'CASA CUMBRE' vs
    'CASA CUMBRE PATAGONIA' aunque el ratio de cadena completa caiga."""
    sa, sb = set(palabras_clave(a)), set(palabras_clave(b))
    if not sa or not sb:
        return 0.0
    inter = sa & sb
    if not inter:
        return 0.0
    return round(2 * len(inter) / (len(sa) + len(sb)), 3)


def similitud(a: str, b: str, relacion: str = None) -> dict:
    a_norm, b_norm = normalizar_fonetico(a), normalizar_fonetico(b)
    a_up, b_up = _sin_acentos(a.upper()), _sin_acentos(b.upper())
    ortografica = _ratio(a_up, b_up)
    fonetica = _ratio(a_norm, b_norm)

    # Orden de palabras: "CASA CUMBRE" vs "CUMBRE CASA" son la misma marca
    # en la práctica, pero el ratio sobre la cadena completa las penaliza
    # fuerte por el orden. Se compara con las palabras ordenadas
    # alfabéticamente (clave, sin vacías) para neutralizar eso.
    palabras_a = sorted(palabras_clave(a))
    palabras_b = sorted(palabras_clave(b))
    orden = 0.0
    if len(palabras_a) > 1 or len(palabras_b) > 1:
        orden = _ratio("".join(palabras_a), "".join(palabras_b))

    tset = token_set(a, b)

    # Contención: si una marca es el núcleo dominante de la otra (más larga),
    # el ratio sobre las cadenas completas subestima el riesgo real — caso
    # típico: "AYUDIN" vs "AYUDIN ANTI-SPLASH". En clase distinta se atenúa.
    contencion = 0.0
    if len(a_norm) >= 4 and len(b_norm) >= 4 and (a_norm in b_norm or b_norm in a_norm):
        corto, largo = (a_norm, b_norm) if len(a_norm) <= len(b_norm) else (b_norm, a_norm)
        contencion = round(0.75 + 0.25 * (len(corto) / len(largo)), 3)
        if relacion == "distinta":
            contencion = round(contencion * 0.85, 3)

    score = max(ortografica, fonetica, orden, tset, contencion)
    # Bonus prefijo: marcas que arrancan igual suelen ser el mismo núcleo.
    if len(a_norm) >= 4 and a_norm[:4] == b_norm[:4]:
        score = min(1.0, score + 0.04)

    return {
        "ortografica": round(ortografica, 3),
        "fonetica": round(fonetica, 3),
        "orden": round(orden, 3),
        "token_set": round(tset, 3),
        "contencion": contencion,
        "score": round(score, 3),
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
    ph = dh = wh = None
    if vig.get("logo_phash") and acta.get("logo_phash"):
        ph = distancia_hash(vig["logo_phash"], acta["logo_phash"])
    if vig.get("logo_dhash") and acta.get("logo_dhash"):
        dh = distancia_hash(vig["logo_dhash"], acta["logo_dhash"])
    if vig.get("logo_whash") and acta.get("logo_whash"):
        wh = distancia_hash(vig["logo_whash"], acta["logo_whash"])
    scores = [s for s in (ph, dh, wh) if s is not None]
    if not scores:
        return 0.0
    if len(scores) >= 2 and min(scores) < 0.70:
        return round(min(scores) * 0.92, 3)
    if ph is not None and dh is not None and wh is not None:
        return round(ph * 0.50 + dh * 0.30 + wh * 0.20, 3)
    if ph is not None and dh is not None:
        return round(ph * 0.55 + dh * 0.45, 3)
    return round(sum(scores) / len(scores), 3)


UMBRAL_ATENCION = 0.85
UMBRAL_TEXTO = 0.60
UMBRAL_LOGO = 0.75

_CLASES_AFINES_BASE = {
    9: [35, 38, 41, 42], 35: [9, 38, 41, 42], 42: [9, 35, 38, 41],
    25: [18, 26, 35], 18: [25, 26], 3: [5, 21, 44], 5: [3, 44],
    29: [30, 31, 32, 33, 43], 30: [29, 31, 32, 33, 43],
    32: [29, 30, 33, 43], 33: [29, 30, 32, 43], 43: [29, 30, 32, 33],
    31: [29, 30],
    36: [35, 37, 45], 37: [36, 45], 45: [35, 36, 37, 42],
    11: [7, 37], 7: [11, 37],
    44: [3, 5, 10, 21], 10: [44], 21: [3, 44],
    16: [35, 41], 41: [9, 35, 42, 16, 28], 28: [41], 38: [9, 42],
    14: [35], 24: [25], 26: [25, 18], 20: [11],
}

# Cierre simétrico: si A es afín a B, B es afín a A (antes duplicado a mano).
CLASES_AFINES = {k: set(v) for k, v in _CLASES_AFINES_BASE.items()}
for _k, _vs in list(CLASES_AFINES.items()):
    for _x in _vs:
        CLASES_AFINES.setdefault(_x, set()).add(_k)
CLASES_AFINES = {k: sorted(v) for k, v in CLASES_AFINES.items()}


def relacion_clases(c1: int, c2: int) -> str:
    try:
        c1, c2 = int(c1), int(c2)
    except (TypeError, ValueError):
        return "distinta"
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

            # Texto: corre para D y también para M/F cuando ambos lados
            # tienen denominación (una mixta idéntica a un acta denominativa
            # debe alertar aunque el logo no matchee).
            umbral_txt = umbral_efectivo
            try:
                min_len = min(
                    len(re.sub(r"[^A-Z0-9]", "", _sin_acentos(str(vig.get("nombre", "")).upper()))),
                    len(re.sub(r"[^A-Z0-9]", "", _sin_acentos(str(acta.get("denominacion", "")).upper()))),
                )
            except Exception:
                min_len = 99
            if min_len <= 3:
                umbral_txt = max(umbral_efectivo, 0.90)  # siglas: exigir casi exacto
            if vig.get("nombre") and acta.get("denominacion"):
                sim = similitud(vig["nombre"], acta["denominacion"], relacion)
                if sim["score"] >= umbral_txt:
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
            if vig.get("tipo") in ("M", "F") and (vig.get("logo_phash") or vig.get("logo_dhash")):
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
            al["requiere_oposicion"] = score >= UMBRAL_ATENCION and (misma or al.get("relacion_clases") == "afin")
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
