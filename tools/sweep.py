"""Vorgerechnete Messreihe: je Profiltyp 30 Profile (Seeds 100-129) und je Fahrzeitreserve schnellste Fahrt, gleichmäßig langsamer, Rollpunkt-Regel und Optimum (DP) -> data/efw_results.json.
Dazu eine kleine Reihe mit Rückspeisung. Aufruf: python tools/sweep.py  (rund 10 Minuten mit 6 Prozessen)"""
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import efw_constants as C  # noqa: E402
import efw_dp as D  # noqa: E402
import efw_evaluation as E  # noqa: E402
import efw_strategies as S  # noqa: E402
import efw_track as TR  # noqa: E402


def one(args):
    typ, seed, reserves, regen = args
    eta = C.REGEN_ETA if regen else 0.0
    prof = TR.make_profile(typ, seed)
    fb = S.FB(prof, eta=eta)
    T0, E0, pf = fb.run(float(fb.lim.max()), None, want_profile=True)
    fast_bal = E.balance(prof, fb.h, pf["v"], pf["F"])
    dp = D.DP(prof, eta=eta)
    rows = []
    for r in reserves:
        Tb = T0 * (1.0 + r / 100.0)
        a = fb.strategy_a(Tb)
        _b1, b2 = fb.strategy_b(Tb, a["vcap"])
        sol = dp.solve_budget(Tb)
        ok = (not sol.get("infeasible", False)) and sol.get("ok", False)
        rec = {"type": typ, "seed": seed, "reserve": r, "regen": regen, "T_min": T0, "E_fast": E0, "T_a": a["T"], "E_a": a["E"], "vcap_a": a["vcap"],
               "E_coast": None if b2 is None else b2["E"], "T_coast": None if b2 is None else b2["T"], "xc": None if b2 is None else b2["xc"],
               "E_dp": sol["E"] if ok else None, "T_dp": sol["T"] if ok else None}
        if ok:
            ph = E.phases_from_kind(sol["kind"])
            rec["coast_share_dp"] = 100.0 * sum(1 for p in ph if p == "coast") / len(ph)
            rec["balance_dp"] = E.balance(prof, dp.dx, sol["v"], sol["F"])
        rec["balance_fast"] = fast_bal
        rows.append(rec)
    return rows


def main():
    t0 = time.time()
    jobs = [(typ, seed, C.SWEEP_RESERVES, False) for typ in C.PROFILE_TYPES for seed in C.SWEEP_SEEDS]
    jobs += [(typ, seed, (C.REGEN_SWEEP_RESERVE,), True) for typ in C.REGEN_SWEEP_TYPES for seed in C.REGEN_SWEEP_SEEDS]
    with ProcessPoolExecutor(max_workers=6) as ex:
        rows = [r for chunk in ex.map(one, jobs, chunksize=2) for r in chunk]
    res = {"meta": {"seeds": [C.SWEEP_SEEDS.start, C.SWEEP_SEEDS.stop], "reserves": list(C.SWEEP_RESERVES), "types": list(C.PROFILE_TYPES), "dp_dx": C.DP_DX, "dp_dv": C.DP_DV, "fb_h": C.FB_H,
                    "regen_seeds": [C.REGEN_SWEEP_SEEDS.start, C.REGEN_SWEEP_SEEDS.stop], "regen_types": list(C.REGEN_SWEEP_TYPES), "regen_reserve": C.REGEN_SWEEP_RESERVE}, "rows": rows}
    out = ROOT / C.RESULTS_FILE
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, separators=(",", ":")), encoding="utf-8")
    print("geschrieben:", out, round(out.stat().st_size / 1024), "KB,", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
