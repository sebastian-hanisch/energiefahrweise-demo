"""Preset-Kriterien: jedes Kriterium kippt einzeln an seiner Schwelle (künstliche Zahlen), und `facts_for` liest die richtigen Größen."""
import math

import pytest

import efw_constants as C
import efw_evaluation as E
import efw_results as R
import efw_stories as S

BASE = dict(s_naive=14.0, s_coast=28.0, s_dp=38.0, formula=17.4, dp_vs_coast=8.0, dp_vs_a=26.0, ref_dp_vs_a=26.0, brake_fast=58.0, coast_ok=True, regen=False, sweep_dev_dp=-18.0,
            sweep_dp_vs_coast=4.8, sweep_dp_vs_a=25.0, sweep_s_naive=14.0, sweep_regen_dp_vs_a=12.8)

GOOD = {
    "Standard": {},
    "Flache Strecke": dict(s_naive=18.5, s_coast=32.0, s_dp=31.8, dp_vs_coast=-0.4, sweep_dp_vs_coast=-0.4),
    "Rampe": dict(s_naive=14.4, s_coast=25.5, s_dp=25.5, dp_vs_coast=0.0, sweep_dp_vs_coast=0.0),
    "Tempolimit": dict(s_naive=36.7, dp_vs_coast=10.5, sweep_s_naive=36.7, sweep_dp_vs_coast=10.5),
    "Starkes Gefälle": dict(s_dp=58.0, dp_vs_coast=37.0, sweep_dp_vs_coast=37.0),
    "Mit Rückspeisung": dict(regen=True, dp_vs_a=8.0, ref_dp_vs_a=15.7, sweep_dp_vs_a=15.7, sweep_regen_dp_vs_a=8.0),
}

BREAK = {
    "Standard": {"naive_close": dict(s_naive=24.0, s_coast=40.0), "dp_far": dict(s_dp=25.0), "coast_better": dict(s_coast=20.0), "dp_beats_coast": dict(dp_vs_coast=2.9),
                 "brake": dict(brake_fast=39.0), "sweep_dp_far": dict(sweep_dev_dp=-9.9), "sweep_beats": dict(sweep_dp_vs_coast=2.9)},
    "Flache Strecke": {"tie": dict(dp_vs_coast=1.0), "coast_saves": dict(s_coast=24.9), "naive_close": dict(s_naive=22.0), "sweep_tie": dict(sweep_dp_vs_coast=1.0)},
    "Rampe": {"tie": dict(dp_vs_coast=-1.0), "coast_better": dict(s_coast=18.0), "sweep_tie": dict(sweep_dp_vs_coast=-1.5)},
    "Tempolimit": {"naive_beats_formula": dict(s_naive=20.0), "dp_beats_coast": dict(dp_vs_coast=4.9), "sweep_naive": dict(sweep_s_naive=27.0), "sweep_beats": dict(sweep_dp_vs_coast=7.9)},
    "Starkes Gefälle": {"coast_ok": dict(coast_ok=False), "dp_saves": dict(s_dp=49.0), "dp_beats_coast": dict(dp_vs_coast=14.9), "sweep_beats": dict(sweep_dp_vs_coast=24.9)},
    "Mit Rückspeisung": {"regen": dict(regen=False), "halved": dict(dp_vs_a=11.0), "still_positive": dict(dp_vs_a=2.9), "sweep_halved": dict(sweep_regen_dp_vs_a=11.1)},
}


def facts(preset, **over):
    return {**BASE, **GOOD[preset], **over}


def failing(preset, **over):
    return [cid for cid, _, ok in S.check(preset, facts(preset, **over)) if not ok]


def test_every_preset_has_criteria_and_breakers_for_each_of_them():
    assert set(S.CRITERIA) == set(C.PRESET_ORDER) == set(GOOD) == set(BREAK)
    for name in C.PRESET_ORDER:
        assert {cid for cid, _, _ in S.CRITERIA[name]} == set(BREAK[name]), name


@pytest.mark.parametrize("preset", C.PRESET_ORDER)
def test_good_facts_pass_every_criterion(preset):
    assert failing(preset) == []


@pytest.mark.parametrize("preset,cid", [(p, c) for p in C.PRESET_ORDER for c in BREAK[p]])
def test_each_criterion_flips_alone(preset, cid):
    assert failing(preset, **BREAK[preset][cid]) == [cid]


