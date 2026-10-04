"""Profile: ganzzahlig erzeugt, eingefroren, und die Eigenschaften jedes Typs über viele Seeds."""
import numpy as np
import pytest

import efw_constants as C
import efw_track as TR


def test_profile_is_deterministic_and_frozen():
    a, b = TR.make_profile("flach", 3), TR.make_profile("flach", 3)
    assert np.array_equal(a["grad"], b["grad"]) and not np.array_equal(a["grad"], TR.make_profile("flach", 4)["grad"]) and not np.array_equal(a["grad"], TR.make_profile("tempolimit", 3)["grad"])
    assert a["grad"][:8].tolist() == [-0.5, -0.5, -0.5, -0.5, -0.5, -0.8, -0.8, -0.8] and a["grad"].mean() == pytest.approx(-0.28) and TR.height_profile(a)[-1] == pytest.approx(-5.6)
    w = TR.make_profile("wellig", 4)
    assert w["grad"][:8].round(2).tolist() == [-12.93, -12.93, -12.93, -12.93, -12.93, 9.98, 9.98, -1.57]
    r = TR.make_profile("rampe", 5)
    assert r["grad"].mean() == pytest.approx(2.4675) and TR.height_profile(r)[-1] == pytest.approx(49.35)
    t = TR.make_profile("tempolimit", 6)
    assert sorted(set(t["lim"].tolist())) == [20.0, 40.0] and int((t["lim"] < 40).sum()) == 11
    g = TR.make_profile("gefaelle", 7)
    assert g["grad"].mean() == pytest.approx(-7.1761, abs=1e-3) and TR.height_profile(g)[-1] == pytest.approx(-143.522, abs=0.01)


def test_unknown_type_is_rejected():
    with pytest.raises(ValueError):
        TR.make_profile("berg", 1)


def test_every_profile_has_the_standard_length_and_limit():
    for typ in C.PROFILE_TYPES:
        p = TR.make_profile(typ, 11)
        assert len(p["grad"]) == len(p["lim"]) == C.N_UNITS and p["L"] == C.LENGTH_M and p["lim"].max() == C.V_TOP and p["typ"] == typ and p["seed"] == 11


def test_flat_profiles_stay_within_one_promille_in_pieces_of_four_to_eight_units():
    for seed in range(60):
        g = TR.make_profile("flach", seed)["grad"]
        assert np.abs(g).max() <= 1.0 + 1e-9
        runs = np.split(g, np.nonzero(np.diff(g))[0] + 1)
        assert all(len(r) >= 4 for r in runs[:-1]) and all(len(r) <= 16 for r in runs)                        # aufeinanderfolgende gleiche Zufallswerte können Stücke verlängern


def test_undulating_profiles_have_zero_net_height_and_stay_in_range():
    for seed in range(60):
        g = TR.make_profile("wellig", seed)["grad"]
        assert abs(g.mean()) < 1e-9 and abs(TR.height_profile({"grad": g})[-1]) < 1e-6 and np.abs(g).max() <= 30.0


def test_a_ramp_profile_has_exactly_one_steep_stretch_of_four_to_eight_units():
    for seed in range(60):
        g = TR.make_profile("rampe", seed)["grad"]
        steep = g >= 14.9
        n = int(steep.sum())
        idx = np.nonzero(steep)[0]
        assert 4 <= n <= 8 and idx.max() - idx.min() + 1 == n and g[steep].max() <= 25.0 + 1e-9 and idx.min() >= 6


def test_speed_limit_zones_have_one_or_two_zones_of_four_to_ten_units_with_the_standard_limits():
    counts = set()
    for seed in range(80):
        lim = TR.make_profile("tempolimit", seed)["lim"]
        low = lim < C.V_TOP
        counts.add(len(np.split(np.nonzero(low)[0], np.nonzero(np.diff(np.nonzero(low)[0]) > 1)[0] + 1)))
        assert low.sum() >= 4 and set(lim[low].tolist()) <= {20.0, 25.0, 30.0} and low[:2].sum() == 0 and low[-2:].sum() == 0
    assert counts >= {1, 2}


def test_descent_profiles_lose_height_on_average():
    means = [TR.make_profile("gefaelle", s)["grad"].mean() for s in range(60)]
    assert -8.5 < np.mean(means) < -4.5 and max(means) < 0


def test_the_approximate_normal_has_the_right_moments():
    from efw_rng import SplitMix64
    rng = SplitMix64(5)
    xs = np.array([TR._normal(rng, 0.0, 1.0, -10, 10) for _ in range(8000)])
    assert abs(xs.mean()) < 0.05 and abs(xs.std() - 1.0) < 0.05 and xs.max() < 5
    assert TR._normal(SplitMix64(1), 100.0, 1.0, -3.0, 3.0) == 3.0 and TR._normal(SplitMix64(1), -100.0, 1.0, -3.0, 3.0) == -3.0
    u = [TR._uniform(SplitMix64(s), -10, 10) for s in range(300)]
    assert min(u) >= -1.0 and max(u) <= 1.0 and len(set(u)) > 15


def test_height_profile_accumulates_gradient_times_length():
    assert TR.height_profile({"grad": np.array([10.0, -10.0, 20.0])}).tolist() == [0.0, 5.0, 0.0, 10.0]
