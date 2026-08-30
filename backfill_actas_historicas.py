"""
Backfill de actas_historicas — puebla la tabla usada por la búsqueda por
similitud (buscar_marcas_similares, vía pg_trgm) a partir de los boletines
que YA se descargaron y procesaron en corridas anteriores del cron.

Es re-corrible sin duplicar: upsert por "acta" (primary key de la tabla).

Variables de entorno necesarias: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import requests
import sys

from parse_boletin import parse_boletin

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}


def log(msg):
    print(msg, flush=True)
    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/debug_logs",
            headers={**HEADERS, "Prefer": ""},
            json=[{"mensaje": f"[backfill] {msg[:3900]}"}],
            timeout=10,
        )
    except Exception:
        pass


def supabase_get(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def supabase_upsert_actas(rows):
    """Upsert en actas_historicas via REST — on_conflict=acta en query param."""
    if not rows:
        return
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/actas_historicas?on_conflict=acta",
        headers=headers,
        json=rows,
        timeout=60,
    )
    if not r.ok:
        raise Exception(f"HTTP {r.status_code}: {r.text[:500]}")


def fecha_iso(fecha_ddmmaaaa):
    if not fecha_ddmmaaaa:
        return None
    try:
        d, m, a = fecha_ddmmaaaa.split("/")
        if not d or not m or not a:
            return None
        return f"{a}-{m.zfill(2)}-{d.zfill(2)}"
    except ValueError:
        return None


def main():
    procesados = supabase_get(
        "boletines_procesados",
        "select=numero_boletin,fecha_boletin&tipo=eq.MARCAS%20NUEVAS&order=numero_boletin.asc"
    )
    log(f"boletines procesados totales: {len(procesados)}")

    ya_en_historico = set()
    try:
        existentes = supabase_get("actas_historicas", "select=boletin_numero")
        ya_en_historico = {a["boletin_numero"] for a in existentes if a.get("boletin_numero")}
    except Exception as e:
        log(f"WARN al leer actas_historicas existentes: {e}")

    pendientes = [p for p in procesados if p["numero_boletin"] not in ya_en_historico]
    log(f"pendientes de volcar: {len(pendientes)}")

    if not pendientes:
        log("nada para hacer, saliendo")
        return

    total_actas = 0
    for p in pendientes:
        numero = p["numero_boletin"]
        url = f"https://portaltramites.inpi.gob.ar/Uploads/Boletines/{numero}_3_.pdf"
        pdf_path = f"/tmp/{numero}.pdf"
        txt_path = f"/tmp/{numero}.txt"
        try:
            pdf_bytes = requests.get(url, timeout=60).content
            if len(pdf_bytes) < 1000:
                log(f"boletin {numero}: PDF muy chico ({len(pdf_bytes)} bytes), probablemente no existe — skip")
                continue
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            ret = os.system(f"pdftotext -layout {pdf_path} {txt_path}")
            if ret != 0:
                log(f"boletin {numero}: pdftotext falló (código {ret})")
                continue

            actas = parse_boletin(txt_path)
            if not actas:
                log(f"boletin {numero}: 0 actas parseadas, skip")
                continue

            rows = [{
                "acta": a["acta"],
                "clase": a["clase"],
                "tipo": a["tipo"],
                "denominacion": a["denominacion"] or None,
                "titulares": a["titulares"],
                "boletin_numero": numero,
                "fecha_publicacion": fecha_iso(a.get("fecha_publicacion")),
            } for a in actas if a.get("acta")]

            supabase_upsert_actas(rows)
            total_actas += len(rows)
            log(f"boletin {numero}: {len(rows)} actas volcadas OK")
        except Exception as e:
            log(f"boletin {numero}: ERROR — {e}")

    log(f"TOTAL: {total_actas} actas nuevas en actas_historicas")


if __name__ == "__main__":
    main()
