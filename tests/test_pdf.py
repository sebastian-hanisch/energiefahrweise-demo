"""Fahrbefehle als PDF: gültige Datei, Kernschrift-Bereinigung, Abschnitte aus Zellen."""
import efw_pdf_export as P


def entry():
    return {"x": [0.0, 250.0, 500.0, 750.0, 1000.0], "v": [0.0, 10.0, 20.0, 20.0, 0.0], "phase": ["drive", "drive", "coast", "brake"]}


def test_segments_merge_consecutive_cells_of_one_phase():
    assert P.segments(entry()) == [("drive", 0.0, 0.5, 0.0, 72.0), ("coast", 0.5, 0.75, 72.0, 72.0), ("brake", 0.75, 1.0, 72.0, 0.0)]


def test_segments_keep_separate_stretches_of_the_same_phase_apart():
    e = {"x": [0.0, 250.0, 500.0, 750.0], "v": [0.0, 10.0, 10.0, 0.0], "phase": ["drive", "coast", "drive"]}
    assert [s[0] for s in P.segments(e)] == ["drive", "coast", "drive"]


def test_pdf_is_a_valid_document():
    data = P.generate_plan_pdf(entry(), "Fahrbefehle", ["Profil flach – Seed 500", "Energie ≤ 400 MJ, v² ‰"])
    assert data.startswith(b"%PDF") and data.rstrip().endswith(b"%%EOF") and len(data) > 1000


def test_clean_replaces_characters_the_core_font_cannot_draw():
    assert P._clean("A – B ≥ C → D … € Ø v² 5‰") == "A - B >= C -> D ... EUR Durchschnitt v^2 5 Promille"
    assert P._clean("Größe äöüß") == "Größe äöüß" and P._clean("Emoji 🚄") == "Emoji ?"
