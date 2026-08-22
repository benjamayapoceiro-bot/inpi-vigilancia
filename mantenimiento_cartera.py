"""
Se corre como parte del cron semanal:
1. Toma marcas_vigiladas con logo_pendiente (subido desde el dashboard),
   calcula su pHash con el mismo algoritmo que usa el resto del sistema,
   lo guarda en logo_phash y borra el pendiente.
2. Revisa fecha_vencimiento de todas las marcas y genera un aviso si
   faltan 90 días o menos (y todavía no se avisó).
"""
import base64
import io
from datetime import date, timedelta

import imagehash
from PIL import Image


def procesar_logos_pendientes(supabase_get, supabase_patch, supabase_insert):
    marcas = supabase_get(
        "marcas_vigiladas", "select=id,logo_pendiente&logo_pendiente=not.is.null"
    )
    for m in marcas:
        try:
            img_bytes = base64.b64decode(m["logo_pendiente"])
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            phash = str(imagehash.phash(im))
            dhash = str(imagehash.dhash(im))
            supabase_patch("marcas_vigiladas", m["id"], {
                "logo_phash": phash, "logo_dhash": dhash, "logo_pendiente": None,
            })
        except Exception as e:
            print(f"no se pudo procesar logo de {m['id']}: {e}")


def generar_avisos_vencimiento(supabase_get, supabase_insert):
    hoy = date.today()
    limite = hoy + timedelta(days=90)
    marcas = supabase_get(
        "marcas_vigiladas",
        f"select=id,nombre,fecha_vencimiento&fecha_vencimiento=lte.{limite.isoformat()}"
        f"&fecha_vencimiento=not.is.null",
    )
    # Dedup por (marca, fecha) y no solo por marca: si el usuario actualiza
    # el vencimiento (ej. renovación), la fecha nueva es un caso distinto y
    # amerita un aviso propio, aunque esa marca ya haya sido avisada antes.
    ya_avisadas = {
        (a["marca_vigilada_id"], a["fecha_vencimiento"])
        for a in supabase_get("avisos_vencimiento", "select=marca_vigilada_id,fecha_vencimiento")
    }
    nuevos = []
    for m in marcas:
        if (m["id"], m["fecha_vencimiento"]) in ya_avisadas:
            continue
        venc = date.fromisoformat(m["fecha_vencimiento"])
        dias = (venc - hoy).days
        nuevos.append({
            "marca_vigilada_id": m["id"],
            "fecha_vencimiento": m["fecha_vencimiento"],
            "dias_restantes": dias,
        })
    supabase_insert("avisos_vencimiento", nuevos)
    return nuevos
