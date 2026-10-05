"""Vergleichsverfahren: Vorwärts-Rückwärts-Simulator (Fahrt mit höchster Zugkraft, gebremst wird so spät wie möglich) für
  (a) „gleichmäßig langsamer“: Höchsttempo gesenkt, so dass die Fahrzeit das Budget erreicht, und
  (b) „Rollpunkt-Regel“ (Beschleunigen - Beharren - Rollen - Bremsen): ab dem Rollpunkt keine Zugkraft mehr; der Rollpunkt wird so gewählt, dass die Fahrzeit das Budget erreicht, das Reisetempo
      unter einigen Kandidaten energieminimal.
"""
from __future__ import annotations

import math

import numpy as np

import efw_constants as C
from efw_physics import MASS_EFF, trans
from efw_track import cell_arrays


class FB:
    def __init__(self, prof: dict, h: float = C.FB_H, eta: float = 0.0):
        self.prof, self.h, self.eta = prof, h, eta
        G, lim = cell_arrays(prof, h)
        self.G, self.lim = G, lim
        n = len(G)
        self.n = n
        nl = np.zeros(n + 1)
        nl[1:n] = np.minimum(lim[:-1], lim[1:])
        self.nl = nl
        self.Gl = G.tolist()
        self.nll = nl.tolist()

    def _forward(self, vcap: float, xc):
        """Quadrat der Geschwindigkeit an den Zellgrenzen bei höchster Zugkraft (bis zum Rollpunkt xc) und danach Rollen; auf vcap und das Tempolimit begrenzt. None, wenn der Zug stehen bleibt."""
        h, n = self.h, self.n
        Gl, nll = self.Gl, self.nll
        ic = n + 1 if xc is None else int(round(xc / h))
        wf = [0.0] * (n + 1)
        w = 0.0
        sq = math.sqrt
        for i in range(n):
            c2 = min(nll[i + 1], vcap) ** 2
            v = sq(w)
            G = Gl[i]
            wj = w
            if i < ic:
                for _ in range(4):
                    vj = sq(wj)
                    vm = sq((w + wj) / 2.0)
                    F = C.F_MAX if vm * C.F_MAX < C.P_MAX else C.P_MAX / max(vm, 1e-9)
                    R = C.RES_A + C.RES_B * vm + C.RES_C * vm * vm
                    wj = w + 2.0 * h * (F - R - G) / MASS_EFF
                    if wj < 0:
                        wj = 0.0
            else:
                for _ in range(6):
                    vj = sq(wj)
                    vm = sq((w + wj) / 2.0)
                    R = C.RES_A + C.RES_B * (v + 4.0 * vm + vj) / 6.0 + C.RES_C * (w + wj) / 2.0
                    wj = w - 2.0 * h * (R + G) / MASS_EFF
                    if wj < 0.25:
                        return None
            if wj > c2:
                wj = c2
            wf[i + 1] = wj
            w = wj
        return np.array(wf)

    def run(self, vcap: float, xc=None, want_profile: bool = False):
        """Fahrt mit Reisetempo vcap und Rollpunkt xc (None = nie rollen). Rückgabe (T, E) oder (inf, inf); mit want_profile zusätzlich dict(v, F)."""
        wf = self._forward(vcap, xc)
        if wf is None:
            return (math.inf, math.inf, None) if want_profile else (math.inf, math.inf)
        n, h = self.n, self.h
        wb = np.zeros(n + 1)
        ab2 = 2.0 * C.DECEL * h
        nl2 = np.minimum(self.nl, vcap) ** 2
        for i in range(n - 1, 0, -1):                              # rückwärts: spätestes Bremsen mit der Verzögerungsgrenze
            wb[i] = min(nl2[i], wb[i + 1] + ab2)
        w = np.minimum(wf, wb)
        w[0] = 0.0
        w[n] = 0.0
        v = np.sqrt(w)
        E, dt, F, feas = trans(v[:-1], v[1:], self.G, self.lim, h, self.eta)
        T, Etot = float(dt.sum()), float(E.sum())
        if want_profile:
            return T, Etot, {"v": v, "F": F, "nbad": int((~feas).sum())}
        return T, Etot

    def fastest(self):
        return self.run(float(self.lim.max()))

    def strategy_a(self, Tb: float, iters: int = C.FB_A_ITERS) -> dict:
        """Gleichmäßig langsamer: Reisetempo (Höchsttempo) per Bisektion so, dass die Fahrzeit Tb erreicht."""
        vmax = float(self.lim.max())
        T, E = self.run(vmax)
        if T >= Tb:
            return {"vcap": vmax, "T": T, "E": E}
        lo, hi = 1.5, vmax
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            t, _e = self.run(mid)
            if t > Tb:
                lo = mid
            else:
                hi = mid
        t, e = self.run(hi)
        return {"vcap": hi, "T": t, "E": e}

    def _x_reach(self, vcap: float):
        wf = self._forward(vcap, None)
        if wf is None:
            return None
        idx = np.nonzero(wf >= (vcap * 0.999) ** 2)[0]
        return int(idx[0]) if len(idx) else None

    def coast_point(self, vcap: float, Tb: float, iters: int = C.FB_COAST_ITERS):
        """Für ein Reisetempo vcap der Rollpunkt, bei dem die Fahrzeit Tb erreicht wird (die Zeit wächst, je früher gerollt wird)."""
        n, h = self.n, self.h
        ilo = self._x_reach(vcap)
        if ilo is None:
            return None
        T_end, _E_end = self.run(vcap, None)
        if T_end > Tb + 1e-9:
            return None                                            # schon ohne Rollen zu langsam
        T_lo, _E_lo = self.run(vcap, ilo * h)
        if T_lo < Tb:
            return None                                            # selbst sofortiges Rollen reicht nicht: Reisetempo zu hoch
        a, b = ilo, n
        for _ in range(iters):
            if b - a <= 1:
                break
            m = (a + b) // 2
            t, _e = self.run(vcap, m * h)
            if t > Tb:
                a = m
            else:
                b = m
        t, e = self.run(vcap, b * h)
        return {"vcap": vcap, "xc": b * h, "T": t, "E": e}

    def strategy_b(self, Tb: float, a_vcap: float, nv: int = C.FB_CANDIDATES, refine: int = C.FB_REFINE):
        """Rollpunkt-Regel. Rückgabe (b1, b2): b1 = Reisetempo gleich Streckenhöchsttempo, nur der Rollpunkt frei (None, wenn das Budget so nicht erreichbar ist);
        b2 = zusätzlich das Reisetempo unter nv Kandidaten (von a_vcap bis zum Höchsttempo) energieminimal, mit lokaler Verfeinerung."""
        vmax = float(self.lim.max())
        b1 = self.coast_point(vmax, Tb)
        best = None
        for vc in np.linspace(a_vcap, vmax, nv):
            r = self.coast_point(float(vc), Tb)
            if r is not None and (best is None or r["E"] < best["E"]):
                best = r
        if best is not None:
            step = (vmax - a_vcap) / (nv - 1)
            for vc in np.linspace(max(a_vcap, best["vcap"] - step), min(vmax, best["vcap"] + step), refine):
                r = self.coast_point(float(vc), Tb)
                if r is not None and r["E"] < best["E"]:
                    best = r
            # Der zulässige Reisetempo-Bereich (Rollpunkt trifft das Budget) endet am Rand, wo schon sofortiges Rollen nicht mehr langsam genug ist; im Gefälle ist er sehr schmal,
            # und die Energie ist dort am kleinsten. Deshalb wird der Rand per Bisektion gesucht und zusammen mit Stützstellen davor geprüft.
            lo, hi = a_vcap, vmax
            if self.coast_point(vmax, Tb) is None:
                for _ in range(C.FB_EDGE_ITERS):
                    mid = 0.5 * (lo + hi)
                    if self.coast_point(mid, Tb) is not None:
                        lo = mid
                    else:
                        hi = mid
                for vc in np.linspace(a_vcap, lo, refine + 1):
                    r = self.coast_point(float(vc), Tb)
                    if r is not None and r["E"] < best["E"]:
                        best = r
        return b1, best
