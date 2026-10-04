"""Dynamische Programmierung: gegen Vollaufzählung auf einer winzigen Strecke, Eigenschaften auf einer echten Strecke, unabhängiger Nachfahrer."""
import itertools

import numpy as np
import pytest

import efw_dp as D
import efw_physics as PH
import efw_strategies as S
import efw_track as TR

TINY = {"grad": np.zeros(8), "lim": np.full(8, 25.0), "L": 4000.0}


def brute_force(lam, dv=5.0, dx=500.0):
    """Kleinster Wert von Energie + lam * Zeit über ALLE Geschwindigkeitsfolgen auf dem Raster (Start und Ziel stehen), unabhängig vom DP-Code."""
    speeds = np.arange(1, 6) * dv
    best = None
    for mid in itertools.product(speeds, repeat=7):
        v = np.array((0.0,) + mid + (0.0,))
        E, dt, _F, feas = PH.trans(v[:-1], v[1:], 0.0, 25.0, dx)
        if not feas.all():
            continue
        val = float(E.sum() + lam * dt.sum())
        if best is None or val < best[0]:
            best = (val, float(E.sum()), float(dt.sum()))
    return best


@pytest.fixture(scope="module")
def tiny():
    return D.DP(TINY, dx=500.0, dv=5.0, modes=())


@pytest.fixture(scope="module")
def real():
    prof = TR.make_profile("wellig", 4)
    return prof, D.DP(prof)


@pytest.mark.parametrize("lam", [0.3, 1.5, 8.0])
def test_value_function_equals_the_enumeration_of_all_speed_sequences_on_a_tiny_track(tiny, lam):
    best = brute_force(lam)
    assert tiny.backward(lam)[0, 0] == pytest.approx(best[0], abs=2e-3)
    r = tiny.trace(lam)
    assert r["ok"] and r["E"] + lam * r["T"] == pytest.approx(best[0], abs=2e-3) and r["E"] == pytest.approx(best[1], abs=2e-3) and r["T"] == pytest.approx(best[2], abs=2e-3)


def test_free_target_modes_never_make_the_tiny_track_worse():
    full = D.DP(TINY, dx=500.0, dv=5.0)
    raster = D.DP(TINY, dx=500.0, dv=5.0, modes=())
    for lam in (0.5, 3.0):
        assert full.backward(lam)[0, 0] <= raster.backward(lam)[0, 0] + 1e-6


def test_tiny_track_states_are_the_expected_raster(tiny):
    assert tiny.N == 8 and tiny.nv == 6 and tiny.vg.tolist() == [0, 5, 10, 15, 20, 25] and tiny.allowed[0].tolist() == [True] + [False] * 5 and tiny.allowed[8].tolist() == [True] + [False] * 5
    assert tiny.allowed[3].tolist() == [False] + [True] * 5


def test_speed_limit_cells_restrict_the_raster():
    prof = {"grad": np.zeros(4), "lim": np.array([25.0, 15.0, 15.0, 25.0]), "L": 2000.0}
    dp = D.DP(prof, dx=500.0, dv=5.0, modes=())
    assert dp.nl.tolist() == [0, 15, 15, 15, 0] or dp.nl.tolist() == [0.0, 15.0, 15.0, 15.0, 0.0]
    assert not dp.allowed[2, 4] and dp.allowed[2, 3]                                                      # an der Grenze zwischen zwei 15-m/s-Zellen sind 20 m/s verboten


def test_a_larger_time_weight_gives_a_faster_and_more_expensive_trip(real):
    prof, dp = real
    rs = [dp.trace(lam) for lam in (0.5, 3.0, 30.0, 300.0)]
    assert all(r["ok"] for r in rs)
    assert all(a["T"] >= b["T"] - 1e-6 for a, b in zip(rs, rs[1:])) and all(a["E"] <= b["E"] + 1e-6 for a, b in zip(rs, rs[1:]))


