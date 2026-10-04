"""Zugphysik von Hand gerechnet: Widerstand, Übergang je Zelle, Sondersteuerungen, Interpolation und der RK4-Nachfahrer."""
import numpy as np
import pytest

import efw_constants as C
import efw_physics as PH
import efw_track as TR

MEFF = C.MASS * C.ROT


def test_resistance_at_constant_speed_is_the_davis_formula():
    assert PH.resist(20.0, 20.0) == pytest.approx(4000 + 60 * 20 + 6 * 400)                       # 7600 N
    assert PH.resist(0.0, 0.0) == pytest.approx(4000.0)


def test_cruising_cell_by_hand():
    E, dt, F, feas = PH.trans(20.0, 20.0, 0.0, 40.0, 500.0)
    assert F == pytest.approx(7600.0) and E == pytest.approx(7600 * 500 / 1e6) and dt == pytest.approx(25.0) and bool(feas)


def test_accelerating_cell_by_hand():
    E, dt, F, feas = PH.trans(10.0, 12.0, 0.0, 40.0, 100.0)
    a = (144 - 100) / 200
    vm = np.sqrt(122.0)
    r = 4000 + 60 * (10 + 4 * vm + 12) / 6 + 6 * 122
    assert F == pytest.approx(MEFF * a + r) and E == pytest.approx((MEFF * a + r) * 100 / 1e6) and dt == pytest.approx(200 / 22) and bool(feas)
    assert float(E) == pytest.approx(9.8674, abs=1e-3)


def test_braking_cell_costs_nothing_and_regeneration_credits_a_share():
    E, dt, F, feas = PH.trans(20.0, 19.5, 0.0, 40.0, 100.0)
    assert F < 0 and E == 0.0 and bool(feas)
    E2, _, F2, _ = PH.trans(20.0, 19.5, 0.0, 40.0, 100.0, eta=0.6)
    assert F2 == F and E2 == pytest.approx(0.6 * F * 100 / 1e6) and E2 < 0                          # Gutschrift: negative Energie


def test_grade_force_from_promille():
    G, lim = TR.cell_arrays({"grad": np.array([10.0, -10.0]), "lim": np.array([40.0, 30.0])}, 500.0)
    assert G[0] == pytest.approx(C.MASS * C.G_ACC * np.sin(np.arctan(0.01))) and G[0] == pytest.approx(39238.0, abs=1.0) and G[1] == pytest.approx(-G[0])
    assert list(lim) == [40.0, 30.0]
    G2, lim2 = TR.cell_arrays({"grad": np.array([10.0]), "lim": np.array([25.0])}, 250.0)
    assert len(G2) == 2 and list(lim2) == [25.0, 25.0] and G2[0] == G2[1]
    with pytest.raises(ValueError):
        TR.cell_arrays({"grad": np.array([0.0]), "lim": np.array([40.0])}, 300.0)


def test_a_climb_needs_more_force():
    G = C.MASS * C.G_ACC * np.sin(np.arctan(0.01))
    E0, _, F0, _ = PH.trans(20.0, 20.0, 0.0, 40.0, 500.0)
    E1, _, F1, _ = PH.trans(20.0, 20.0, G, 40.0, 500.0)
    assert F1 == pytest.approx(F0 + G) and E1 > E0


@pytest.mark.parametrize("vi,vj,dx,G,lim,why", [(20.0, 10.0, 100.0, 0.0, 40.0, "Verzögerung über 0,7 m/s²"), (1.0, 10.0, 10.0, 0.0, 40.0, "Zugkraft über der Grenze"),
                                                (20.0, 31.0, 5000.0, 0.0, 30.0, "Tempolimit überschritten"), (np.float64(0.0), np.float64(0.0), 100.0, 0.0, 40.0, "Stillstand ohne Bewegung")])
def test_infeasible_cells_are_marked(vi, vj, dx, G, lim, why):
    assert not bool(PH.trans(vi, vj, G, lim, dx)[3]), why


