"""Fahrweise als PDF (fpdf2, Kernschrift Helvetica: Umlaute gehen, Gedankenstrich, Euro-Zeichen, Emoji und U+2212 nicht)."""
from __future__ import annotations

from fpdf import FPDF

_REPLACE = {"–": "-", "—": "-", "−": "-", "≤": "<=", "≥": ">=", "→": "->", "↔": "<->", "…": "...", "€": "EUR", "·": ".", "Ø": "Durchschnitt", "‰": " Promille", "²": "^2"}
PHASE_TEXT = {"drive": "Antrieb / Halten", "coast": "Rollen (keine Zugkraft)", "brake": "Bremsen"}


def _clean(text: str) -> str:
    for a, b in _REPLACE.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def segments(entry: dict) -> list:
    """Aufeinanderfolgende Zellen gleicher Fahrphase zu Abschnitten zusammenfassen: (Phase, Weg von (km), Weg bis (km), Geschwindigkeit am Anfang (km/h), am Ende (km/h))."""
    out = []
    x, v = entry["x"], entry["v"]
    for k, p in enumerate(entry["phase"]):
        if out and out[-1][0] == p:
            out[-1] = (p, out[-1][1], x[k + 1] / 1000.0, out[-1][3], v[k + 1] * 3.6)
        else:
            out.append((p, x[k] / 1000.0, x[k + 1] / 1000.0, v[k] * 3.6, v[k + 1] * 3.6))
    return out


def generate_plan_pdf(entry: dict, title: str, summary_lines: list) -> bytes:
    """Fahrbefehle: je Abschnitt Fahrphase, Weg und Geschwindigkeit."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _clean(title), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for line in summary_lines:
        pdf.multi_cell(0, 5, _clean(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _clean("Fahrphase | von km | bis km | km/h am Anfang | km/h am Ende"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for p, a, b, va, vb in segments(entry):
        pdf.cell(0, 5, _clean(f"{PHASE_TEXT[p]} | {a:.2f} | {b:.2f} | {va:.0f} | {vb:.0f}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
