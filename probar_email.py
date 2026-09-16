"""Prueba manual del mail de vigilancia al admin.
Uso: GMAIL_ADDRESS=... GMAIL_APP_PASSWORD=... python3 probar_email.py
Arma 1 alerta logo + 1 texto con datos REALES de la DB (solo lectura)
y las manda con enviar_resumen para validar SMTP/Gmail.
"""
import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://oomczohvjqycpuhhmotv.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
DEST = os.environ.get("GMAIL_ADDRESS", "benjamayapoceiro@gmail.com")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notificar_email import enviar_resumen


def main():
    alertas = []
    if SERVICE_KEY:
        h = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/alertas",
            headers=h,
            params={"select": "acta_nueva,denominacion_nueva,clase,tipo_match,similitud_score,boletin_numero,logo_url_acta,logo_url_cartera,enlace_inpi,marcas_vigiladas(nombre)", "order": "created_at.desc", "limit": "2"},
            timeout=30,
        )
        r.raise_for_status()
        for a in r.json():
            alertas.append({
                "tipo_match": a.get("tipo_match"),
                "marca_vigilada": (a.get("marcas_vigiladas") or {}).get("nombre"),
                "acta_nueva": a.get("acta_nueva"),
                "denominacion_nueva": a.get("denominacion_nueva"),
                "clase": a.get("clase"),
                "similitud": {"score": float(a.get("similitud_score") or 0)},
                "enlace_inpi": a.get("enlace_inpi") or "",
                "evidencia": [{}],
            })
    if not alertas:
        alertas = [{
            "tipo_match": "logo", "marca_vigilada": "MARCA PRUEBA",
            "acta_nueva": "0000000", "denominacion_nueva": "",
            "clase": 36, "similitud": {"score": 0.851},
            "enlace_inpi": "", "evidencia": [{}],
        }]
    print(f"Mandando prueba a {DEST} con {len(alertas)} alerta(s)...")
    enviar_resumen(alertas, [], destinatario=DEST)
    print("OK prueba enviada (revisá spam si no llega).")


if __name__ == "__main__":
    main()