def test_special_steps_by_hand():
    (Ec, dtc, vjc, fc), (Ef, dtf, vjf, ff), (Eb, dtb, vjb, fb) = PH.special_steps(np.array(30.0), 0.0, 40.0, 100.0, 0.1)
    assert Ec == 0.0 and vjc == pytest.approx(29.912, abs=0.01) and vjc < 30 and bool(fc)                  # Rollen auf flacher Strecke: leichte Verzögerung durch den Widerstand
    (Ec2, _, vjf2, _), (_, _, vjf3, _), _ = PH.special_steps(np.array(10.0), 0.0, 40.0, 100.0, 0.1)
    assert vjf3 == pytest.approx(13.85, abs=0.05) and vjf3 > 10                                              # volle Zugkraft (200 kN) beschleunigt mit etwa 0,46 m/s²
    assert vjb == pytest.approx(np.sqrt(900 - 2 * 0.7 * 100)) and Eb == 0.0 and bool(fb)                      # volle Bremsung: v² sinkt um 2 * 0,7 * dx
    G = C.MASS * C.G_ACC * np.sin(np.arctan(-0.02))
    assert PH.special_steps(np.array(10.0), G, 40.0, 100.0, 0.1, modes=("coast",))[0][2] > 10                  # bergab rollt der Zug schneller


def test_special_steps_mark_a_stop_as_infeasible():
    out = PH.special_steps(np.array(1.0), 0.0, 40.0, 500.0, 0.1, modes=("brake", "coast"))
    assert not bool(out[0][3]) and not bool(out[1][3])                                                        # bremsen und rollen enden bei 1 m/s nach 500 m unter dem Mindesttempo


def test_stencil_weights_sum_to_one_and_the_cubic_interpolation_is_exact_for_cubics():
    dv, nv = 0.5, 30
    vj = np.array([3.3, 7.77, 0.0, 14.1])
    idx, w, jlo, wl = PH.stencil(vj, dv, nv)
    assert np.allclose(w.sum(axis=-1), 1.0) and np.allclose(np.clip(wl, 0, 1), wl)
    assert jlo.tolist() == [6, 15, 0, 28] and np.allclose(wl, [0.6, 0.54, 0.0, 0.2])                                         # Index der unteren Rasterstelle und lineares Gewicht; v = 0 liegt auf Index 0
    Vn = (dv * np.arange(nv)) ** 3
    got = PH.interp_v(Vn, idx, w, jlo, wl, cubic=True)
    assert np.allclose(got[[0, 1, 3]], vj[[0, 1, 3]] ** 3, atol=1e-9)                                         # kubisch exakt; am Rand (0,0) greift die lineare Rückfallstelle
    lin = PH.interp_v(Vn, idx, w, jlo, wl, cubic=False)
    assert np.allclose(lin[0], (1 - wl[0]) * Vn[jlo[0]] + wl[0] * Vn[jlo[0] + 1])


def test_interpolation_falls_back_to_linear_next_to_forbidden_states():
    dv, nv = 1.0, 10
    Vn = np.full(nv, 5.0)
    Vn[5] = PH.BIG
    idx, w, jlo, wl = PH.stencil(np.array([4.5]), dv, nv)                                                     # Stützstellen 3..6 enthalten den verbotenen Zustand 5
    assert PH.interp_v(Vn, idx, w, jlo, wl, cubic=True)[0] == pytest.approx(0.5 * 5.0 + 0.5 * PH.BIG)


def test_replay_energy_is_force_times_distance_and_time_is_step_independent():
    G = np.zeros(4)
    vn = np.zeros(5)
    Fc = np.full(4, 100e3)
    kind = np.zeros(4, dtype=int)
    a = PH.replay(G, 500.0, vn, Fc, kind, dt_step=0.2)
    b = PH.replay(G, 500.0, vn, Fc, kind, dt_step=0.05)
    assert a["E"] == pytest.approx(100e3 * 2000 / 1e6, rel=1e-9) and a["T"] == pytest.approx(b["T"], rel=1e-6) and a["vend"] > 10 and a["maxdev"] > 0


def test_replay_a_standing_start_without_force_aborts():
    r = PH.replay(np.zeros(2), 500.0, np.zeros(3), np.zeros(2), np.zeros(2, dtype=int))
    assert np.isnan(r["E"]) and r["maxdev"] == float("inf")


def test_replay_brake_cells_use_the_planned_node_speed():
    one = PH.replay(np.zeros(1), 500.0, np.array([0.0, 20.0]), np.array([100e3]), np.array([0]))                 # Geschwindigkeit nach der ersten Zelle
    r = PH.replay(np.zeros(2), 500.0, np.array([0.0, 20.0, 10.0]), np.array([100e3, -1.0]), np.array([0, 1]))
    assert r["vend"] == pytest.approx(10.0) and r["maxdec"] == pytest.approx((one["vend"] ** 2 - 100) / 1000.0)
