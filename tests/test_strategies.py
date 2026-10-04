"""Vergleichsverfahren: Vorwärts-Rückwärts-Simulator, gleichmäßig langsamer und Rollpunkt-Regel."""
import math

import numpy as np
import pytest

import efw_constants as C
import efw_evaluation as E
import efw_strategies as S
import efw_track as TR

FLAT = {"typ": "flach", "seed": 0, "grad": np.zeros(40), "lim": np.full(40, 40.0), "L": 20000.0}


@pytest.fixture(scope="module")
def flat_fb():
    return S.FB(FLAT)


@pytest.fixture(scope="module")
def hilly_fb():
    return S.FB(TR.make_profile("wellig", 4))


def test_the_fastest_trip_by_hand_on_a_flat_track(flat_fb):
    T, E_, prof = flat_fb.run(40.0, None, want_profile=True)
    v = prof["v"]
    assert v[0] == 0 and v[-1] == 0 and v.max() == pytest.approx(40.0, abs=1e-6)                            # erreicht das Höchsttempo
    assert (v[-23:-1] ** 2 - v[-22:] ** 2).max() == pytest.approx(2 * 0.7 * 50, abs=0.5)                      # Bremsweg 1143 m: die letzten Zellen verzögern mit der Grenze 0,7 m/s²
    assert 560 < T < 600 and 600 < E_ < 640 and prof["nbad"] == 0


def test_lower_cruising_speed_means_a_longer_cheaper_trip(flat_fb):
    runs = [flat_fb.run(v) for v in (40.0, 35.0, 30.0, 25.0)]
    assert all(a[0] < b[0] for a, b in zip(runs, runs[1:])) and all(a[1] > b[1] for a, b in zip(runs, runs[1:]))


def test_a_coast_point_lowers_energy_and_lengthens_the_trip(flat_fb):
    no = flat_fb.run(40.0)
    early = flat_fb.run(40.0, 8000.0)
    late = flat_fb.run(40.0, 16000.0)
    assert no[1] > late[1] > early[1] and no[0] < late[0] < early[0]


def test_coasting_from_the_start_stops_the_train(flat_fb):
    assert flat_fb.run(40.0, 0.0) == (math.inf, math.inf)
    assert flat_fb.run(40.0, 0.0, want_profile=True) == (math.inf, math.inf, None)


def test_the_speed_limit_caps_the_trip():
    lim = np.full(40, 40.0)
    lim[10:20] = 20.0
    fb = S.FB({"grad": np.zeros(40), "lim": lim, "L": 20000.0})
    _, _, prof = fb.run(40.0, None, want_profile=True)
    assert prof["v"][fb.n // 4 + 2:fb.n // 2 - 2].max() <= 20.0 + 1e-6


def test_energy_balance_holds_on_the_simulated_trip(hilly_fb):
    for xc in (None, 6000.0):
        T, E_, prof = hilly_fb.run(36.0, xc, want_profile=True)
        b = E.balance(hilly_fb.prof, hilly_fb.h, prof["v"], prof["F"])
        assert b["traction"] - b["brake"] == pytest.approx(b["resist"] + b["lift"], abs=1e-6) and b["traction"] == pytest.approx(E_, abs=1e-6)


def test_strategy_a_meets_the_budget_and_gets_cheaper_with_more_time(flat_fb):
    T0 = flat_fb.fastest()[0]
    a = [flat_fb.strategy_a(T0 * (1 + r)) for r in (0.05, 0.10, 0.20)]
    for r, s in zip((0.05, 0.10, 0.20), a):
        assert s["T"] <= T0 * (1 + r) and s["T"] >= T0 * (1 + r) - 1.0
    assert a[0]["vcap"] > a[1]["vcap"] > a[2]["vcap"] and a[0]["E"] > a[1]["E"] > a[2]["E"]


def test_strategy_a_returns_the_fastest_trip_if_the_budget_is_not_longer(flat_fb):
    T0, E0 = flat_fb.fastest()
    s = flat_fb.strategy_a(T0 * 0.9)
    assert s["vcap"] == 40.0 and s["T"] == T0 and s["E"] == E0


def test_the_coast_point_hits_the_budget_and_beats_slow_driving(flat_fb):
    T0 = flat_fb.fastest()[0]
    Tb = 1.10 * T0
    a = flat_fb.strategy_a(Tb)
    b1, b2 = flat_fb.strategy_b(Tb, a["vcap"])
    assert b1 is not None and abs(b1["T"] - Tb) < 2.0 and b1["E"] < 0.9 * a["E"]
    assert abs(b2["T"] - Tb) < 2.0 and b2["E"] <= b1["E"] + 1e-9 and b2["xc"] % flat_fb.h == 0 and 0 < b2["xc"] < 20000


def test_unreachable_budgets_return_none(flat_fb):
    T0 = flat_fb.fastest()[0]
    assert flat_fb.coast_point(40.0, 0.9 * T0) is None                                                       # schon ohne Rollen zu langsam
    assert flat_fb.coast_point(40.0, 30.0 * T0) is None                                                      # selbst sofortiges Rollen reicht nicht (der Zug bleibt stehen)


def test_the_reach_point_exists_for_reachable_speeds_and_not_for_unreachable_ones():
    lim = np.full(40, 40.0)
    fb = S.FB({"grad": np.zeros(40), "lim": lim, "L": 20000.0})
    assert fb._x_reach(30.0) is not None and fb._x_reach(30.0) < fb.n
    fb2 = S.FB({"grad": np.full(40, 30.0), "lim": lim, "L": 20000.0})
    assert fb2._x_reach(40.0) is None                                                                        # an einer 30-‰-Rampe erreicht der Zug 144 km/h nie


def test_the_independent_simulator_and_the_budget_use_one_clock(hilly_fb):
    r = E.run_live({"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 4})
    assert r["T_min"] == pytest.approx(S.FB(hilly_fb.prof).fastest()[0]) and r["T_budget"] == pytest.approx(1.1 * r["T_min"]) and C.FB_H == 50.0
