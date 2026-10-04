"""Abnahmekriterien der Presets: jedes Preset erzählt eine Geschichte, die am gezeigten Profil UND an der Messreihe überprüfbar ist.

Reine Funktionen einfacher Zahlen (`check`), damit Tests sie mit künstlichen Werten einzeln an ihrer Schwelle kippen können; `facts_for` baut die Zahlen aus einer Live-Rechnung, derselben
Rechnung ohne Rückspeisung und der Ergebnisdatei. `tools/preset_search.py` sucht damit einen Seed außerhalb der Messreihen-Seeds, bei dem alle Kriterien aller Presets gelten.
"""
from __future__ import annotations

import efw_evaluation as E
import efw_results as R

NAN = float("nan")

CRITERIA = {
    "Standard": [
        ("naive_close", "Gleichmäßig langsamer liegt höchstens 6 Punkte neben der v²-Formel", lambda f: abs(f["s_naive"] - f["formula"]) <= 6.0),
        ("dp_far", "Das Optimum spart mindestens 10 Punkte mehr als die Formel", lambda f: f["s_dp"] - f["formula"] >= 10.0),
        ("coast_better", "Die Rollpunkt-Regel spart mindestens 8 Punkte mehr als gleichmäßig langsamer", lambda f: f["s_coast"] - f["s_naive"] >= 8.0),
        ("dp_beats_coast", "Das Optimum braucht mindestens 3 % weniger Energie als die Rollpunkt-Regel", lambda f: f["dp_vs_coast"] >= 3.0),
        ("brake", "In der schnellsten Fahrt gehen mindestens 40 % der eingesetzten Energie in die Bremse", lambda f: f["brake_fast"] >= 40.0),
        ("sweep_dp_far", "Messreihe: das Optimum spart im Mittel mindestens 10 Punkte mehr als die Formel", lambda f: f["sweep_dev_dp"] <= -10.0),
        ("sweep_beats", "Messreihe: das Optimum braucht im Mittel mindestens 3 % weniger Energie als die Rollpunkt-Regel", lambda f: f["sweep_dp_vs_coast"] >= 3.0),
    ],
    "Flache Strecke": [
        ("tie", "Das Optimum liegt weniger als 1 % neben der Rollpunkt-Regel", lambda f: abs(f["dp_vs_coast"]) < 1.0),
        ("coast_saves", "Die Rollpunkt-Regel spart mindestens 25 %", lambda f: f["s_coast"] >= 25.0),
        ("naive_close", "Gleichmäßig langsamer liegt höchstens 3 Punkte neben der v²-Formel", lambda f: abs(f["s_naive"] - f["formula"]) <= 3.0),
        ("sweep_tie", "Messreihe: das Optimum liegt im Mittel weniger als 1 % neben der Rollpunkt-Regel", lambda f: abs(f["sweep_dp_vs_coast"]) < 1.0),
    ],
    "Rampe": [
        ("tie", "Das Optimum liegt weniger als 1 % neben der Rollpunkt-Regel", lambda f: abs(f["dp_vs_coast"]) < 1.0),
        ("coast_better", "Die Rollpunkt-Regel spart mindestens 5 Punkte mehr als gleichmäßig langsamer", lambda f: f["s_coast"] - f["s_naive"] >= 5.0),
        ("sweep_tie", "Messreihe: das Optimum liegt im Mittel weniger als 1 % neben der Rollpunkt-Regel", lambda f: abs(f["sweep_dp_vs_coast"]) < 1.0),
    ],
    "Tempolimit": [
        ("naive_beats_formula", "Gleichmäßig langsamer spart mindestens 3 Punkte mehr als die Formel", lambda f: f["s_naive"] - f["formula"] >= 3.0),
        ("dp_beats_coast", "Das Optimum braucht mindestens 5 % weniger Energie als die Rollpunkt-Regel", lambda f: f["dp_vs_coast"] >= 5.0),
        ("sweep_naive", "Messreihe: gleichmäßig langsamer spart im Mittel mindestens 10 Punkte mehr als die Formel", lambda f: f["sweep_s_naive"] - f["formula"] >= 10.0),
        ("sweep_beats", "Messreihe: das Optimum braucht im Mittel mindestens 8 % weniger Energie als die Rollpunkt-Regel", lambda f: f["sweep_dp_vs_coast"] >= 8.0),
    ],
    "Starkes Gefälle": [
        ("coast_ok", "Die Rollpunkt-Regel erreicht das Fahrzeitbudget", lambda f: f["coast_ok"]),
        ("dp_saves", "Das Optimum spart mindestens 50 %", lambda f: f["s_dp"] >= 50.0),
        ("dp_beats_coast", "Das Optimum braucht mindestens 15 % weniger Energie als die Rollpunkt-Regel", lambda f: f["dp_vs_coast"] >= 15.0),
        ("sweep_beats", "Messreihe: das Optimum braucht im Mittel mindestens 25 % weniger Energie als die Rollpunkt-Regel", lambda f: f["sweep_dp_vs_coast"] >= 25.0),
    ],
    "Mit Rückspeisung": [
        ("regen", "Rückspeisung ist eingeschaltet", lambda f: f["regen"]),
        ("halved", "Der Vorsprung des Optimums gegenüber gleichmäßig langsamer ist höchstens 70 % des Vorsprungs ohne Rückspeisung", lambda f: f["dp_vs_a"] <= 0.7 * f["ref_dp_vs_a"]),
        ("still_positive", "Das Optimum spart noch mindestens 3 % gegenüber gleichmäßig langsamer", lambda f: f["dp_vs_a"] >= 3.0),
        ("sweep_halved", "Messreihe: mit Rückspeisung ist der Vorsprung im Mittel höchstens 70 % des Vorsprungs ohne", lambda f: f["sweep_regen_dp_vs_a"] <= 0.7 * f["sweep_dp_vs_a"]),
    ],
}


def facts_for(run: dict, ref: dict, res: dict, settings: dict) -> dict:
    """Die Zahlen für die Kriterien. `ref` = dieselbe Rechnung ohne Rückspeisung (für Presets ohne Rückspeisung der Lauf selbst)."""
    typ = settings["profile"]
    r10 = R.summary(res, typ, 10.0)
    f = {"s_naive": E.saving_pct(run, "naive"), "s_coast": E.saving_pct(run, "coast"), "s_dp": E.saving_pct(run, "dp"), "formula": E.formula_saving(run["reserve"]),
         "dp_vs_coast": E.dp_vs_pct(run, "coast"), "dp_vs_a": E.dp_vs_pct(run, "naive"), "ref_dp_vs_a": E.dp_vs_pct(ref, "naive"), "brake_fast": E.brake_share_pct(run["results"]["fast"]),
         "coast_ok": run["coast_ok"], "regen": settings["regen"] == "mit", "sweep_dev_dp": r10["dev_dp"], "sweep_dp_vs_coast": r10["dp_vs_coast"], "sweep_dp_vs_a": r10["dp_vs_a"],
         "sweep_s_naive": r10["saving_a"], "sweep_regen_dp_vs_a": NAN}
    if typ in res["meta"]["regen_types"]:
        f["sweep_regen_dp_vs_a"] = R.regen_summary(res, typ)["dp_vs_a"]
    return f


def check(preset: str, facts: dict) -> list:
    """Liste (Kennung, Text, erfüllt) der Kriterien eines Presets."""
    return [(cid, text, bool(fn(facts))) for cid, text, fn in CRITERIA[preset]]
