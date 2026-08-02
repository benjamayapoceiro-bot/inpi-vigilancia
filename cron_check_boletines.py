"""
Cron semanal — correr con GitHub Actions (ver workflow .yml al final).

Flujo:
1. Lee https://portaltramites.inpi.gob.ar/Boletines?Tipo_Item=3
2. Filtra boletines "MARCAS NUEVAS" no procesados (chequea contra Supabase)
3. Descarga y parsea cada PDF nuevo
4. Corre el matcher contra la cartera de marcas_vigiladas (todas, de todos
   los usuarios) en Supabase
5. Inserta alertas y marca el boletín como procesado

Variables de entorno necesarias:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import re
import json
import requests
from datetime import datetime

from parse_boletin import parse_boletin  # mismo parser ya probado
from matcher import buscar_coincidencias
from extract_logos import extraer_logos

INPI_LISTADO = "https://portaltramites.inpi.gob.ar/Boletines?Tipo_Item=3"
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def supabase_get(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS)
    r.raise_for_status()
    return r.json()


def supabase_insert(tabla, rows):
    if not rows:
        return
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{tabla}", headers=HEADERS, json=rows)
    r.raise_for_status()


def listar_boletines_marcas_nuevas():
    """Trae la página de listado y extrae (numero, fecha, url) de tipo MARCAS NUEVAS."""
    r = requests.get(INPI_LISTADO, timeout=30)
    r.raise_for_status()
    html = r.text

    # Filas de tabla: número, tipo, sector, fecha, url del pdf, comentario
    filas = re.findall(
        r'(\d{4,5})\s*</td>\s*<td[^>]*>\s*Boletines\s*</td>\s*<td[^>]*>\s*Marcas\s*</td>\s*'
        r'<td[^>]*>\s*([\d/]+)[^<]*</td>\s*<td[^>]*>.*?href="([^"]+\.pdf)".*?</td>\s*'
        r'<td[^>]*>\s*MARCAS NUEVAS',
        html, re.DOTALL | re.IGNORECASE,
    )
    return [{"numero": n, "fecha": f, "url": u} for n, f, u in filas]


def main():
    ya_procesados = {
        b["numero_boletin"] for b in supabase_get("boletines_procesados", "select=numero_boletin")
    }

    boletines = listar_boletines_marcas_nuevas()
    nuevos = [b for b in boletines if b["numero"] not in ya_procesados]

    if not nuevos:
        print("Sin boletines nuevos.")
        return

    cartera = supabase_get("marcas_vigiladas", "select=id,nombre,clase,cliente,tipo,logo_phash")
    cartera = [{"id": m["id"], "nombre": m["nombre"], "clase": m["clase"],
                "cliente": m.get("cliente", ""), "tipo": m.get("tipo", "D"),
                "logo_phash": m.get("logo_phash")} for m in cartera]

    for b in nuevos:
        print(f"Procesando boletín {b['numero']}...")
        pdf_bytes = requests.get(b["url"], timeout=60).content
        pdf_path = f"/tmp/{b['numero']}.pdf"
        txt_path = f"/tmp/{b['numero']}.txt"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        os.system(f"pdftotext -layout {pdf_path} {txt_path}")

        actas = parse_boletin(txt_path)

        # Sumar logo_phash a cada acta tipo M
        logos = extraer_logos(pdf_path)
        for acta in actas:
            if acta["tipo"] == "M" and acta["acta"] in logos:
                acta["logo_phash"] = logos[acta["acta"]]

        alertas = buscar_coincidencias(cartera, actas, umbral=0.72, umbral_logo=0.80)

        rows = [{
            "marca_vigilada_id": next(
                (m["id"] for m in cartera if m["nombre"] == al["marca_vigilada"]
                 and m["clase"] == al["clase"]), None),
            "tipo_match": al["tipo_match"],
            "acta_nueva": al["acta_nueva"],
            "denominacion_nueva": al["denominacion_nueva"],
            "clase": al["clase"],
            "titular_nuevo": al["titular_nuevo"],
            "boletin_numero": b["numero"],
            "similitud_ortografica": al["similitud"]["ortografica"],
            "similitud_fonetica": al["similitud"]["fonetica"],
            "similitud_logo": al["similitud"]["score"] if al["tipo_match"] == "logo" else None,
            "similitud_score": al["similitud"]["score"],
        } for al in alertas]

        supabase_insert("alertas", rows)
        supabase_insert("boletines_procesados", [{
            "numero_boletin": b["numero"],
            "fecha_boletin": datetime.strptime(b["fecha"], "%d/%m/%Y").date().isoformat(),
            "tipo": "MARCAS NUEVAS",
            "actas_encontradas": len(actas),
        }])
        print(f"  {len(actas)} actas, {len(alertas)} alertas insertadas.")


if __name__ == "__main__":
    import traceback
    try:
        main()
        supabase_insert("debug_logs", [{"mensaje": "OK: corrida completa sin errores"}])
    except Exception:
        tb = traceback.format_exc()
        print(tb)
        try:
            supabase_insert("debug_logs", [{"mensaje": tb[:4000]}])
        except Exception as e2:
            print("no se pudo ni loguear el error:", e2)
        raise
