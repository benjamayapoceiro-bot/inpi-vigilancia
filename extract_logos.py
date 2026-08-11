"""
Extrae los logos embebidos en el PDF del boletín y los asocia a su acta
correspondiente por proximidad de posición en la página (probado: la
etiqueta "Acta" y la imagen del logo comparten prácticamente el mismo y0).

Calcula DOS hashes por logo (pHash + dHash) para bajar falsos positivos/negativos:
pHash capta estructura de frecuencias (bueno con recortes/ruido), dHash capta
gradientes de brillo (bueno con variaciones de color/contraste). Se exige que
AMBOS coincidan por encima del umbral para considerar "muy parecido".

Devuelve {numero_acta: {"phash": ..., "dhash": ...}}.
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
        words = page.get_text("words")
        actas_en_pagina = []
        for i, w in enumerate(words):
            if w[4] == "Acta" and i + 1 < len(words) and re.match(r"^\d+$", words[i + 1][4]):
                numero_acta = words[i + 1][4]
                actas_en_pagina.append({"numero": numero_acta, "y0": w[1]})

        if not actas_en_pagina:
            continue

        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            y0_img = rects[0].y0
            w_img = rects[0].width

            if w_img > 200:
                continue

            candidatos = [a for a in actas_en_pagina if abs(a["y0"] - y0_img) < tolerancia_y]
            if not candidatos:
                continue
            acta_asociada = min(candidatos, key=lambda a: abs(a["y0"] - y0_img))

            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                im = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                resultado[acta_asociada["numero"]] = {
                    "phash": str(imagehash.phash(im)),
                    "dhash": str(imagehash.dhash(im)),
                }
            except Exception:
                continue

    return resultado


if __name__ == "__main__":
    import sys
    import json

    logos = extraer_logos(sys.argv[1])
    print(f"{len(logos)} logos asociados a actas")
    if len(sys.argv) > 2:
        json.dump(logos, open(sys.argv[2], "w"), indent=2)
        print(f"-> guardado en {sys.argv[2]}")
