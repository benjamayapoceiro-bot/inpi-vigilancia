"""
Extrae los logos embebidos en el PDF del boletín y los asocia a su acta
correspondiente por proximidad de posición en la página (probado: la
etiqueta "Acta" y la imagen del logo comparten prácticamente el mismo y0).

Devuelve {numero_acta: phash_hex} para fusionar con la salida de parse_boletin.py.
"""
import fitz
import imagehash
from PIL import Image
import io
import re


def extraer_logos(pdf_path: str, tolerancia_y: float = 15.0) -> dict:
    doc = fitz.open(pdf_path)
    resultado = {}

    for page in doc:
        # Posiciones de cada etiqueta "Acta" y el número que le sigue
        words = page.get_text("words")  # (x0,y0,x1,y1,texto,block,line,word_no)
        actas_en_pagina = []
        for i, w in enumerate(words):
            if w[4] == "Acta" and i + 1 < len(words) and re.match(r"^\d+$", words[i + 1][4]):
                numero_acta = words[i + 1][4]
                actas_en_pagina.append({"numero": numero_acta, "y0": w[1]})

        if not actas_en_pagina:
            continue

        # Imágenes de la página con su posición
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            y0_img = rects[0].y0
            w_img = rects[0].width

            # Descartar banners de encabezado (muy anchos) — los logos son ~cuadrados/chicos
            if w_img > 200:
                continue

            # Asociar a la acta cuya etiqueta tiene el y0 más cercano
            candidatos = [a for a in actas_en_pagina if abs(a["y0"] - y0_img) < tolerancia_y]
            if not candidatos:
                continue
            acta_asociada = min(candidatos, key=lambda a: abs(a["y0"] - y0_img))

            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                im = Image.open(io.BytesIO(pix.tobytes("png")))
                resultado[acta_asociada["numero"]] = str(imagehash.phash(im))
            except Exception:
                continue  # imagen corrupta o formato no soportado, se omite

    return resultado


if __name__ == "__main__":
    import sys
    import json

    logos = extraer_logos(sys.argv[1])
    print(f"{len(logos)} logos asociados a actas")
    if len(sys.argv) > 2:
        json.dump(logos, open(sys.argv[2], "w"), indent=2)
        print(f"-> guardado en {sys.argv[2]}")
