"""Strecke der Demo: Steigungsprofil und Tempolimit aus 500-m-Einheiten, erzeugt mit SplitMix64 (Zufallszahlen in Ganzzahl-Arithmetik, plattformstabil)."""
from __future__ import annotations

import numpy as np

import efw_constants as C
from efw_rng import SplitMix64


def _uniform(rng, lo: int, hi: int) -> float:
    """Gleichverteilt zwischen lo/10 und hi/10 (Promille) in Schritten von 0,1."""
    return (lo + rng.below(hi - lo + 1)) / 10.0


def _normal(rng, mean: float, sd: float, lo: float, hi: float) -> float:
    """Näherung der Normalverteilung (Summe von zwölf Gleichverteilten minus 6, Irwin-Hall), beschnitten auf [lo, hi]."""
    z = (sum(rng.below(1000) for _ in range(12)) - 6000) / 1000.0
    return float(min(max(mean + sd * z, lo), hi))


def _pieces(rng, n: int, lo_len: int, hi_len: int, draw) -> np.ndarray:
    """Stückweise konstante Werte: Stücke von lo_len bis hi_len Einheiten Länge."""
    out = np.zeros(n)
    i = 0
    while i < n:
        ln = lo_len + rng.below(hi_len - lo_len + 1)
        out[i:i + ln] = draw()
        i += ln
    return out


def make_profile(typ: str, seed: int) -> dict:
    """Profil: Steigung `grad` in Promille und Tempolimit `lim` in m/s je Einheit. Typen: flach, wellig (Höhenunterschied null), rampe, tempolimit, gefaelle."""
    if typ not in C.PROFILE_TYPES:
        raise ValueError(typ)
    rng = SplitMix64(1_000_003 * (C.PROFILE_TYPES.index(typ) + 1) + seed)
    n = C.N_UNITS
    lim = np.full(n, C.V_TOP)
    if typ in ("flach", "rampe", "tempolimit"):
        grad = _pieces(rng, n, 4, 8, lambda: _uniform(rng, -10, 10))
    elif typ == "wellig":
        grad = _pieces(rng, n, 2, 6, lambda: _normal(rng, 0.0, 8.0, -15.0, 15.0))
        grad = grad - grad.mean()
    else:
        grad = _pieces(rng, n, 2, 6, lambda: _normal(rng, -6.0, 5.0, -18.0, 6.0))
    if typ == "rampe":
        ln = 4 + rng.below(5)
        s = 6 + rng.below(n - ln - 10)
        grad[s:s + ln] = _uniform(rng, 150, 250)
    if typ == "tempolimit":
        for _ in range(1 + rng.below(2)):
            ln = 4 + rng.below(7)
            s = 2 + rng.below(n - ln - 4)
            lim[s:s + ln] = min(lim[s], float((20, 25, 30)[rng.below(3)]))
    return {"typ": typ, "seed": int(seed), "grad": grad, "lim": lim, "L": n * C.UNIT_M}


def cell_arrays(prof: dict, dx: float) -> tuple:
    """Steigungskraft (N) und Tempolimit je Zelle der Länge dx (muss 500 m teilen)."""
    reps = C.UNIT_M / dx
    if abs(reps - round(reps)) > 1e-9:
        raise ValueError("dx muss 500 m teilen")
    reps = int(round(reps))
    grad = np.repeat(prof["grad"], reps)
    lim = np.repeat(prof["lim"], reps)
    return C.MASS * C.G_ACC * np.sin(np.arctan(grad / 1000.0)), lim


def height_profile(prof: dict) -> np.ndarray:
    """Höhe (m) an den Einheitsgrenzen, Start 0: Steigung in Promille mal Länge."""
    return np.concatenate([[0.0], np.cumsum(prof["grad"] / 1000.0 * C.UNIT_M)])
