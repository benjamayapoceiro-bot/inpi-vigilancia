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
    denominacion = txt("#ContentPlaceHolder1_lblDenominacion") or txt(".denominacion") or txt("span[id*='Denominacion']")
    titular = txt("#ContentPlaceHolder1_lblTitular") or txt("span[id*='Titular']")
    clase = txt("#ContentPlaceHolder1_lblClase") or txt("span[id*='Clase']")
    if clase:
        m = re.search(r"\b(\d{1,2})\b", clase)
        clase = m.group(1) if m else clase
    estado = txt("#ContentPlaceHolder1_lblEstado") or txt("span[id*='Estado']")
    reivindicaciones = txt("#ContentPlaceHolder1_lblProductos") or txt("span[id*='Productos']") or txt("div.productos")
    logo = soup.select_one("#ContentPlaceHolder1_imgLogo") or soup.select_one("img[id*='Logo']") or soup.select_one("img.logo-marca")
    logo_url = None
    if logo and logo.get("src"):
        src = logo["src"]
        logo_url = src if src.startswith("http") else "https://portaltramites.inpi.gob.ar/" + src.lstrip("/")
    return {
        "acta": acta,
        "denominacion": denominacion,
        "titular": titular,
        "clase": int(clase) if clase and str(clase).isdigit() else None,
        "estado": estado,
        "reivindicaciones": (reivindicaciones[:4000] if reivindicaciones else None),
        "logo_url": logo_url,
        "expediente_url": f"https://portaltramites.inpi.gob.ar/MarcasConsultas/Resultado?acta={acta}",
    }

if __name__ == "__main__":
    import sys, json
    for a in sys.argv[1:]:
        print(json.dumps(detalle_acta(a), ensure_ascii=False, indent=2))
