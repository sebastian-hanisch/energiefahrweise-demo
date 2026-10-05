"""Orakel-Tests (unabhängiger Rechenweg): Raster-DP gegen Vollaufzählung mit Gefälle und Rückspeisung; Rollpunkt-Regel gegen Gittersuche über (Reisetempo, Rollpunkt)."""
import itertools

import numpy as np
import pytest

import efw_constants as C
import efw_dp as D
import efw_strategies as S
import efw_track as TR

M = C.MASS * C.ROT


def cell_by_quadrature(vi, vj, G, lim, dx, eta, n=800):
    """Kosten einer Zelle mit konstanter Beschleunigung: mittlere Zugkraft aus punktweiser Quadratur des Widerstands (nicht Simpson), eigene Zulässigkeit."""
    if vi + vj <= 0 or vi > lim + 1e-9 or vj > lim + 1e-9:
        return None
    a = (vj * vj - vi * vi) / (2 * dx)
    if a < -C.DECEL - 1e-9:
        return None
    x = (np.arange(n) + 0.5) * dx / n
    v = np.sqrt(np.maximum(vi * vi + 2 * a * x, 0.0))
    F = M * a + (C.RES_A + C.RES_B * v + C.RES_C * v * v).mean() + G
    vm = np.sqrt((vi * vi + vj * vj) / 2)
    if M * a + C.RES_A + C.RES_B * vm + C.RES_C * vm * vm + G > min(C.F_MAX, C.P_MAX / max(vm, 1e-9)) + 1.0:
        return None
    return (max(F, 0.0) - eta * max(-F, 0.0)) * dx / 1e6, 2 * dx / (vi + vj)


@pytest.mark.parametrize("seed", range(6))
def test_raster_dp_equals_the_enumeration_with_gradients_and_regeneration(seed):
    rng = np.random.default_rng(seed)
    dx, dv, nspeed = 500.0, 5.0, 4
    grad = rng.uniform(-8, 8, 5)
    prof = {"grad": grad, "lim": np.full(5, 20.0), "L": 2500.0}
    eta = 0.6 if seed % 2 else 0.0
    lam = float(rng.choice([0.3, 1.5, 8.0]))
    G = C.MASS * C.G_ACC * np.sin(np.arctan(grad / 1000.0))
    best = None
    for mid in itertools.product(range(1, nspeed + 1), repeat=4):
        seq = (0,) + mid + (0,)
        cells = [cell_by_quadrature(seq[k] * dv, seq[k + 1] * dv, G[k], 20.0, dx, eta) for k in range(5)]
        if any(c is None for c in cells):
            continue
        val = sum(c[0] + lam * c[1] for c in cells)
        best = val if best is None or val < best else best
    dp = D.DP(prof, dx=dx, dv=dv, eta=eta, modes=())
    assert dp.backward(lam)[0, 0] == pytest.approx(best, rel=2e-3)


def test_coast_rule_is_near_the_grid_search_optimum_on_a_downhill_profile():
    """Im Gefälle ist der zulässige Reisetempo-Bereich der Rollpunkt-Regel sehr schmal (hier rund 0,2 m/s); die Regel muss ihn finden (alte Fassung: 15 % schlechter als die Gittersuche)."""
    prof = TR.make_profile("gefaelle", 7409)
    fb = S.FB(prof)
    Tb = 1.15 * fb.fastest()[0]
    a = fb.strategy_a(Tb)
    _b1, b2 = fb.strategy_b(Tb, a["vcap"])
    best = None
    for vc in np.linspace(a["vcap"], a["vcap"] + 0.6, 13):
        ilo = fb._x_reach(float(vc))
        for i in range(ilo, fb.n + 1, 4):
            t, e = fb.run(float(vc), i * fb.h)
            if t <= Tb + 1e-9 and (best is None or e < best):
                best = e
    assert b2 is not None and b2["T"] <= Tb + 1e-9
    assert b2["E"] <= best * 1.01
