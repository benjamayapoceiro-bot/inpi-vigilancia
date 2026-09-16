"""
Manda mails de resumen cuando el cron encuentra algo que amerita
atención: alertas con score >= 0.85 o vencimientos dentro de 90 días.

Un solo remitente (Gmail del admin) reparte a cada estudio: el cron
agrupa por estudio y cada uno recibe SOLO lo suyo en su
email_contacto — el estudio no configura nada.

Requiere en el entorno:
  GMAIL_ADDRESS — tu dirección de Gmail (remitente y resumen admin)
  GMAIL_APP_PASSWORD — contraseña de aplicación (myaccount.google.com/apppasswords,
                         requiere verificación en 2 pasos activada)
"""
import os
import smtplib
import time
from email.mime.text import MIMEText

DOMINIOS_FALSOS = ("demo.fons.legal", "demo.test", "example.com", "example.test")


def es_email_real(email: str) -> bool:
    if not email or "@" not in email:
        return False
    dom = email.strip().lower().split("@")[-1]
    return dom not in DOMINIOS_FALSOS


def _credenciales():
    return os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD")


def _armar_cuerpo(alertas_fuertes: list, avisos_vencimiento: list, nombre_estudio: str = None):
    partes = []
    if nombre_estudio:
        partes.append(f"Hola {nombre_estudio}, esto detectó la vigilancia automática:\n")
    if alertas_fuertes:
        oposiciones = [a for a in alertas_fuertes if a.get("tipo_match") == "oposicion_recibida"]
        resoluciones = [a for a in alertas_fuertes if a.get("tipo_match") == "resolucion"]
        similares = [a for a in alertas_fuertes if a.get("tipo_match") not in ("oposicion_recibida", "resolucion")]

        if resoluciones:
            partes.append(f"✅ {len(resoluciones)} RESOLUCIÓN(ES) — el INPI no avisa, nosotros sí:\n")
            for a in resoluciones:
                ev = (a.get("evidencia") or [{}])[0]
                partes.append(f"  - {a.get('marca_vigilada') or a.get('denominacion_nueva') or '(marca)'} (Acta {a.get('acta_nueva')}) {ev.get('estado_viejo','?')} → {ev.get('estado_nuevo','?')}"
                              f" — {a.get('enlace_inpi','')}")

        if oposiciones:
            partes.append(f"\n🚨 {len(oposiciones)} OPOSICIÓN(ES) RECIBIDA(S):\n")
            for a in oposiciones:
                partes.append(f"  - {a.get('denominacion_nueva', '(desconocida)')} (Acta nuestra afectada: {a.get('acta_nueva')})")

        if similares:
            partes.append(f"\n⚠ {len(similares)} marca(s) nueva(s) muy parecidas a tu cartera:\n")
            for a in similares:
                partes.append(
                    f"  - Acta {a['acta_nueva']}: \"{a.get('denominacion_nueva') or '(logo)'}\" "
                    f"(clase {a['clase']}, {round(a.get('similitud', {}).get('score', 0)*100)}% similitud)"
                )
    if avisos_vencimiento:
        partes.append(f"\n📅 {len(avisos_vencimiento)} marca(s) por vencer en menos de 90 días:\n")
        for v in avisos_vencimiento:
            partes.append(f"  - Vence el {v['fecha_vencimiento']} (en {v['dias_restantes']} días)")

    partes.append("\nVer el detalle completo en el dashboard:")
    partes.append("https://benjamayapoceiro-bot.github.io/inpi-vigilancia-dashboard/")
    return "\n".join(partes)


def _mandar(address: str, app_password: str, destinatario: str, asunto: str, cuerpo: str):
    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = address
    msg["To"] = destinatario
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, app_password)
        server.send_message(msg)


def enviar_resumen(alertas_fuertes: list, avisos_vencimiento: list, destinatario: str = None):
    address, app_password = _credenciales()
    if not address or not app_password:
        print("Sin GMAIL_ADDRESS/GMAIL_APP_PASSWORD configurados, no se manda mail")
        return

    if not alertas_fuertes and not avisos_vencimiento:
        return  # nada urgente, no molestar por mail

    cuerpo = _armar_cuerpo(alertas_fuertes, avisos_vencimiento)
    _mandar(address, app_password, destinatario or address,
            f"Vigilancia INPI — {len(alertas_fuertes)} alerta(s), {len(avisos_vencimiento)} vencimiento(s)",
            cuerpo)
    print("Mail de resumen enviado.")


def enviar_a_estudio(destinatario: str, nombre_estudio: str, alertas: list, vencimientos: list):
    """Mail individual a un estudio con SOLO sus alertas/vencimientos.
    El remitente siempre es el Gmail de la plataforma."""
    address, app_password = _credenciales()
    if not address or not app_password:
        print("Sin GMAIL_ADDRESS/GMAIL_APP_PASSWORD configurados, no se manda mail")
        return False
    if not es_email_real(destinatario):
        print(f"email no válido para estudio {nombre_estudio}, se omite")
        return False
    if not alertas and not vencimientos:
        return False
    cuerpo = _armar_cuerpo(alertas, vencimientos, nombre_estudio)
    _mandar(address, app_password, destinatario,
            f"Vigilancia INPI — {len(alertas)} alerta(s), {len(vencimientos)} vencimiento(s)",
            cuerpo)
    print(f"Mail enviado a estudio {nombre_estudio} <{destinatario}>.")
    return True


def repartir_por_estudio(grupos: dict):
    """grupos: {email: {"nombre": str, "alertas": [...], "vencimientos": [...]}}.
    Best-effort: un fallo no frena al resto. Devuelve cantidad enviada."""
    enviados = 0
    for email, g in grupos.items():
        try:
            if enviar_a_estudio(email, g.get("nombre") or "estudio",
                                g.get("alertas") or [], g.get("vencimientos") or []):
                enviados += 1
        except Exception as e:
            print(f"no se pudo mandar a {email}: {e}")
        time.sleep(1)  # Gmail limita envíos por minuto
    return enviados
