"""
core_build.py — Agregare randuri + generare Word, reutilizabila de app.py.
"""

from pathlib import Path
from datetime import datetime
from collections import defaultdict

from docx import Document
from docx.shared import Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

PRET_66 = {
    "petresti-sebes-petresti",
    "petresti-rachita-petresti",
}
PRET_DEFAULT = 120


def normalize_ruta_key(ruta: str) -> str:
    return " ".join(ruta.strip().lower().split())


def pret_pentru_ruta(ruta: str):
    key = normalize_ruta_key(ruta)
    if key in PRET_66:
        return 66
    if key:
        return PRET_DEFAULT
    return None


def parse_data(data_str: str):
    data_str = data_str.strip().replace(" ", "")
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(data_str, fmt)
        except ValueError:
            continue
    return None


def incarca_randuri(raw_results: list):
    """raw_results = lista de dict-uri, output-ul lui core_extract.extract_all()"""
    toate_randurile = []
    toate_neclare = []
    for poza in raw_results:
        sursa = poza.get("_sursa_fisier", "?")
        for r in poza.get("randuri", []):
            r["_sursa_fisier"] = sursa
            toate_randurile.append(r)
        for r in poza.get("randuri_neclare", []):
            r["_sursa_fisier"] = sursa
            toate_neclare.append(r)
    return toate_randurile, toate_neclare


def agrega(randuri):
    grupuri = defaultdict(int)
    ordine_zi = defaultdict(list)
    date_parsate = {}

    for r in randuri:
        data_str = r.get("data", "").strip()
        ruta = r.get("ruta", "").strip()
        nr = r.get("nr_curse", 1) or 1
        if not data_str or not ruta:
            continue
        dt = parse_data(data_str)
        if dt is None:
            continue
        date_parsate[data_str] = dt
        key = (data_str, ruta)
        if key not in grupuri:
            ordine_zi[data_str].append(ruta)
        grupuri[key] += nr

    zile_sortate = sorted(date_parsate.keys(), key=lambda d: date_parsate[d])

    randuri_finale = []
    for data_str in zile_sortate:
        for ruta in ordine_zi[data_str]:
            nr_curse = grupuri[(data_str, ruta)]
            pret = pret_pentru_ruta(ruta)
            total = nr_curse * pret if pret is not None else None
            randuri_finale.append({
                "data": data_str,
                "ruta": ruta,
                "nr_curse": nr_curse,
                "pret": pret,
                "total": total,
            })
    return randuri_finale


def set_cell_width(cell, width_cm):
    cell.width = Cm(width_cm)


def build_document(randuri_finale, output_path: Path):
    doc = Document()

    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)

    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Nr.", "Data", "Ruta", "Nr. de curse", "Pret/cursa", "Total"]
    widths_cm = [1.5, 2.8, 7.5, 2.5, 2.5, 2.5]

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        for p in hdr_cells[i].paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.bold = True
        set_cell_width(hdr_cells[i], widths_cm[i])

    total_general = 0
    randuri_fara_pret = []

    for idx, r in enumerate(randuri_finale, start=1):
        row_cells = table.add_row().cells
        row_cells[0].text = str(idx)
        row_cells[1].text = r["data"]
        row_cells[2].text = r["ruta"]
        row_cells[3].text = str(r["nr_curse"])
        row_cells[4].text = str(r["pret"]) if r["pret"] is not None else ""
        row_cells[5].text = str(r["total"]) if r["total"] is not None else ""

        if r["pret"] is None:
            randuri_fara_pret.append((idx, r["data"], r["ruta"]))
        else:
            total_general += r["total"]

        for i, cell in enumerate(row_cells):
            set_cell_width(cell, widths_cm[i])
            for p in cell.paragraphs:
                if i in (0, 1, 3, 4, 5):
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph()
    total_p = doc.add_paragraph()
    total_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = total_p.add_run(f"Total {total_general} RON+TVA")
    run.bold = True

    doc.save(output_path)

    return total_general, randuri_fara_pret


def run_pipeline(raw_results: list, output_path: Path):
    """Functie de conveniente: de la rezultatele brute Gemini pana la Word generat."""
    randuri, neclare = incarca_randuri(raw_results)
    randuri_finale = agrega(randuri)
    total, fara_pret = build_document(randuri_finale, output_path)
    return {
        "randuri_finale": randuri_finale,
        "randuri_neclare": neclare,
        "total_general": total,
        "randuri_fara_pret": fara_pret,
    }
