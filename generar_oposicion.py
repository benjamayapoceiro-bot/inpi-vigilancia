"""
Genera un borrador de oposición (Art. 24, Ley 22.362) cuando una alerta
supera el umbral de "muy parecida". Es un PUNTO DE PARTIDA para que
Timmy lo revise y complete — nunca se presenta automáticamente al TAD.
"""

UMBRAL_OPOSICION = 0.85  # score a partir del cual se genera el borrador


def generar_borrador(alerta: dict, marca_vigilada: dict) -> str:
    tipo = "denominativa" if alerta["tipo_match"] == "texto" else "mixta (por similitud de logo)"
    fundamento_similitud = (
        f"presenta una similitud ortográfica/fonética del {alerta['similitud'].get('ortografica', 0)*100:.0f}%/"
        f"{alerta['similitud'].get('fonetica', 0)*100:.0f}% respecto de la marca preexistente"
        if alerta["tipo_match"] == "texto"
        else f"presenta una similitud visual (hash perceptual) del {alerta['similitud']['score']*100:.0f}% "
             f"respecto del logo de la marca preexistente"
    )

    return f"""BORRADOR — ESCRITO DE OPOSICIÓN (Art. 24, Ley 22.362)
[REVISAR Y COMPLETAR ANTES DE PRESENTAR — generado automáticamente, no presentar sin control profesional]

Solicitud opuesta: Acta N° {alerta['acta_nueva']}
Denominación: {alerta['denominacion_nueva'] or '(marca mixta sin denominación)'}
Clase: {alerta['clase']}
Titular solicitante: {', '.join(t['nombre'] for t in alerta['titular_nuevo']) if alerta['titular_nuevo'] else '(a completar)'}

Marca preexistente (base de la oposición):
{marca_vigilada['nombre'] or '(logo sin denominación)'} — Clase {marca_vigilada['clase']}
Titular/cliente: {marca_vigilada.get('cliente', '(completar)')}
Tipo: {tipo}

FUNDAMENTO PRELIMINAR:
La solicitud de marca individualizada en el Acta N° {alerta['acta_nueva']} {fundamento_similitud},
en la misma clase ({alerta['clase']}) que la marca preexistente de mi mandante, lo que genera
riesgo de confusión, asociación indebida y/o dilución en los términos del art. 3 inc. a) y b)
de la Ley 22.362.

[Completar: reseña de antecedentes registrales del oponente, jurisprudencia aplicable,
coexistencia o no de rubros, y petitorio formal]

PLAZO: la oposición debe presentarse dentro de los 30 días hábiles desde la publicación
en el Boletín de Marcas. Verificar fecha de publicación exacta antes de presentar.
"""


if __name__ == "__main__":
    # Prueba rápida con datos de ejemplo
    alerta_ejemplo = {
        "tipo_match": "texto", "acta_nueva": "4700000", "denominacion_nueva": "CASA CUMBRRE",
        "clase": 42, "titular_nuevo": [{"nombre": "COMPETIDOR SA", "pais": "AR"}],
        "similitud": {"ortografica": 0.91, "fonetica": 0.95, "score": 0.95},
    }
    marca_ejemplo = {"nombre": "CASA CUMBRE", "clase": 42, "cliente": "Casa Cumbre"}
    print(generar_borrador(alerta_ejemplo, marca_ejemplo))
