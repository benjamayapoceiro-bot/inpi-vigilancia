import os
import requests
import xml.etree.ElementTree as ET
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
        <Cuit>{cuit}</Cuit>
        <Activa>true</Activa>
        <Clave>{clave}</Clave>
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

def consultar_oposiciones_nuevas(marcas_vigiladas, dias_atras=7):
    cuit = os.environ.get("INPI_CUIT")
    clave = os.environ.get("INPI_CLAVE")
    
    if not cuit or not clave:
        print("Faltan INPI_CUIT o INPI_CLAVE, omitiendo consulta de notificaciones de oposición.")
        return []
        
    try:
        ops = obtener_oposiciones_recibidas(cuit, clave, dias_atras)
    except Exception as e:
        print(f"Error consultando ConsultaNotificaciones: {e}")
        return []
        
    alertas_oposicion = []
    
    for op in ops:
        acta_afectada = op.get("acta")
        
        # Buscar la marca en nuestra cartera por número de acta
        marca_afectada = next((m for m in marcas_vigiladas if str(m.get("numero_acta", "")) == str(acta_afectada)), None)
        
        if marca_afectada:
            alertas_oposicion.append({
                "marca_vigilada_id": marca_afectada["id"],
                "tipo_match": "oposicion_recibida",
                "acta_nueva": acta_afectada, # Reusamos este campo para mostrar alerta de que recibió oposición
                "denominacion_nueva": "Oposición contra: " + (op.get("denominacion") or marca_afectada.get("nombre", "")),
                "titular_nuevo": "Tercero Opositor",
                "clase": marca_afectada.get("clase"),
                "requiere_atencion": True,
                "borrador_oposicion": None,
                "similitud": {"score": 1.0, "ortografica": 1.0, "fonetica": 1.0}, # Nivel máximo porque es una alerta crítica directa
            })
            
    return alertas_oposicion
