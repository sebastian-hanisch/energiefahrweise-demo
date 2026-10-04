"""Live-Rechnung der Fahrweisen für ein Profil und eine Fahrzeitreserve, Energiebilanz, Vergleichsformel und Meldungen."""
from __future__ import annotations

import time

import numpy as np

import efw_constants as C
import efw_dp as D
import efw_strategies as S
import efw_track as TR
from efw_physics import resist

COAST_F = 500.0            # Zellen mit |Zugkraft| unter 500 N gelten als Rollen (ohne Zugkraft)


def formula_saving(reserve_pct: float) -> float:
    """Ersparnis (Prozent) nach der Slow-Steaming-Formel „Energie je km ~ v^2“: eine um den Faktor 1 + r längere Fahrzeit bedeutet 1 / (1 + r)^2 der Energie."""
    r = reserve_pct / 100.0
    return 100.0 * (1.0 - 1.0 / (1.0 + r) ** 2)


def phases_from_force(F) -> list:
    """Art je Zelle aus der mittleren Zugkraft: `drive` (Antrieb oder Halten), `coast` (Rollen), `brake`."""
    return ["brake" if f < -COAST_F else "coast" if abs(f) <= COAST_F else "drive" for f in F]


def phases_from_kind(kind) -> list:
    return [("drive", "brake", "coast")[int(k)] for k in kind]


def balance(prof: dict, dx: float, v, F) -> dict:
    """Energiebilanz einer Fahrt in MJ: Traktionsarbeit, Widerstandsarbeit, Hubarbeit (Höhenunterschied) und Bremsverlust (Bremsarbeit der negativen Zugkraft).
    Es gilt Traktion - Bremsverlust = Widerstand + Hub (Start und Ziel stehen)."""
    G, _ = TR.cell_arrays(prof, dx)
    v = np.asarray(v, dtype=float)
    F = np.asarray(F, dtype=float)
    return {"traction": float(np.maximum(F, 0.0).sum() * dx / 1e6), "brake": float(np.maximum(-F, 0.0).sum() * dx / 1e6),
            "resist": float(resist(v[:-1], v[1:]).sum() * dx / 1e6), "lift": float(G.sum() * dx / 1e6)}


def _entry(prof, dx, v, F, phase, E, T, eta):
    n = len(F)
    x = [dx * k for k in range(n + 1)]
    return {"E": float(E), "T": float(T), "x": x, "v": [float(a) for a in v], "phase": phase, "F": [float(a) for a in F], "balance": balance(prof, dx, v, F), "dx": dx, "eta": eta}


def run_live(settings: dict) -> dict:
    """Schnellste Fahrt, gleichmäßig langsamer, Rollpunkt-Regel und Optimum (DP) auf dem Profil zu `settings` (reserve in %, profile, regen, seed). Fahrzeitbudget = (1 + r) mal
    schnellste Fahrt des Simulators."""
    t0 = time.time()
    prof = TR.make_profile(settings["profile"], settings["seed"])
    eta = C.REGEN_ETA if settings["regen"] == "mit" else 0.0
    reserve = float(settings["reserve"])
    fb = S.FB(prof, eta=eta)
    T0, E0, pf = fb.run(float(fb.lim.max()), None, want_profile=True)
    Tb = T0 * (1.0 + reserve / 100.0)
    results = {"fast": _entry(prof, fb.h, pf["v"], pf["F"], phases_from_force(pf["F"]), E0, T0, eta)}
    a = fb.strategy_a(Tb)
    _, _, pa = fb.run(a["vcap"], None, want_profile=True)[0:3]
    results["naive"] = _entry(prof, fb.h, pa["v"], pa["F"], phases_from_force(pa["F"]), a["E"], a["T"], eta)
    results["naive"]["vcap"] = a["vcap"]
    _b1, b2 = fb.strategy_b(Tb, a["vcap"])
    coast_ok = b2 is not None
    if coast_ok:
        _, _, pb = fb.run(b2["vcap"], b2["xc"], want_profile=True)
        results["coast"] = _entry(prof, fb.h, pb["v"], pb["F"], phases_from_force(pb["F"]), b2["E"], b2["T"], eta)
        results["coast"].update({"vcap": b2["vcap"], "xc": b2["xc"]})
    else:                                                      # Budget so nicht erreichbar: die Regel fällt auf „gleichmäßig langsamer“ zurück
        results["coast"] = dict(results["naive"])
    dp = D.DP(prof, eta=eta)
    sol = dp.solve_budget(Tb)
    dp_ok = not sol.get("infeasible", False) and sol.get("ok", False)
    if dp_ok:
        results["dp"] = _entry(prof, dp.dx, sol["v"], sol["F"], phases_from_kind(sol["kind"]), sol["E"], sol["T"], eta)
    else:
        results["dp"] = dict(results["coast"])
    return {"profile": prof, "reserve": reserve, "eta": eta, "T_min": T0, "T_budget": Tb, "results": results, "coast_ok": coast_ok, "dp_ok": dp_ok,
            "formula_E": E0 / (1.0 + reserve / 100.0) ** 2, "seconds": time.time() - t0}


