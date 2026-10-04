"""Live-Rechnung, Energiebilanz und Meldungen: eingefrorene Werte, Eigenschaften jedes Laufs, Meldungen an ihren Schwellen mit künstlichen Zahlen."""
import numpy as np
import pytest

import efw_constants as C
import efw_dp as D
import efw_evaluation as E
import efw_physics as PH
import efw_strategies as S

STD = {"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 500}
FLAT = {"reserve": 10.0, "profile": "flach", "regen": "aus", "seed": 500}


def entry(Ev, brake=100.0, traction=200.0, lift=0.0, coast=20, n=80):
    return {"E": Ev, "T": 600.0, "x": [250.0 * k for k in range(n + 1)], "v": [0.0] * (n + 1), "phase": ["coast"] * coast + ["drive"] * (n - coast), "F": [0.0] * n,
            "balance": {"traction": traction, "brake": brake, "resist": traction - brake - lift, "lift": lift}, "dx": 250.0, "eta": 0.0}


def fake(fast=600.0, naive=500.0, coast=420.0, dp=400.0, reserve=10.0, coast_ok=True, dp_ok=True):
    return {"reserve": reserve, "eta": 0.0, "T_min": 580.0, "T_budget": 638.0, "coast_ok": coast_ok, "dp_ok": dp_ok, "formula_E": fast / (1 + reserve / 100) ** 2,
            "results": {"fast": entry(fast, brake=300.0, traction=600.0), "naive": entry(naive), "coast": entry(coast), "dp": entry(dp)}}


def test_formula_saving_by_hand():
    assert E.formula_saving(0.0) == 0.0 and E.formula_saving(10.0) == pytest.approx(100 * (1 - 1 / 1.21)) and E.formula_saving(20.0) == pytest.approx(100 * (1 - 1 / 1.44))
    assert E.formula_saving(2.5) == pytest.approx(4.8185, abs=1e-3)


def test_phase_classification():
    assert E.phases_from_force([100e3, 400.0, 0.0, -400.0, -501.0, -1e5, 500.0]) == ["drive", "coast", "coast", "coast", "brake", "brake", "coast"]
    assert E.phases_from_kind([0, 1, 2, 0]) == ["drive", "brake", "coast", "drive"]


def test_energy_balance_by_hand():
    prof = {"grad": np.zeros(3), "lim": np.full(3, 40.0), "L": 1500.0}
    v = np.array([0.0, 10.0, 10.0, 0.0])
    F = np.array([100e3, 0.0, -50e3])
    b = E.balance(prof, 500.0, v, F)
    assert b["traction"] == pytest.approx(100e3 * 500 / 1e6) and b["brake"] == pytest.approx(50e3 * 500 / 1e6) and b["lift"] == pytest.approx(0.0, abs=1e-9)
    expected = sum(float(PH.resist(a, c)) for a, c in ((0.0, 10.0), (10.0, 10.0), (10.0, 0.0))) * 500 / 1e6
    assert b["resist"] == pytest.approx(expected)
    hill = {"grad": np.full(3, 10.0), "lim": np.full(3, 40.0), "L": 1500.0}
    assert E.balance(hill, 500.0, v, F)["lift"] == pytest.approx(3 * 500 * 39238.0 / 1e6, rel=1e-3)


def test_brake_share_counts_released_height_energy_as_supply():
    assert E.brake_share_pct(entry(100.0, brake=40.0, traction=100.0, lift=20.0)) == pytest.approx(40.0)              # bergauf: nur die Traktion zählt
    assert E.brake_share_pct(entry(100.0, brake=40.0, traction=100.0, lift=-20.0)) == pytest.approx(100 * 40 / 120)   # bergab: Lageenergie kommt dazu
    assert np.isnan(E.brake_share_pct(entry(100.0, brake=0.0, traction=0.0)))


def test_savings_use_the_stated_bases():
    run = fake(fast=600.0, naive=480.0, coast=360.0, dp=300.0)
    assert E.saving_pct(run, "naive") == pytest.approx(20.0) and E.saving_pct(run, "dp") == pytest.approx(50.0) and E.saving_pct(run, "fast") == 0.0
    assert E.dp_vs_pct(run, "coast") == pytest.approx(100 * (1 - 300 / 360)) and E.dp_vs_pct(run, "naive") == pytest.approx(37.5)
    assert E.coast_share_pct(entry(1.0, coast=20)) == pytest.approx(25.0)


def test_standard_runs_are_frozen():
    flat = E.run_live(FLAT)
    r = flat["results"]
    assert all(abs(a - b) < 1.0 for a, b in zip([r[k]["E"] for k in C.METHODS], [629.0, 511.7, 427.6, 428.2]))
    assert flat["T_min"] == pytest.approx(582.4, abs=0.2) and flat["T_budget"] == pytest.approx(1.1 * flat["T_min"]) and E.brake_share_pct(r["fast"]) == pytest.approx(51.8, abs=0.3)
    hilly = E.run_live(STD)
    h = hilly["results"]
    assert all(abs(a - b) < 1.0 for a, b in zip([h[k]["E"] for k in C.METHODS], [835.8, 722.8, 598.3, 515.3]))
    assert flat["coast_ok"] and flat["dp_ok"] and hilly["coast_ok"] and hilly["dp_ok"] and hilly["formula_E"] == pytest.approx(835.8 / 1.21, abs=1.0)


def test_every_trip_meets_the_budget_and_the_arrays_are_consistent():
    run = E.run_live(STD)
    for key in C.METHODS:
        e = run["results"][key]
        assert len(e["x"]) == len(e["v"]) == len(e["F"]) + 1 == len(e["phase"]) + 1 and e["x"][0] == 0 and e["x"][-1] == pytest.approx(C.LENGTH_M) and e["v"][0] == 0 == e["v"][-1]
        if key != "fast":
            assert e["T"] <= run["T_budget"] + 1e-6 and e["T"] >= run["T_budget"] - 3.0
        b = e["balance"]
        assert b["traction"] - b["brake"] == pytest.approx(b["resist"] + b["lift"], abs=1e-3)
    assert run["results"]["fast"]["E"] > run["results"]["naive"]["E"] > run["results"]["coast"]["E"] > run["results"]["dp"]["E"]
    assert run["results"]["naive"]["vcap"] < C.V_TOP and 0 < run["results"]["coast"]["xc"] < C.LENGTH_M


def test_every_setting_changes_the_run():
    ref = E.run_live(FLAT)
    snap = {k: round(v["E"], 4) for k, v in ref["results"].items()}
    for change in ({"reserve": 5.0}, {"profile": "rampe"}, {"regen": "mit"}, {"seed": 501}):
        other = E.run_live({**FLAT, **change})
        assert {k: round(v["E"], 4) for k, v in other["results"].items()} != snap, change


def test_regeneration_credits_braking_in_every_method():
    a, b = E.run_live(FLAT), E.run_live({**FLAT, "regen": "mit"})
    assert b["eta"] == C.REGEN_ETA and a["eta"] == 0.0
    for key in C.METHODS:
        assert b["results"][key]["E"] < a["results"][key]["E"]
    assert E.dp_vs_pct(b, "naive") < 0.7 * E.dp_vs_pct(a, "naive")


def test_the_coast_rule_falls_back_to_slow_driving_if_the_budget_is_unreachable(monkeypatch):
    monkeypatch.setattr(S.FB, "strategy_b", lambda self, Tb, a_vcap, **kw: (None, None))
    run = E.run_live(FLAT)
    assert not run["coast_ok"] and run["results"]["coast"]["E"] == run["results"]["naive"]["E"]
    assert any(s == "warning" and "Rollpunkt-Regel erreicht das Fahrzeitbudget" in t for s, t in E.messages(run, FLAT))


def test_the_optimum_falls_back_to_the_coast_rule_if_the_dp_finds_nothing(monkeypatch):
    monkeypatch.setattr(D.DP, "solve_budget", lambda self, Tb, iters=0: {"infeasible": True})
    run = E.run_live(FLAT)
    assert not run["dp_ok"] and run["results"]["dp"]["E"] == run["results"]["coast"]["E"]
    assert any(s == "warning" and "keine zulässige Fahrt" in t for s, t in E.messages(run, FLAT))


def texts(run, **over):
    return E.messages(run, {**STD, **over})


def test_main_message_names_the_formula_and_the_brake_loss():
    state, text = texts(fake(fast=600.0, naive=500.0, coast=420.0, dp=300.0))[0]
    assert state == "success" and "gleichmäßiges Langsamfahren 17 %" in text and "v²-Formel sagt 17 % voraus" in text and "Rollpunkt-Regel 30 %" in text and "Optimum 50 %" in text
    assert "50 % der Traktionsenergie" in text
    assert texts(fake(fast=600.0, naive=500.0, coast=420.0, dp=438.0))[0][0] == "success" and texts(fake(fast=600.0, naive=500.0, coast=420.0, dp=442.0))[0][0] == "info"      # Schwelle: 10 Punkte über gleichmäßig langsamer (16,7 %)


def test_gap_message_has_three_cases():
    tie = texts(fake(coast=400.0, dp=400.0))[1]
    assert tie[0] == "info" and "genügt die einfache Rollpunkt-Regel" in tie[1] and "+0.0 %" in tie[1]
    assert texts(fake(coast=400.0, dp=396.0))[1][1].startswith("Das Optimum braucht 1 % weniger") and texts(fake(coast=400.0, dp=398.0))[1][1].startswith("Hier genügt")                # Schwelle 1 %
    mid, big = texts(fake(coast=420.0, dp=400.0))[1], texts(fake(coast=420.0, dp=380.0))[1]
    assert mid[0] == "info" and "5 % weniger" in mid[1] and big[0] == "success" and "10 % weniger" in big[1]
    worse = texts(fake(coast=400.0, dp=410.0))[1]
    assert worse[0] == "info" and worse[1].startswith("Hier ist die Rollpunkt-Regel sogar 2.5 % besser als die DP") and texts(fake(coast=400.0, dp=403.9))[1][1].startswith("Hier genügt")          # -1 %: Schwelle


def test_regeneration_and_warning_messages():
    assert any("Mit Rückspeisung (60 %)" in t for _, t in texts(fake(), regen="mit")) and not any("Rückspeisung" in t for _, t in texts(fake()))
    assert not any(s == "warning" for s, _ in texts(fake()))
    assert any(s == "warning" and "Rollpunkt-Regel erreicht" in t for s, t in texts(fake(coast_ok=False)))
    assert any(s == "warning" and "keine zulässige Fahrt" in t for s, t in texts(fake(dp_ok=False)))
