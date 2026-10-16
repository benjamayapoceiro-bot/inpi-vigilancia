"""
Reenvía el resumen de vigilancia a UN estudio (disparado por workflow_dispatch
desde el botón "Reenviar" del admin). Manda las alertas fuertes no revisadas
de los últimos 30 días + vencimientos pendientes de ese estudio.
Uso: ESTUDIO_ID=xxx python reenviar_estudio.py
"""
import os
from datetime import date, timedelta

import requests

from notificar_email import enviar_a_estudio

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def sget(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    estudio_id = os.environ.get("ESTUDIO_ID", "").strip()
    if not estudio_id:
        raise RuntimeError("Falta ESTUDIO_ID")
    est = sget("estudios", f"select=id,nombre,email_contacto&id=eq.{estudio_id}")
    if not est:
        raise RuntimeError(f"Estudio {estudio_id} no existe")
    info = est[0]
    desde = (date.today() - timedelta(days=30)).isoformat()
    marcas = sget("marcas_vigiladas", f"select=id,nombre&estudio_id=eq.{estudio_id}")
    ids = [m["id"] for m in marcas]
    alertas = []
    if ids:
        or_id = ",".join(ids)
        alertas = sget(
            "alertas",
            f"select=marca_vigilada_id,tipo_match,acta_nueva,denominacion_nueva,clase,clase_acta,"
            f"relacion_clases,titular_nuevo,boletin_numero,similitud_ortografica,similitud_fonetica,"
            f"similitud_logo,similitud_score,score_ajustado,nivel_riesgo,requiere_oposicion,"
            f"borrador_oposicion,fecha_limite_oposicion,enlace_inpi"
            f"&marca_vigilada_id=in.({or_id})&revisada=is.false"
            f"&created_at=gte.{desde}&similitud_score=gte.0.85&order=similitud_score.desc",
        )
        por_marca = {m["id"]: m.get("nombre") for m in marcas}
        for a in alertas:
            a.setdefault("marca_vigilada", por_marca.get(a.get("marca_vigilada_id"), "Marca"))
            a.setdefault("similitud", {
                "ortografica": a.get("similitud_ortografica") or 0,
                "fonetica": a.get("similitud_fonetica") or 0,
                "score": a.get("similitud_score") or 0,
            })
    vencs = sget(
        "avisos_vencimiento",
        f"select=marca_vigilada_id,fecha_vencimiento,dias_restantes&avisado=is.false"
        f"&marca_vigilada_id=in.({','.join(ids)})" if ids else "select=marca_vigilada_id&limit=0",
    )
    for v in vencs:
        v["nombre_marca"] = next((m.get("nombre") for m in marcas if m["id"] == v.get("marca_vigilada_id")), "Marca")
    contexto = f"Reenvío manual del {date.today().isoformat()}."
    ok = enviar_a_estudio(info.get("email_contacto"), info.get("nombre") or "estudio",
                          alertas, vencs, contexto=contexto)
    print(f"reenvío a {info.get('nombre')}: {'OK' if ok else 'OMITIDO (sin mail real o sin credenciales)'} "
          f"({len(alertas)} alertas, {len(vencs)} vencimientos)")


if __name__ == "__main__":
    main()
