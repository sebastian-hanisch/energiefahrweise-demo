"""Auswertung der Messreihe an einer von Hand gerechneten Mini-Ergebnisdatei."""
import json
import math

import pytest

import efw_constants as C
import efw_evaluation as E
import efw_results as R


def row(typ, seed, a, coast, dp, regen=False, reserve=10.0, share=50.0, bal=None):
    bal = bal or {"traction": 100.0, "brake": 40.0, "resist": 60.0, "lift": 0.0}
    return {"type": typ, "seed": seed, "reserve": reserve, "regen": regen, "T_min": 580.0, "E_fast": 100.0, "E_a": a, "E_coast": coast, "E_dp": dp, "coast_share_dp": share, "balance_fast": bal,
            "balance_dp": bal}


RES = {"meta": {"reserves": [10.0], "types": ["flach", "wellig"], "regen_types": ["flach"], "regen_reserve": 10.0, "seeds": [100, 103]}, "rows": [
    row("flach", 100, 80.0, 70.0, 70.0), row("flach", 101, 82.0, 72.0, 71.0), row("flach", 102, 78.0, None, 69.0, share=60.0),
    row("wellig", 100, 90.0, 80.0, 60.0), row("wellig", 101, 88.0, 76.0, 60.0),
    row("flach", 100, 85.0, 80.0, 78.0, regen=True), row("flach", 101, 87.0, 82.0, 80.0, regen=True),
]}


def test_mean_se():
    m, se = R.mean_se([1, 3])
    assert m == 2 and se == pytest.approx(1.0) and R.mean_se([5])[0] == 5 and math.isnan(R.mean_se([5])[1])


def test_saving_and_gap_bases():
    r = row("flach", 1, 80.0, 70.0, 56.0)
    assert R.saving(r, "a") == pytest.approx(20.0) and R.saving(r, "dp") == pytest.approx(44.0)
    assert R.gap(r, "dp", "a") == pytest.approx(100 * (1 - 56 / 80)) and R.gap(r, "dp", "coast") == pytest.approx(20.0)


def test_summary_by_hand():
    s = R.summary(RES, "flach", 10.0)
    assert s["n"] == 3 and s["n_coast"] == 2 and s["n_dp"] == 3 and s["formula"] == pytest.approx(E.formula_saving(10.0))
    assert s["saving_a"] == pytest.approx(20.0) and s["saving_a_se"] == pytest.approx(2 / 3 ** 0.5) and s["saving_dp"] == pytest.approx(30.0)
    assert s["saving_coast"] == pytest.approx((30.0 + 28.0) / 2) and s["saving_coast_se"] == pytest.approx(1.0)                  # Mittel nur über die zwei Strecken mit Rollpunkt-Ergebnis
    assert s["dp_vs_a"] == pytest.approx((12.5 + 100 * (1 - 71 / 82) + 100 * (1 - 69 / 78)) / 3)
    assert s["dp_vs_coast"] == pytest.approx((0.0 + 100 * (1 - 71 / 72)) / 2) and s["dp_vs_coast_max"] == pytest.approx(100 * (1 - 71 / 72))
    assert s["dev_a"] == pytest.approx(E.formula_saving(10.0) - 20.0) and s["dev_dp"] == pytest.approx(E.formula_saving(10.0) - 30.0)
    assert s["E_fast"] == 100.0 and s["E_dp"] == pytest.approx((70 + 71 + 69) / 3) and s["brake_fast"] == pytest.approx(40.0) and s["coast_share"] == pytest.approx((50 + 50 + 60) / 3)


def test_summary_without_any_coast_result_gives_nan():
    res = {"meta": RES["meta"], "rows": [row("flach", 1, 80.0, None, 70.0)]}
    s = R.summary(res, "flach", 10.0)
    assert s["n_coast"] == 0 and math.isnan(s["saving_coast"]) and math.isnan(s["dp_vs_coast"]) and math.isnan(s["dp_vs_coast_max"])


def test_regen_rows_are_kept_apart():
    assert R.summary(RES, "flach", 10.0)["n"] == 3 and R.regen_summary(RES, "flach")["n"] == 2
    assert R.regen_summary(RES, "flach")["dp_vs_a"] == pytest.approx((100 * (1 - 78 / 85) + 100 * (1 - 80 / 87)) / 2)


def test_brake_share_counts_released_height_energy():
    assert R.brake_share({"traction": 100.0, "brake": 40.0, "lift": 20.0}) == pytest.approx(40.0) and R.brake_share({"traction": 100.0, "brake": 40.0, "lift": -20.0}) == pytest.approx(100 * 40 / 120)


def test_curve_returns_the_mean_saving_per_reserve():
    assert R.curve(RES, "flach", "a") == [pytest.approx(20.0)] and R.curve(RES, "flach", "coast") == [pytest.approx(29.0)] and R.curve(RES, "wellig", "dp") == [pytest.approx(60 * 0 + 40.0)]


def test_cell_exists_only_for_sweep_reserves_without_regeneration():
    base = {"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 3}
    assert R.cell_exists(base) and R.cell_exists({**base, "reserve": 2.5}) and not R.cell_exists({**base, "reserve": 7.5}) and not R.cell_exists({**base, "regen": "mit"})
    assert all(r in C.SWEEP_RESERVES for r in (2.5, 5.0, 10.0, 15.0, 20.0))


def test_load_results_reads_a_file(tmp_path):
    f = tmp_path / "res.json"
    f.write_text(json.dumps(RES), encoding="utf-8")
    assert R.load_results(f)["meta"]["types"] == ["flach", "wellig"]