def test_thresholds_are_exact():
    assert failing("Standard", formula=20.0, s_naive=26.0, s_dp=30.0, s_coast=40.0) == [] and failing("Standard", formula=20.0, s_naive=26.0, s_dp=29.9, s_coast=40.0) == ["dp_far"]
    assert failing("Standard", s_naive=23.4, s_coast=40.0) == [] and failing("Standard", s_naive=23.5, s_coast=40.0) == ["naive_close"]
    assert failing("Standard", s_coast=22.0) == [] and failing("Standard", s_coast=21.9) == ["coast_better"] and failing("Standard", dp_vs_coast=3.0) == [] and failing("Standard", brake_fast=40.0) == []
    assert failing("Standard", sweep_dev_dp=-10.0) == [] and failing("Standard", sweep_dp_vs_coast=3.0) == []
    assert failing("Flache Strecke", s_coast=25.0) == [] and failing("Flache Strecke", dp_vs_coast=0.99) == [] and failing("Flache Strecke", dp_vs_coast=-0.99) == [] and failing("Flache Strecke", s_naive=20.4) == []
    assert failing("Rampe", s_coast=19.5) == [] and failing("Rampe", s_coast=19.3) == ["coast_better"] and failing("Rampe", dp_vs_coast=-0.99) == []
    assert failing("Tempolimit", s_naive=20.4, formula=17.4) == [] and failing("Tempolimit", dp_vs_coast=5.0) == [] and failing("Tempolimit", sweep_s_naive=27.4) == [] and failing("Tempolimit", sweep_dp_vs_coast=8.0) == []
    assert failing("Starkes Gefälle", s_dp=50.0) == [] and failing("Starkes Gefälle", dp_vs_coast=15.0) == [] and failing("Starkes Gefälle", sweep_dp_vs_coast=25.0) == []
    assert failing("Mit Rückspeisung", dp_vs_a=10.98) == [] and failing("Mit Rückspeisung", dp_vs_a=3.0) == [] and failing("Mit Rückspeisung", sweep_regen_dp_vs_a=10.98) == []


def test_missing_sweep_values_fail_the_sweep_criteria():
    nan = float("nan")
    assert failing("Standard", sweep_dev_dp=nan, sweep_dp_vs_coast=nan) == ["sweep_dp_far", "sweep_beats"] and failing("Mit Rückspeisung", sweep_regen_dp_vs_a=nan) == ["sweep_halved"]


def test_facts_for_reads_the_live_run_and_the_sweep():
    res = R.load_results()
    settings = {"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 500}
    run = E.run_live(settings)
    f = S.facts_for(run, run, res, settings)
    assert f["s_naive"] == pytest.approx(E.saving_pct(run, "naive")) and f["s_dp"] == pytest.approx(E.saving_pct(run, "dp")) and f["formula"] == pytest.approx(E.formula_saving(10.0))
    assert f["dp_vs_coast"] == pytest.approx(E.dp_vs_pct(run, "coast")) and f["dp_vs_a"] == f["ref_dp_vs_a"] and f["coast_ok"] is True and f["regen"] is False
    assert f["brake_fast"] == pytest.approx(E.brake_share_pct(run["results"]["fast"]))
    s = R.summary(res, "wellig", 10.0)
    assert f["sweep_dev_dp"] == s["dev_dp"] and f["sweep_dp_vs_coast"] == s["dp_vs_coast"] and f["sweep_s_naive"] == s["saving_a"] and f["sweep_dp_vs_a"] == s["dp_vs_a"]
    assert f["sweep_regen_dp_vs_a"] == R.regen_summary(res, "wellig")["dp_vs_a"]


def test_facts_for_without_a_regeneration_sweep_uses_nan():
    res = R.load_results()
    settings = {"reserve": 10.0, "profile": "rampe", "regen": "aus", "seed": 500}
    run = E.run_live(settings)
    assert math.isnan(S.facts_for(run, run, res, settings)["sweep_regen_dp_vs_a"])


def test_facts_for_a_regeneration_preset_compares_with_the_run_without():
    res = R.load_results()
    settings = {"reserve": 10.0, "profile": "flach", "regen": "mit", "seed": 500}
    run = E.run_live(settings)
    ref = E.run_live({**settings, "regen": "aus"})
    f = S.facts_for(run, ref, res, settings)
    assert f["regen"] is True and f["dp_vs_a"] == pytest.approx(E.dp_vs_pct(run, "naive")) and f["ref_dp_vs_a"] == pytest.approx(E.dp_vs_pct(ref, "naive")) and f["dp_vs_a"] < f["ref_dp_vs_a"]
