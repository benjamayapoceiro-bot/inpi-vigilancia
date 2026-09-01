"""
Manda un mail de resumen cuando el cron encuentra algo que amerita
atención: alertas con score >= 0.85 o vencimientos dentro de 90 días.

Requiere en el entorno:
  GMAIL_ADDRESS — tu dirección de Gmail
  GMAIL_APP_PASSWORD — contraseña de aplicación (myaccount.google.com/apppasswords,
                        requiere verificación en 2 pasos activada)
"""
import os
import smtplib
from email.mime.text import MIMEText


def enviar_resumen(alertas_fuertes: list, avisos_vencimiento: list, destinatario: str = None):
    address = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not address or not app_password:
        print("Sin GMAIL_ADDRESS/GMAIL_APP_PASSWORD configurados, no se manda mail")
        return

    if not alertas_fuertes and not avisos_vencimiento:
        return  # nada urgente, no molestar por mail

    partes = []
    if alertas_fuertes:
        oposiciones = [a for a in alertas_fuertes if a.get("tipo_match") == "oposicion_recibida"]
        similares = [a for a in alertas_fuertes if a.get("tipo_match") != "oposicion_recibida"]
        
        if oposiciones:
            partes.append(f"🚨 {len(oposiciones)} OPOSICIÓN(ES) RECIBIDA(S):\n")
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

    cuerpo = "\n".join(partes)
    msg = MIMEText(cuerpo)
    msg["Subject"] = f"Vigilancia INPI — {len(alertas_fuertes)} alerta(s), {len(avisos_vencimiento)} vencimiento(s)"
    msg["From"] = address
    msg["To"] = destinatario or address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(address, app_password)
        server.send_message(msg)
    print("Mail de resumen enviado.")
