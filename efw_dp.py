"""Dynamische Programmierung über (Ort, Geschwindigkeit) mit Lagrange-Parameter auf der Zeit: minimiert Energie + lambda * Zeit; lambda wird per Bisektion so gewählt, dass die Fahrzeit das
Budget erreicht.

Zustände: Ortszellen der Länge dx, Geschwindigkeitsraster dv. Übergänge: Raster-Zielgeschwindigkeiten (Halten, Beschleunigen, Bremsen) plus drei Übergänge mit freiem Zielzustand und
interpolierter Wertfunktion: Rollen (F = 0), volle Zugkraft, volle Bremsung. (Eine DP nur mit Raster-Zielen ist bei kleinen Zellen um rund 15 % zu langsam, weil die Geschwindigkeitsänderung je
Zelle kleiner als der Rasterschritt ist.) Die Vorwärtsspur läuft im kontinuierlichen Zustand ohne Rasterrundung des Pfades.
"""
from __future__ import annotations

import numpy as np

import efw_constants as C
from efw_physics import BIG, interp_v, special_steps, stencil, trans
from efw_track import cell_arrays

KIND_DRIVE, KIND_BRAKE, KIND_COAST = 0, 1, 2


class DP:
    def __init__(self, prof: dict, dx: float = C.DP_DX, dv: float = C.DP_DV, eta: float = 0.0, modes=("coast", "full", "brake"), cubic: bool = False):
        self.prof, self.dx, self.dv, self.eta, self.cubic, self.modes = prof, dx, dv, eta, cubic, modes
        G, lim = cell_arrays(prof, dx)
        N = len(G)
        self.N, self.G, self.lim = N, G, lim
        nv = int(round(float(lim.max()) / dv)) + 1
        self.nv = nv
        self.vg = dv * np.arange(nv)
        vg = self.vg
        nl = np.zeros(N + 1)                                      # Tempolimit an den Zellgrenzen: Minimum der Nachbarzellen
        nl[1:N] = np.minimum(lim[:-1], lim[1:])
        self.nl = nl
        allowed = vg[None, :] <= nl[:, None] + 1e-9
        allowed[:, 0] = False
        allowed[0, 0] = True
        allowed[N, 0] = True                                      # Start und Ziel stehen
        allowed[0, 1:] = False
        allowed[N, 1:] = False
        self.allowed = allowed
        vi, vj = vg[None, :, None], vg[None, None, :]
        self.Eb = np.empty((N, nv, nv), dtype=np.float32)
        self.Tb = np.empty((N, nv, nv), dtype=np.float32)
        chunk = max(1, int(2e6 // (nv * nv)))
        for k0 in range(0, N, chunk):
            k1 = min(N, k0 + chunk)
            E, dt, _F, feas = trans(vi, vj, G[k0:k1, None, None], lim[k0:k1, None, None], dx, eta)
            feas &= allowed[k0:k1, :, None] & allowed[k0 + 1:k1 + 1, None, :]
            self.Eb[k0:k1] = np.where(feas, E, BIG)
            self.Tb[k0:k1] = np.where(feas, dt, 0.0)
        sp = special_steps(vg[None, :], G[:, None], lim[:, None], dx, dv, eta, modes)
        cE, cdt, cjlo, cw, cf, cidx, cw4 = [], [], [], [], [], [], []
        for (E, dt, vj_, fe) in sp:
            E, dt, vj_, fe = [np.broadcast_to(z, (N, nv)) for z in (E, dt, vj_, fe)]
            fe = fe & allowed[:N] & (vj_ <= nl[1:, None] + 1e-9)
            idx4, w4, jlo, w = stencil(vj_, dv, nv)
            cidx.append(idx4)
            cw4.append(w4)
            cE.append(np.where(fe, E, 0.0))
            cdt.append(np.where(fe, dt, 0.0))
            cjlo.append(jlo)
            cw.append(w)
            cf.append(fe)
        self.sE, self.sdt, self.sjlo, self.sw, self.sf = np.array(cE), np.array(cdt), np.array(cjlo), np.array(cw), np.array(cf)
        self.sidx, self.sw4 = np.array(cidx), np.array(cw4)

    def backward(self, lam: float) -> np.ndarray:
        """Wertfunktion V[k, j] = kleinste Energie + lam * Zeit vom Zustand (Zellgrenze k, Geschwindigkeit j) bis zum Ziel."""
        N, nv = self.N, self.nv
        V = np.full((N + 1, nv), BIG)
        V[N, 0] = 0.0
        for k in range(N - 1, -1, -1):
            Vn = V[k + 1]
            best = (self.Eb[k] + lam * self.Tb[k] + Vn[None, :]).min(axis=1)
            for m in range(len(self.modes)):
                cc = self.sE[m, k] + lam * self.sdt[m, k] + interp_v(Vn, self.sidx[m, k], self.sw4[m, k], self.sjlo[m, k], self.sw[m, k], self.cubic)
                best = np.minimum(best, np.where(self.sf[m, k], cc, 2 * BIG))
            V[k] = np.where(self.allowed[k], np.minimum(best, BIG), BIG)
        return V

    def trace(self, lam: float, V=None) -> dict:
        """Vorwärtsspur zu lam: Knotengeschwindigkeiten `v`, mittlere Zugkraft je Zelle `F`, Art der Zelle `kind` (0 Antrieb/Halten, 1 Bremsen, 2 Rollen), Energie `E` und Zeit `T`."""
        if V is None:
            V = self.backward(lam)
        N, dx, dv, vg = self.N, self.dx, self.dv, self.vg
        v = 0.0
        vn = np.zeros(N + 1)
        Fc = np.zeros(N)
        kind = np.zeros(N, dtype=np.int8)
        E = T = 0.0
        fails = 0
        for k in range(N):
            Vn = V[k + 1]
            e, dt, F, feas = trans(v, vg, self.G[k], self.lim[k], dx, self.eta)
            feas = feas & self.allowed[k + 1]
            cost = np.where(feas, e + lam * dt + Vn, 2 * BIG)
            j = int(np.argmin(cost))
            bestc = cost[j]
            choice = ("g", j)
            if v > 0:
                for m, (es, dts, vjs, fs) in enumerate(special_steps(np.array(v), self.G[k], self.lim[k], dx, dv, self.eta, self.modes)):
                    if fs and vjs <= self.nl[k + 1] + 1e-9:
                        i4, w4, jl, wl = stencil(float(vjs), dv, self.nv)
                        cc = float(es) + lam * float(dts) + float(interp_v(Vn, i4, w4, jl, wl, self.cubic))
                        if cc < bestc:
                            bestc = cc
                            choice = ("s", m, float(vjs), float(dts), float(es))
            if bestc >= BIG:                                       # nicht fortsetzbar: auf einen Rasterzustand zurückfallen
                fails += 1
                v0 = vg[max(int(round(v / dv)), 1)] if k > 0 else 0.0
                e, dt, F, feas = trans(v0, vg, self.G[k], self.lim[k], dx, self.eta)
                feas = feas & self.allowed[k + 1]
                cost = np.where(feas, e + lam * dt + Vn, 2 * BIG)
                j = int(np.argmin(cost))
                v = v0
                choice = ("g", j)
                if cost[j] >= BIG:
                    return {"ok": False, "E": float("nan"), "T": float("nan"), "fails": fails}
            if choice[0] == "g":
                j = choice[1]
                E += float(e[j])
                T += float(dt[j])
                Fc[k] = float(F[j])
                kind[k] = KIND_BRAKE if F[j] < 0 else KIND_DRIVE
                v = float(vg[j])
            else:
                _, m, vjs, dts, es = choice
                mode = self.modes[m]
                _, _, Fs, _ = trans(np.array(v), np.array(vjs), self.G[k], self.lim[k], dx, self.eta)
                E += es
                T += dts
                Fc[k] = float(Fs) if mode != "coast" else 0.0
                kind[k] = {"coast": KIND_COAST, "full": KIND_DRIVE, "brake": KIND_BRAKE}[mode] if not (mode == "brake" and Fc[k] >= 0) else KIND_DRIVE
                v = vjs
            vn[k + 1] = v
        return {"ok": abs(v) < 1e-9, "E": E, "T": T, "v": vn, "F": Fc, "kind": kind, "fails": fails, "lam": lam}

    def solve_budget(self, Tb: float, iters: int = C.DP_ITERS) -> dict:
        """Kleinste Energie bei Fahrzeit höchstens Tb (Bisektion auf lambda). Gewählt wird die zulässige Spur; ihr Wert ist eine obere Schranke des wahren Optimums."""
        hi = 4.0
        res_hi = self.trace(hi)
        while (not res_hi["ok"] or res_hi["T"] > Tb) and hi < 4000.0:
            hi *= 4.0
            res_hi = self.trace(hi)
        if not res_hi["ok"] or res_hi["T"] > Tb:
            res_hi["infeasible"] = True
            return res_hi
        best, lo = res_hi, 0.0
        for _ in range(iters):
            mid = 0.5 * (lo + hi)
            r = self.trace(mid)
            if r["ok"] and r["T"] <= Tb:
                hi = mid
                if r["E"] < best["E"]:
                    best = r
            else:
                lo = mid
        best["infeasible"] = False
        return best

    def fastest(self) -> dict:
        return self.trace(1000.0)
