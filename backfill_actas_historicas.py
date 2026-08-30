"""
Backfill de actas_historicas — puebla la tabla usada por la búsqueda por
similitud (buscar_marcas_similares, vía pg_trgm) a partir de los boletines
que YA se descargaron y procesaron en corridas anteriores del cron.

A diferencia de cron_check_boletines.py y rescan_cartera.py, acá se inserta
TODA acta del boletín (no solo las que matchean contra la cartera vigilada),
porque el objetivo es tener un histórico completo contra el cual correr
búsquedas previas de clientes nuevos.

Es re-corrible sin duplicar: upsert por "acta" (primary key de la tabla).

Variables de entorno necesarias: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import requests

from parse_boletin import parse_boletin

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def supabase_get(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def supabase_upsert(tabla, rows, on_conflict):
    if not rows:
        return
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates"}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{tabla}?on_conflict={on_conflict}",
        headers=headers, json=rows, timeout=60,
    )
    r.raise_for_status()


def fecha_iso(fecha_ddmmaaaa):
    if not fecha_ddmmaaaa:
        return None
    try:
        d, m, a = fecha_ddmmaaaa.split("/")
        return f"{a}-{m}-{d}"
    except ValueError:
        return None


def main():
    procesados = supabase_get("boletines_procesados", "select=numero_boletin,fecha_boletin&tipo=eq.MARCAS%20NUEVAS&order=numero_boletin.asc")
    ya_en_historico = {a["boletin_numero"] for a in supabase_get("actas_historicas", "select=boletin_numero") if a.get("boletin_numero")}

    pendientes = [p for p in procesados if p["numero_boletin"] not in ya_en_historico]
    print(f"{len(procesados)} boletines procesados en total, {len(pendientes)} sin volcar al histórico todavía")

    total_actas = 0
    for p in pendientes:
        numero = p["numero_boletin"]
        url = f"https://portaltramites.inpi.gob.ar/Uploads/Boletines/{numero}_3_.pdf"
        pdf_path, txt_path = f"/tmp/{numero}.pdf", f"/tmp/{numero}.txt"
        try:
            pdf_bytes = requests.get(url, timeout=60).content
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            os.system(f"pdftotext -layout {pdf_path} {txt_path}")
            actas = parse_boletin(txt_path)

            rows = [{
                "acta": a["acta"],
                "clase": a["clase"],
                "tipo": a["tipo"],
                "denominacion": a["denominacion"] or None,
                "titulares": a["titulares"],
                "boletin_numero": numero,
                "fecha_publicacion": fecha_iso(a.get("fecha_publicacion")),
            } for a in actas if a.get("acta")]

            supabase_upsert("actas_historicas", rows, on_conflict="acta")
            total_actas += len(rows)
            print(f"boletin {numero}: {len(rows)} actas volcadas al histórico")
        except Exception as e:
            print(f"boletin {numero}: ERROR {e}")

    print(f"TOTAL: {total_actas} actas nuevas en actas_historicas")


if __name__ == "__main__":
    main()
