"""
Parser de Boletines de Marcas del INPI (texto extraído con pdftotext -layout)
Convierte cada acta en un registro estructurado.
"""
import re
import json
import sys
from pathlib import Path


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_boletin(txt_path: str):
    raw = Path(txt_path).read_text(encoding="utf-8")

    # Cortar encabezados de página tipo:
    # "\x0cN                                    BOLETÍN DE MARCAS Nº 11089 - 29 DE JULIO DE 2026"
    raw = re.sub(r"\x0c?\s*\d*\s*BOLET[ÍI]N DE MARCAS.*", "", raw)
    raw = re.sub(r"\x0c", "\n", raw)

    # Cada acta empieza con "(21) Acta"
    chunks = re.split(r"(?=\(21\)\s*Acta\s+\d+)", raw)

    records = []
    for chunk in chunks:
        m_acta = re.search(r"\(21\)\s*Acta\s+(\d+)\s*-\s*\(51\)\s*Clase\s+(\d+)", chunk)
        if not m_acta:
            continue

        acta = m_acta.group(1)
        clase = m_acta.group(2)

        m_tipo = re.search(r"\(40\)\s*([A-Z])\s*\(54\)[ \t]*([^\n]*)", chunk)
        tipo = m_tipo.group(1) if m_tipo else None
        denominacion = clean(m_tipo.group(2)) if m_tipo else ""
        if re.match(r"^\(\d+\)", denominacion):
            denominacion = ""  # se coló el campo siguiente; tratar como vacía

        m_fecha_sol = re.search(r"\(22\)\s*([\d/]+)", chunk)
        fecha_solicitud = m_fecha_sol.group(1) if m_fecha_sol else None

        # Titular(es): entre (73) y el próximo campo numerado ( (57), (30), (74), (44) )
        m_titular = re.search(
            r"\(73\)\s*(.*?)(?=\(57\)|\(30\)|\(74\)|\(44\)|\Z)", chunk, re.DOTALL
        )
        titular_raw = clean(m_titular.group(1)) if m_titular else ""
        # Separar titulares individuales (vienen como "NOMBRE - PAIS *NOMBRE2 - PAIS *")
        titulares = re.findall(r"([A-ZÁÉÍÓÚÑ0-9.,&' ]+?)\s*-\s*([A-Z]{2})\s*\*", titular_raw)
        titulares = [{"nombre": clean(n), "pais": p} for n, p in titulares]

        # Productos/servicios
        m_prod = re.search(
            r"\(57\)\s*(.*?)(?=\(30\)|\(74\)|\(44\)|\Z)", chunk, re.DOTALL
        )
        productos = clean(m_prod.group(1)) if m_prod else ""

        m_fecha_pub = re.search(r"\(44\)\s*([\d/]+)", chunk)
        fecha_publicacion = m_fecha_pub.group(1) if m_fecha_pub else None

        m_agente = re.search(r"\(74\)\s*([^\n\-]+?)\s*-\s*\(44\)", chunk)
        agente = clean(m_agente.group(1)) if m_agente else None

        records.append({
            "acta": acta,
            "clase": int(clase),
            "tipo": tipo,  # D = denominativa, M = mixta/figurativa
            "denominacion": denominacion,
            "titulares": titulares,
            "fecha_solicitud": fecha_solicitud,
            "fecha_publicacion": fecha_publicacion,
            "agente": agente,
            "productos_servicios": productos[:2000],  # cap por las dudas
        })

    return records


if __name__ == "__main__":
    txt_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else None

    records = parse_boletin(txt_file)
    print(f"{txt_file}: {len(records)} actas parseadas")

    denominativas_vacias = sum(1 for r in records if r["tipo"] == "D" and not r["denominacion"])
    if denominativas_vacias:
        print(f"  ⚠ {denominativas_vacias} actas 'D' sin denominación detectada (revisar)")

    if out_file:
        Path(out_file).write_text(
            json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  -> guardado en {out_file}")
