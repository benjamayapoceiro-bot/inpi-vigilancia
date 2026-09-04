import re
import requests
from bs4 import BeautifulSoup

BASE = "https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado"
HEADERS = {"User-Agent": "Mozilla/5.0 (INPI Vigilancia)"}

def detalle_acta(acta: str, timeout=20) -> dict:
    acta = str(acta).strip()
    if not acta:
        raise ValueError("acta vacía")
    r = requests.get(f"{BASE}?acta={acta}", headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    def txt(sel):
        el = soup.select_one(sel)
        return el.get_text(" ", strip=True) if el else None
    def txt_any(patterns):
        for p in patterns:
            v = txt(p)
            if v:
                return v
        return None
    denominacion = txt_any(["#ContentPlaceHolder1_lblDenominacion", ".denominacion", "span[id*='Denominacion']", "td:contains('DENOMINACIÓN') + td"])
    titular = txt_any(["#ContentPlaceHolder1_lblTitular", "span[id*='Titular']", "td:contains('NOMBRE') + td"])
    clase = txt_any(["#ContentPlaceHolder1_lblClase", "span[id*='Clase']", "td:contains('CLASE') + td"])
    if clase:
        m = re.search(r"\b(\d{1,2})\b", clase)
        clase = m.group(1) if m else clase
    estado = txt_any(["#ContentPlaceHolder1_lblEstado", "span[id*='Estado']", "td:contains('ESTADO') + td"])
    presentacion = txt_any(["td:contains('PRESENTACIÓN') + td", "span[id*='Presentacion']"])
    tipo_marca = txt_any(["td:contains('TIPO DE MARCA') + td", "span[id*='TipoMarca']"])
    reivindicaciones = txt_any(["#ContentPlaceHolder1_lblProductos", "span[id*='Productos']", "div.productos", "td:contains('LIMITACION') + td", "td:contains('PROTECCION') + td"])
    domicilio_legal = txt_any(["td:contains('DOMICILIO LEGAL') + td"])
    domicilio_real = txt_any(["td:contains('DOMICILIO REAL') + td"])
    cuit = txt_any(["td:contains('CUIT') + td", "span[id*='Cuit']"])
    dni = txt_any(["td:contains('DNI:') + td", "td:contains('DNI') + td"])
    logo = soup.select_one("#ContentPlaceHolder1_imgLogo") or soup.select_one("img[id*='Logo']") or soup.select_one("img.logo-marca") or soup.select_one("img[src*='Maujo']")
    logo_url = None
    if logo and logo.get("src"):
        src = logo["src"]
        logo_url = src if src.startswith("http") else "https://portaltramites.inpi.gob.ar/" + src.lstrip("/")
    # Fallback: si no se pudo parsear nada, al menos devolver acta y URL para no romper el modal
    if not denominacion and not titular and not clase:
        # No se pudo parsear, devolver objeto mínimo pero no null para evitar crash en frontend
        return {
            "acta": acta,
            "denominacion": None,
            "titular": None,
            "clase": None,
            "estado": None,
            "presentacion": None,
            "tipo_marca": None,
            "domicilio_legal": None,
            "domicilio_real": None,
            "cuit": None,
            "dni": None,
            "reivindicaciones": None,
            "logo_url": logo_url,
            "expediente_url": f"https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado?acta={acta}",
        }
    return {
        "acta": acta,
        "denominacion": denominacion,
        "titular": titular,
        "clase": int(clase) if clase and str(clase).isdigit() else None,
        "presentacion": presentacion,
        "tipo_marca": tipo_marca,
        "estado": estado,
        "domicilio_legal": domicilio_legal,
        "domicilio_real": domicilio_real,
        "cuit": cuit,
        "dni": dni,
        "reivindicaciones": (reivindicaciones[:4000] if reivindicaciones else None),
        "logo_url": logo_url,
        "expediente_url": f"https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado?acta={acta}",
    }

if __name__ == "__main__":
    import sys, json
    for a in sys.argv[1:]:
        print(json.dumps(detalle_acta(a), ensure_ascii=False, indent=2))
