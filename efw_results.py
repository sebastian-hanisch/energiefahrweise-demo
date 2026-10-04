"""Vorgerechnete Messreihe (data/efw_results.json, erzeugt mit tools/sweep.py): Auswertung je Profiltyp und Fahrzeitreserve. Die App rechnet sie nie live."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import efw_constants as C
import efw_evaluation as E

ROOT = Path(__file__).resolve().parent


def load_results(path=None) -> dict:
    return json.loads(Path(path or ROOT / C.RESULTS_FILE).read_text(encoding="utf-8"))


def mean_se(xs) -> tuple:
    xs = list(xs)
    return st.mean(xs), (st.stdev(xs) / len(xs) ** 0.5 if len(xs) > 1 else float("nan"))


def rows_of(res: dict, typ: str, reserve: float, regen: bool = False) -> list:
    return [r for r in res["rows"] if r["type"] == typ and abs(r["reserve"] - reserve) < 1e-9 and bool(r["regen"]) == regen]


def saving(row: dict, key: str) -> float:
    """Ersparnis in Prozent der Energie der schnellsten Fahrt."""
    return 100.0 * (1.0 - row[f"E_{key}"] / row["E_fast"])


def gap(row: dict, key: str, ref: str) -> float:
    """Um wie viel Prozent `key` weniger Energie braucht als `ref` (Basis = Referenz)."""
    return 100.0 * (1.0 - row[f"E_{key}"] / row[f"E_{ref}"])


def summary(res: dict, typ: str, reserve: float, regen: bool = False) -> dict:
    rows = rows_of(res, typ, reserve, regen)
    form = E.formula_saving(reserve)
    out = {"n": len(rows), "reserve": reserve, "formula": form}
    ok_coast = [r for r in rows if r["E_coast"] is not None]
    out["n_coast"] = len(ok_coast)
    out["n_dp"] = sum(1 for r in rows if r["E_dp"] is not None)
    for key in ("a", "dp"):
        out[f"saving_{key}"], out[f"saving_{key}_se"] = mean_se(saving(r, key) for r in rows)
    out["saving_coast"], out["saving_coast_se"] = mean_se(saving(r, "coast") for r in ok_coast) if ok_coast else (float("nan"), float("nan"))
    out["dp_vs_a"], out["dp_vs_a_se"] = mean_se(gap(r, "dp", "a") for r in rows)
    out["dp_vs_coast"], out["dp_vs_coast_se"] = mean_se(gap(r, "dp", "coast") for r in ok_coast) if ok_coast else (float("nan"), float("nan"))
    out["dp_vs_coast_max"] = max(gap(r, "dp", "coast") for r in ok_coast) if ok_coast else float("nan")
    out["dev_a"], out["dev_a_se"] = mean_se(form - saving(r, "a") for r in rows)
    out["dev_dp"], out["dev_dp_se"] = mean_se(form - saving(r, "dp") for r in rows)
    out["E_fast"] = st.mean(r["E_fast"] for r in rows)
    out["E_dp"] = st.mean(r["E_dp"] for r in rows)
    out["brake_fast"], out["brake_fast_se"] = mean_se(brake_share(r["balance_fast"]) for r in rows)
    out["coast_share"], out["coast_share_se"] = mean_se(r["coast_share_dp"] for r in rows)
    return out


def brake_share(b: dict) -> float:
    """Bremsverlust in Prozent der eingesetzten Energie (Traktion plus beim Bergabfahren frei werdende Lageenergie)."""
    supply = b["traction"] + max(-b["lift"], 0.0)
    return 100.0 * b["brake"] / supply


def curve(res: dict, typ: str, key: str) -> list:
    """Mittlere Ersparnis (Prozent) je Fahrzeitreserve der Messreihe für `key` (a, coast, dp)."""
    out = []
    for r in res["meta"]["reserves"]:
        rows = [x for x in rows_of(res, typ, r) if x[f"E_{key}"] is not None]
        out.append(st.mean(saving(x, key) for x in rows))
    return out


def regen_summary(res: dict, typ: str) -> dict:
    return summary(res, typ, res["meta"]["regen_reserve"], regen=True)


def cell_exists(settings: dict) -> bool:
    """Gibt es zu den Einstellungen eine Messreihen-Zelle (Profiltyp und Reserve, ohne Rückspeisung)? Der Seed gehört nicht dazu."""
    return settings["regen"] == "aus" and any(abs(settings["reserve"] - r) < 1e-9 for r in C.SWEEP_RESERVES)
