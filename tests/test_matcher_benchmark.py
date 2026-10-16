import json
from matcher import similitud, distancia_logo_combinada, relacion_clases, calcular_riesgo, buscar_coincidencias

casos_texto = [
    ("CASA CUMBRE", "CASA CUMBRRE", 0.85, "misma"),
    ("CASA CUMBRE", "CASA CUMBRE", 1.0, "misma"),
    ("CRESPO THURN", "CRESPO THURM", 0.80, "misma"),
    ("REALLY UP", "REAL AGENCY", 0.45, "afin"),  # marcas distintas: precisión > recall
    ("AYUDIN", "AYUDIN ANTI-SPLASH", 0.75, "misma"),
    ("CASA CUMBRE", "CASA CUMBRE", 1.0, "distinta"),
    ("CASA DE CUMBRE", "CASA CUMBRE", 0.85, "misma"),  # stopwords no rompen
    ("CUMBRES PATAGONICAS", "CUMBRE PATAGONICA", 0.85, "misma"),  # plural naive
    ("TORTE", "TORTEN", 0.80, "misma"),
    ("3M", "3M", 1.0, "misma"),  # dígitos conservados
]

def test_siglas_no_matchean():
    # IBM vs IBN en misma clase: umbral 0.90 para siglas, no debe alertar
    vig = [{"id": "9", "nombre": "IBM", "clase": 9, "cliente": "x", "tipo": "D"}]
    actas = [{"acta": "5000009", "denominacion": "IBN", "clase": 9, "titulares": []}]
    als = buscar_coincidencias(vig, actas)
    print("siglas IBM vs IBN alertas:", len(als))
    assert len(als) == 0, "siglas distintas no deben alertar"

def test_mixta_matchea_texto():
    # Vigilada M con nombre idéntico a acta D: debe alertar por texto
    vig = [{"id": "1", "nombre": "CASA CUMBRE", "clase": 42, "cliente": "Casa Cumbre",
            "tipo": "M", "logo_phash": "ffff0000ffff0000", "logo_dhash": "ffff0000ffff0000"}]
    actas = [{"acta": "5000010", "denominacion": "CASA CUMBRE", "clase": 42, "titulares": []}]
    als = buscar_coincidencias(vig, actas)
    tipos = [a["tipo_match"] for a in als]
    print("mixta vs denominativa idéntica:", tipos)
    assert "texto" in tipos, "M con nombre debe matchear texto del acta"

def test_benchmark():
    print("=== Benchmark texto ===")
    for a, b, exp_min, rel in casos_texto:
        sim = similitud(a, b)
        riesgo = calcular_riesgo(sim["score"], rel, "texto")
        estado = "✓" if sim["score"] >= exp_min else "✗"
        print(f"{estado} '{a}' vs '{b}' score={sim['score']} riesgo={riesgo['nivel']} ({rel}) detalle={sim}")

    print("\n=== Relaciones clases ===")
    for c1, c2 in [(36,36),(9,35),(42,5),(36,25)]:
        print(f"clase {c1} vs {c2} = {relacion_clases(c1,c2)}")

    print("\n=== Logo combinado ===")
    vig = {"logo_phash":"ffff0000ffff0000","logo_dhash":"ffff0000ffff0000"}
    acta_same = {"logo_phash":"ffff0000ffff0000","logo_dhash":"ffff0000ffff0000"}
    acta_diff = {"logo_phash":"0000000000000000","logo_dhash":"0000000000000000"}
    print("mismo logo:", distancia_logo_combinada(vig, acta_same))
    print("distinto logo:", distancia_logo_combinada(vig, acta_diff))

    print("\n=== Buscar_coincidencias class-aware ===")
    vigiladas = [
        {"id":"1","nombre":"CASA CUMBRE","clase":42,"cliente":"Casa Cumbre","tipo":"D"},
        {"id":"2","nombre":"CRESPO THURN","clase":36,"cliente":"Crespo","tipo":"D"},
    ]
    actas = [
        {"acta":"5000001","denominacion":"CASA CUMBRRE","clase":42,"titulares":[]},
        {"acta":"5000002","denominacion":"CASA CUMBRE","clase":35,"titulares":[]},
        {"acta":"5000003","denominacion":"CRESPO THURN ESTUDIO","clase":36,"titulares":[]},
        {"acta":"5000004","denominacion":"CASA CUMBRE","clase":25,"titulares":[]},
    ]
    alertas = buscar_coincidencias(vigiladas, actas)
    for al in alertas:
        print(f"[{al['nivel_riesgo']}] {al['marca_vigilada']} ({al['clase']}) ~ {al['denominacion_nueva']} clase {al['clase_acta']} rel={al['relacion_clases']} score={al['similitud']['score']} ajust={al['score_ajustado']}")

if __name__ == "__main__":
    test_benchmark()
    test_siglas_no_matchean()
    test_mixta_matchea_texto()
    print("OK nuevos tests")