def test_the_fastest_trace_agrees_with_the_independent_simulator(real):
    prof, dp = real
    T_fb, _E_fb = S.FB(prof).fastest()
    assert dp.fastest()["T"] == pytest.approx(T_fb, rel=0.003)


def test_budget_is_met_and_energy_falls_convexly_with_more_time(real):
    prof, dp = real
    Tmin = S.FB(prof).fastest()[0]
    sols = [dp.solve_budget(Tmin * (1 + r)) for r in (0.05, 0.10, 0.15, 0.20)]
    for r, s in zip((0.05, 0.10, 0.15, 0.20), sols):
        assert not s["infeasible"] and s["T"] <= Tmin * (1 + r) and s["T"] >= Tmin * (1 + r) - 3.0
    E = [s["E"] for s in sols]
    assert all(a > b for a, b in zip(E, E[1:])) and all(E[i] - 2 * E[i + 1] + E[i + 2] > -0.02 * E[0] for i in range(2))     # fallend und (innerhalb der Rasterstreuung) konvex


def test_an_unreachable_budget_is_reported_as_infeasible(real):
    prof, dp = real
    assert dp.solve_budget(0.8 * S.FB(prof).fastest()[0])["infeasible"] is True


def test_the_trace_is_a_valid_trip_per_the_independent_replay(real):
    prof, dp = real
    Tmin = S.FB(prof).fastest()[0]
    s = dp.solve_budget(1.10 * Tmin)
    G, _lim = TR.cell_arrays(prof, dp.dx)
    r = PH.replay(G, dp.dx, s["v"], s["F"], s["kind"])
    assert abs(r["T"] - s["T"]) < 0.5 and abs(r["E"] - s["E"]) / s["E"] < 0.005 and abs(r["vend"]) < 0.05 and r["maxdec"] <= 0.7 + 1e-6 and r["maxdev"] < 0.05


def test_trace_kinds_and_forces_are_consistent(real):
    prof, dp = real
    s = dp.solve_budget(1.10 * S.FB(prof).fastest()[0])
    assert set(np.unique(s["kind"]).tolist()) <= {D.KIND_DRIVE, D.KIND_BRAKE, D.KIND_COAST}
    assert (s["F"][s["kind"] == D.KIND_COAST] == 0).all() and (s["F"][s["kind"] == D.KIND_BRAKE] <= 0).all()
    assert s["v"][0] == 0 and s["v"][-1] == 0 and (s["v"] <= 40.0 + 1e-9).all() and s["fails"] == 0


def test_coasting_is_what_saves_energy_on_a_flat_track():
    prof = TR.make_profile("flach", 3)
    fb = S.FB(prof)
    Tb = 1.10 * fb.fastest()[0]
    opt = D.DP(prof).solve_budget(Tb)
    slower = fb.strategy_a(Tb)
    assert opt["E"] < 0.9 * slower["E"] and (opt["kind"] == D.KIND_COAST).sum() > 20                      # das Optimum rollt auf mehr als 20 von 80 Zellen und spart über 10 % gegen Langsamfahren


def test_each_special_mode_set_changes_the_result():
    prof = TR.make_profile("wellig", 4)
    Tb = 1.10 * S.FB(prof).fastest()[0]
    full = D.DP(prof).solve_budget(Tb)["E"]
    raster_only = D.DP(prof, modes=()).solve_budget(Tb)["E"]
    no_coast = D.DP(prof, modes=("full", "brake")).solve_budget(Tb)["E"]
    assert raster_only != full and no_coast != full and abs(raster_only - full) > 0.001 and full <= no_coast + 1.0                    # mehr Übergänge: nie nennenswert schlechter


def test_regeneration_lowers_the_energy_of_the_optimum():
    prof = TR.make_profile("flach", 3)
    Tb = 1.10 * S.FB(prof).fastest()[0]
    assert D.DP(prof, eta=0.6).solve_budget(Tb)["E"] < D.DP(prof).solve_budget(Tb)["E"]
