import os
import requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from datetime import datetime, timedelta

def obtener_oposiciones_recibidas(cuit, clave, dias_atras=7):
    url = "https://portaltramites.inpi.gob.ar/ServicioWeb/wsTramites.asmx"
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://tempuri.org/ConsultaNotificaciones"
    }

    hoy = datetime.now()
    fecha_final = hoy.strftime("%Y-%m-%d")
    fecha_inicial = (hoy - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

    payload = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <ConsultaNotificaciones xmlns="http://tempuri.org/">
      <fechaInicial>{fecha_inicial}</fechaInicial>
      <fechafinal>{fecha_final}</fechafinal>
      <expediente></expediente>
      <direccion></direccion>
      <tipoNotificacion></tipoNotificacion>
      <datosUsuario>
        <Cuit>{escape(str(cuit))}</Cuit>
        <Activa>true</Activa>
        <Clave>{escape(str(clave))}</Clave>
      </datosUsuario>
    </ConsultaNotificaciones>
  </soap:Body>
</soap:Envelope>"""

    response = requests.post(url, data=payload, headers=headers, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.text)
    
    oposiciones = []
    # Parsea iterativamente ignorando namespaces
    for elem in root.iter():
        tag = elem.tag.lower()
        if "notificacion" in tag and "tipo" not in tag and "result" not in tag:
            acta = ""
            denominacion = ""
            notif_tipo = ""
            for child in elem:
                ctag = child.tag.lower()
                if "acta" in ctag:
                    acta = child.text
                elif "denominacion" in ctag or "marca" in ctag:
                    denominacion = child.text
                elif "tipo" in ctag:
                    notif_tipo = child.text or ""

            # Filtramos sólo oposiciones (el tipo puede venir como 'OPOSICION' o similar)
            if acta and "oposici" in notif_tipo.lower():
                oposiciones.append({
                    "acta": acta.strip(),
                    "denominacion": (denominacion or "").strip(),
                })
    
    return oposiciones

def consultar_oposiciones_nuevas(marcas_vigiladas, credenciales, dias_atras=7, reportar=None):
    """Consulta notificaciones por cada estudio con credenciales entregadas
    exclusivamente por el RPC service_role de Supabase. Nunca registra CUIT ni clave."""
    def log(mensaje):
        print(mensaje)
        if callable(reportar):
            try:
                reportar(mensaje)
            except Exception:
                pass

    alertas_oposicion = []
    for cred in credenciales or []:
        estudio_id = str(cred.get("estudio_id") or "")
        cuit = cred.get("cuit")
        clave = cred.get("clave")
        if not estudio_id or not cuit or not clave:
            log("WARN oposiciones INPI: registro de credencial incompleto; se omite.")
            continue

        cartera_estudio = [
            m for m in marcas_vigiladas
            if str(m.get("estudio_id") or "") == estudio_id and m.get("numero_acta")
        ]
        if not cartera_estudio:
            log(f"INFO oposiciones INPI: estudio {estudio_id[:8]} sin actas vigiladas.")
            continue

        try:
            ops = obtener_oposiciones_recibidas(cuit, clave, dias_atras)
            log(f"ConsultaNotificaciones INPI estudio {estudio_id[:8]}: {len(ops)} notificaciones en {dias_atras} días.")
        except Exception as e:
            log(f"ERROR ConsultaNotificaciones INPI estudio {estudio_id[:8]}: {type(e).__name__}: {str(e)[:400]}")
            continue

        por_acta = {str(m.get("numero_acta", "")).strip(): m for m in cartera_estudio}
        sin_vinculo = 0
        for op in ops:
            acta_afectada = str(op.get("acta") or "").strip()
            marca_afectada = por_acta.get(acta_afectada)
            if not marca_afectada:
                sin_vinculo += 1
                continue

            alertas_oposicion.append({
                "marca_vigilada_id": marca_afectada["id"],
                "tipo_match": "oposicion_recibida",
                "acta_nueva": acta_afectada,
                "denominacion_nueva": "Oposición contra: " + (op.get("denominacion") or marca_afectada.get("nombre", "")),
                "titular_nuevo": "Tercero opositor (identidad a verificar en INPI)",
                "clase": marca_afectada.get("clase"),
                "clase_acta": marca_afectada.get("clase"),
                "relacion_clases": "misma",
                "requiere_atencion": True,
                "requiere_oposicion": False,
                "borrador_oposicion": None,
                "similitud": {"score": 1.0, "ortografica": 1.0, "fonetica": 1.0},
                "nivel_riesgo": "alto",
            })
        log(f"Oposiciones vinculadas estudio {estudio_id[:8]}: {len(ops) - sin_vinculo}; sin acta en cartera: {sin_vinculo}.")

    return alertas_oposicion
