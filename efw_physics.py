"""Zugphysik je Zelle (vektorisiert): Fahrwiderstand, Übergang mit konstanter Beschleunigung, Sondersteuerungen (Rollen, volle Zugkraft, volle Bremsung).

Energie in MJ (Arbeit am Rad), Zeit in s, Geschwindigkeit in m/s, Kraft in N. Ohne Rückspeisung kostet Bremsen null; mit Wirkungsgrad eta > 0 wird ein Anteil eta der
Bremsarbeit gutgeschrieben.
"""
from __future__ import annotations

import numpy as np

import efw_constants as C

MASS_EFF = C.MASS * C.ROT


def resist(vi, vj):
    """Mittlerer Fahrwiderstand über eine Zelle bei konstanter Beschleunigung (v^2 linear im Ort); das Integral von v über den Ort nach Simpson."""
    wi = vi * vi
    wj = vj * vj
    vm = np.sqrt((wi + wj) / 2.0)
    vavg = (vi + 4.0 * vm + vj) / 6.0
    return C.RES_A + C.RES_B * vavg + C.RES_C * (wi + wj) / 2.0


def trans(vi, vj, G, vlim, dx, eta=0.0):
    """Übergang vi -> vj über dx mit konstanter Beschleunigung. Rückgabe (E in MJ, dt in s, mittlere Zugkraft F in N, zulässig)."""
    wi = vi * vi
    wj = vj * vj
    a = (wj - wi) / (2.0 * dx)
    F = MASS_EFF * a + resist(vi, vj) + G
    vm = np.sqrt((wi + wj) / 2.0)
    Fmid = MASS_EFF * a + C.RES_A + C.RES_B * vm + C.RES_C * vm * vm + G                # Zugkraft in Zellmitte
    cap = np.minimum(C.F_MAX, C.P_MAX / np.maximum(vm, 1e-9))
    feas = ((a >= -C.DECEL - 1e-9) & (Fmid <= cap + 1.0) & (vi <= vlim + 1e-9) & (vj <= vlim + 1e-9) & ((vi + vj) > 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        dt = 2.0 * dx / (vi + vj)
    E = (np.maximum(F, 0.0) - eta * np.maximum(-F, 0.0)) * dx / 1e6
    return E, dt, F, feas


def special_steps(vi, G, vlim, dx, vmin, eta=0.0, modes=("coast", "full", "brake")):
    """Steuerungen mit freiem (nicht-Raster-)Zielzustand: Rollen (F = 0), volle Zugkraft, volle Bremsung. Rückgabe je Modus (E, dt, vj, zulässig)."""
    vi = np.asarray(vi, dtype=float)
    wi = vi * vi
    out = []
    for mode in modes:
        if mode == "brake":
            wj = wi - 2.0 * C.DECEL * dx
            vj = np.sqrt(np.maximum(wj, 0.0))
        else:
            vj = vi.copy()
            wj = wi
            for _ in range(14):
                if mode == "coast":
                    F = 0.0
                    wj = wi + 2.0 * dx * (F - resist(vi, vj) - G) / MASS_EFF
                else:
                    vmid = np.sqrt((wi + vj * vj) / 2.0)
                    F = np.minimum(C.F_MAX, C.P_MAX / np.maximum(vmid, 1e-9))
                    wj = wi + 2.0 * dx * (F - (C.RES_A + C.RES_B * vmid + C.RES_C * vmid * vmid) - G) / MASS_EFF
                vj = np.sqrt(np.maximum(wj, 0.0))
        E, dt, F, feas = trans(vi, vj, G, vlim, dx, eta)
        if mode == "coast":
            E = E * 0.0
        feas = feas & (wj >= vmin * vmin) & (vi > 0)
        out.append((E, dt, vj, feas))
    return out


def stencil(vj, dv, nv):
    """Kubische Lagrange-Stützstellen (j0-1 .. j0+2) mit Gewichten sowie lineare Rückfallwerte für die Interpolation der Wertfunktion."""
    vj = np.asarray(vj)
    j0 = np.clip(np.floor(vj / dv + 1e-9).astype(int), 1, nv - 3)
    t = vj / dv - j0
    w = np.stack([-t * (t - 1) * (t - 2) / 6.0, (t + 1) * (t - 1) * (t - 2) / 2.0, -(t + 1) * t * (t - 2) / 2.0, (t + 1) * t * (t - 1) / 6.0], axis=-1)
    idx = j0[..., None] + np.array([-1, 0, 1, 2])
    jlo = np.clip(np.floor(vj / dv + 1e-9).astype(int), 0, nv - 2)
    wl = np.clip(vj / dv - jlo, 0.0, 1.0)
    return idx, w, jlo, wl


BIG = 1e12


def interp_v(Vn, idx, w, jlo, wl, cubic=True):
    """Wertfunktion bei beliebiger Geschwindigkeit: linear zwischen den Rasterpunkten, kubisch, wo alle vier Stützwerte zulässig sind."""
    lin = (1 - wl) * Vn[jlo] + wl * Vn[jlo + 1]
    if not cubic:
        return lin
    g = Vn[idx]
    ok = (g < BIG / 2).all(axis=-1)
    return np.where(ok, (g * w).sum(axis=-1), lin)


def replay(G, dx, vn, Fc, kind, dt_step=0.2):
    """Unabhängige Vorwärtsintegration (RK4 im Zeitbereich) einer Steuerfolge. Antriebs- und Rollzellen: offene Steuerung mit konstanter Zugkraft je Zelle, Energie als Integral F v dt;
    Bremszellen: Bremsregelung auf die geplante Knotengeschwindigkeit (Energie 0). Rückgabe E (MJ), T (s), Endgeschwindigkeit, größte Knotenabweichung, größte Verzögerung."""
    def acc(v, F, g):
        return (F - (C.RES_A + C.RES_B * v + C.RES_C * v * v) - g) / MASS_EFF

    def rk4(x, v, e, F, g, h):
        def f(vv):
            return vv, acc(vv, F, g), F * vv
        k1 = f(v)
        k2 = f(v + 0.5 * h * k1[1])
        k3 = f(v + 0.5 * h * k2[1])
        k4 = f(v + h * k3[1])
        return (x + h * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]) / 6.0, v + h * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]) / 6.0, e + h * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2]) / 6.0)

    v = 0.0
    E = T = maxdev = maxdec = 0.0
    for k in range(len(G)):
        g = G[k]
        if kind[k] == 1:                                           # Bremsen auf die Zielgeschwindigkeit
            vt = vn[k + 1]
            a = (vt * vt - v * v) / (2 * dx)
            maxdec = max(maxdec, -a)
            T += 2 * dx / (v + vt) if (v + vt) > 0 else float("inf")
            v = vt
            continue
        F = Fc[k]
        x, vv, e, t = 0.0, v, 0.0, 0.0
        while x < dx - 1e-12:
            x1, v1, e1 = rk4(x, vv, e, F, g, dt_step)
            if x1 <= dx:
                x, vv, e = x1, v1, e1
                t += dt_step
            else:
                lo, hi = 0.0, dt_step
                for _ in range(40):
                    mid = 0.5 * (lo + hi)
                    if rk4(x, vv, e, F, g, mid)[0] > dx:
                        hi = mid
                    else:
                        lo = mid
                x, vv, e = rk4(x, vv, e, F, g, hi)
                t += hi
                break
            if vv <= 0:
                return {"E": float("nan"), "T": float("nan"), "vend": 0.0, "maxdev": float("inf"), "maxdec": maxdec}
        E += max(e, 0.0) if F > 0 else 0.0
        T += t
        v = vv
        maxdev = max(maxdev, abs(v - vn[k + 1]))
    return {"E": E / 1e6, "T": T, "vend": v, "maxdev": maxdev, "maxdec": maxdec}
