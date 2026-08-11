"""
Re-escanea boletines YA procesados contra la cartera actual de marcas_vigiladas.
Útil para cuando agregás una marca nueva a vigilar y querés chequearla contra
el historial ya descargado, sin esperar al próximo boletín.

No vuelve a tocar boletines_procesados (evita duplicar ese registro).
"""
import os
import requests

from parse_boletin import parse_boletin
from matcher import buscar_coincidencias
from extract_logos import extraer_logos

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}


def supabase_get(tabla, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}?{params}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def supabase_insert(tabla, rows):
    if not rows:
        return
    r = requests.post(f"{SUPABASE_URL}/rest/v1/{tabla}", headers=HEADERS, json=rows, timeout=30)
    r.raise_for_status()


def main():
    procesados = supabase_get("boletines_procesados", "select=numero_boletin,tipo&tipo=eq.MARCAS NUEVAS")
    cartera = supabase_get("marcas_vigiladas", "select=id,nombre,clase,cliente,tipo,logo_phash,logo_dhash")
    cartera = [{"id": m["id"], "nombre": m["nombre"], "clase": m["clase"],
                "cliente": m.get("cliente", ""), "tipo": m.get("tipo", "D"),
                "logo_phash": m.get("logo_phash"), "logo_dhash": m.get("logo_dhash")} for m in cartera]

    total_alertas = 0
    for p in procesados:
        numero = p["numero_boletin"]
        url = f"https://portaltramites.inpi.gob.ar/Uploads/Boletines/{numero}_3_.pdf"
        pdf_path, txt_path = f"/tmp/{numero}.pdf", f"/tmp/{numero}.txt"
        try:
            pdf_bytes = requests.get(url, timeout=60).content
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            os.system(f"pdftotext -layout {pdf_path} {txt_path}")
            actas = parse_boletin(txt_path)
            logos = extraer_logos(pdf_path)
            for acta in actas:
                if acta["tipo"] == "M" and acta["acta"] in logos:
                    acta["logo_phash"] = logos[acta["acta"]]["phash"]
                    acta["logo_dhash"] = logos[acta["acta"]]["dhash"]

            alertas = buscar_coincidencias(cartera, actas, umbral=0.72, umbral_logo=0.80)
            rows = [{
                "marca_vigilada_id": next((m["id"] for m in cartera if m["nombre"] == al["marca_vigilada"]
                                            and m["clase"] == al["clase"]), None),
                "tipo_match": al["tipo_match"], "acta_nueva": al["acta_nueva"],
                "denominacion_nueva": al["denominacion_nueva"], "clase": al["clase"],
                "titular_nuevo": al["titular_nuevo"], "boletin_numero": numero,
                "similitud_ortografica": al["similitud"]["ortografica"],
                "similitud_fonetica": al["similitud"]["fonetica"],
                "similitud_logo": al["similitud"]["score"] if al["tipo_match"] == "logo" else None,
                "similitud_score": al["similitud"]["score"],
                "requiere_atencion": al["requiere_atencion"],
                "borrador_oposicion": al["borrador_oposicion"],
            } for al in alertas]
            supabase_insert("alertas", rows)
            total_alertas += len(rows)
            print(f"boletin {numero}: {len(actas)} actas, {len(rows)} alertas")
        except Exception as e:
            print(f"boletin {numero}: ERROR {e}")

    print(f"TOTAL: {total_alertas} alertas")


if __name__ == "__main__":
    main()