def saving_pct(run: dict, key: str) -> float:
    """Ersparnis in Prozent der Energie der schnellsten Fahrt (Basis = schnellste Fahrt)."""
    return 100.0 * (1.0 - run["results"][key]["E"] / run["results"]["fast"]["E"])


def dp_vs_pct(run: dict, ref: str) -> float:
    """Um wie viel Prozent das Optimum weniger Energie braucht als `ref` (Basis = Referenz)."""
    return 100.0 * (1.0 - run["results"]["dp"]["E"] / run["results"][ref]["E"])


def coast_share_pct(entry: dict) -> float:
    """Anteil der Strecke (Prozent), der rollend (ohne Zugkraft) gefahren wird."""
    return 100.0 * sum(1 for p in entry["phase"] if p == "coast") / len(entry["phase"])


def brake_share_pct(entry: dict) -> float:
    """Anteil der eingesetzten Energie, der in der Bremse vernichtet wird: Bremsverlust geteilt durch Traktionsarbeit plus beim Bergabfahren frei werdende Lageenergie."""
    b = entry["balance"]
    supply = b["traction"] + max(-b["lift"], 0.0)
    return 100.0 * b["brake"] / supply if supply else float("nan")


def messages(run: dict, settings: dict) -> list:
    """Meldungen der App als Liste (Zustand, Text); Zustand `success`, `info` oder `warning`."""
    out = []
    r = run["results"]
    res = run["reserve"]
    s_naive, s_coast, s_dp = saving_pct(run, "naive"), saving_pct(run, "coast"), saving_pct(run, "dp")
    form = formula_saving(res)
    out.append(("success" if s_dp - s_naive >= 10.0 else "info",
                f"Bei {res:g} % Fahrzeitreserve spart gleichmäßiges Langsamfahren {s_naive:.0f} % der Energie (die v²-Formel sagt {form:.0f} % voraus), die Rollpunkt-Regel {s_coast:.0f} % und das Optimum {s_dp:.0f} %. "
                f"Der Unterschied kommt vom Rollen: In der schnellsten Fahrt gehen {brake_share_pct(r['fast']):.0f} % der Traktionsenergie in der Bremse verloren."))
    gap = dp_vs_pct(run, "coast")
    if abs(gap) < 1.0:
        out.append(("info", f"Hier genügt die einfache Rollpunkt-Regel: Das Optimum liegt nur {gap:+.1f} % neben ihr, eine einzige Rollphase reicht aus (Unterschiede unter 0,5 % sind nicht belastbar)."))
    elif gap > 0:
        out.append(("success" if gap >= 5.0 else "info", f"Das Optimum braucht {gap:.0f} % weniger Energie als die Rollpunkt-Regel: Es rollt dort, wo es sich am meisten lohnt (Gefälle und vor dem Bremsen), und setzt Zugkraft gezielt ein."))
    else:
        out.append(("info", f"Hier ist die Rollpunkt-Regel sogar {-gap:.1f} % besser als die DP: Das Optimum ist nur so genau wie sein Raster (Fehlerboden etwa 0,3 bis 0,5 %), bei dieser Strecke bringt die Optimierung nichts."))
    if settings["regen"] == "mit":
        out.append(("info", f"Mit Rückspeisung ({int(100 * C.REGEN_ETA)} %) wird ein Teil der Bremsenergie zurückgewonnen; der Vorsprung des Rollens gegenüber dem Langsamfahren ist dann nur etwa halb so groß wie ohne."))
    if not run["coast_ok"]:
        out.append(("warning", "Die Rollpunkt-Regel erreicht das Fahrzeitbudget auf diesem Profil nicht; sie ist hier durch „gleichmäßig langsamer“ ersetzt."))
    if not run["dp_ok"]:
        out.append(("warning", "Die DP fand keine zulässige Fahrt im Fahrzeitbudget; gezeigt wird die Rollpunkt-Regel."))
    return out
