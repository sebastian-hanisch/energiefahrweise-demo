"""Fehler-Einbau-Test: baut einzelne Fehler in die Module ein und prüft, ob die Tests (ohne AppTests) sie finden.

Aufruf (im Projektordner): python tools/mutation_check.py [Teilstring des Dateinamens] [--jobs N] [--indices 5,8-12] [--with-app] [--dry-run]
Jeder Mutant ersetzt genau eine Stelle; Überlebende sind entweder gleichwertig (kein sichtbarer Unterschied) oder eine Lücke der Tests. Die Kopie liegt je Mutant in einem
temporären Ordner; PYTHONDONTWRITEBYTECODE=1, damit veralteter Bytecode keine Überlebenden vortäuscht; Quelltexte als LF. Ein Mutant kann in eine Endlosschleife laufen;
nach TIMEOUT Sekunden gilt er als gefunden. `--with-app` nimmt die AppTests hinzu, `--dry-run` prüft nur, ob jede Zeichenkette genau einmal vorkommt."""
import concurrent.futures
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable
WITH_APP = "--with-app" in sys.argv
TIMEOUT = 600
TEST_ORDER = ["test_rng.py", "test_track.py", "test_physics.py", "test_results.py", "test_presets.py", "test_evaluation.py", "test_stories.py", "test_gaps.py", "test_pdf.py", "test_strategies.py",
              "test_claims.py", "test_dp.py"]

MUTANTS = [
    ('efw_track.py', '    return (lo + rng.below(hi - lo + 1)) / 10.0', '    return (lo + rng.below(hi - lo)) / 10.0'),
    ('efw_track.py', '    z = (sum(rng.below(1000) for _ in range(12)) - 6000) / 1000.0', '    z = (sum(rng.below(1000) for _ in range(12)) - 5000) / 1000.0'),
    ('efw_track.py', '        ln = lo_len + rng.below(hi_len - lo_len + 1)', '        ln = lo_len + rng.below(hi_len - lo_len)'),
    ('efw_track.py', '        grad = grad - grad.mean()', '        grad = grad - 0.0'),
    ('efw_track.py', '        s = 6 + rng.below(n - ln - 10)', '        s = 2 + rng.below(n - ln - 10)'),
    ('efw_track.py', '            lim[s:s + ln] = min(lim[s], float((20, 25, 30)[rng.below(3)]))', '            lim[s:s + ln] = min(lim[s], float((20, 25, 30)[rng.below(2)]))'),
    ('efw_track.py', '    return C.MASS * C.G_ACC * np.sin(np.arctan(grad / 1000.0)), lim', '    return C.MASS * C.G_ACC * np.sin(np.arctan(grad / 100.0)), lim'),
    ('efw_physics.py', '    vavg = (vi + 4.0 * vm + vj) / 6.0', '    vavg = (vi + vm + vj) / 3.0'),
    ('efw_physics.py', '    return C.RES_A + C.RES_B * vavg + C.RES_C * (wi + wj) / 2.0', '    return C.RES_A + C.RES_B * vavg + C.RES_C * (wi + wj)'),
    ('efw_physics.py', '    F = MASS_EFF * a + resist(vi, vj) + G\n    vm = np.sqrt((wi + wj) / 2.0)', '    F = C.MASS * a + resist(vi, vj) + G\n    vm = np.sqrt((wi + wj) / 2.0)'),
    ('efw_physics.py', '    feas = ((a >= -C.DECEL - 1e-9) & (Fmid <= cap + 1.0)', '    feas = ((a >= -2 * C.DECEL - 1e-9) & (Fmid <= cap + 1.0)'),
    ('efw_physics.py', '    E = (np.maximum(F, 0.0) - eta * np.maximum(-F, 0.0)) * dx / 1e6', '    E = (np.maximum(F, 0.0) + eta * np.maximum(-F, 0.0)) * dx / 1e6'),
    ('efw_physics.py', '            wj = wi - 2.0 * C.DECEL * dx', '            wj = wi - C.DECEL * dx'),
    ('efw_physics.py', '        if mode == "coast":\n            E = E * 0.0', '        if mode == "coast":\n            E = E * 1.0'),
    ('efw_physics.py', '        feas = feas & (wj >= vmin * vmin) & (vi > 0)', '        feas = feas & (vi > 0)'),
    ('efw_physics.py', '    jlo = np.clip(np.floor(vj / dv + 1e-9).astype(int), 0, nv - 2)', '    jlo = np.clip(np.floor(vj / dv + 1e-9).astype(int), 1, nv - 2)'),
    ('efw_physics.py', '        E += max(e, 0.0) if F > 0 else 0.0', '        E += max(e, 0.0)'),
    ('efw_dp.py', '        allowed[N, 0] = True                                      # Start und Ziel stehen', '        allowed[N, 0] = False                                      # Start und Ziel stehen'),
    ('efw_dp.py', '        nl[1:N] = np.minimum(lim[:-1], lim[1:])', '        nl[1:N] = np.maximum(lim[:-1], lim[1:])'),
    ('efw_dp.py', '            best = (self.Eb[k] + lam * self.Tb[k] + Vn[None, :]).min(axis=1)', '            best = (self.Eb[k] + self.Tb[k] + Vn[None, :]).min(axis=1)'),
    ('efw_dp.py', '                kind[k] = KIND_BRAKE if F[j] < 0 else KIND_DRIVE', '                kind[k] = KIND_DRIVE'),
    ('efw_dp.py', '        hi = 4.0\n        res_hi = self.trace(hi)', '        hi = 400.0\n        res_hi = self.trace(hi)'),
    ('efw_dp.py', '            if r["ok"] and r["T"] <= Tb:\n                hi = mid', '            if r["ok"] and r["T"] >= Tb:\n                hi = mid'),
    ('efw_dp.py', '                Fc[k] = float(Fs) if mode != "coast" else 0.0', '                Fc[k] = float(Fs)'),
    ('efw_strategies.py', '            c2 = min(nll[i + 1], vcap) ** 2', '            c2 = max(nll[i + 1], vcap) ** 2'),
    ('efw_strategies.py', '        ab2 = 2.0 * C.DECEL * h', '        ab2 = C.DECEL * h'),
    ('efw_strategies.py', '                    F = C.F_MAX if vm * C.F_MAX < C.P_MAX else C.P_MAX / max(vm, 1e-9)', '                    F = C.F_MAX'),
    ('efw_strategies.py', '                    wj = w - 2.0 * h * (R + G) / MASS_EFF\n                    if wj < 0.25:', '                    wj = w - 2.0 * h * R / MASS_EFF\n                    if wj < 0.25:'),
    ('efw_strategies.py', '        if T >= Tb:\n            return {"vcap": vmax, "T": T, "E": E}', '        if T > Tb:\n            return {"vcap": vmax, "T": T, "E": E}'),
    ('efw_strategies.py', '            if t > Tb:\n                lo = mid\n            else:\n                hi = mid\n        t, e = self.run(hi)', '            if t < Tb:\n                lo = mid\n            else:\n                hi = mid\n        t, e = self.run(hi)'),
    ('efw_strategies.py', '        if T_end > Tb + 1e-9:\n            return None', '        if T_end > Tb + 1e9:\n            return None'),
    ('efw_strategies.py', '        if T_lo < Tb:\n            return None', '        if T_lo > Tb:\n            return None'),
    ('efw_evaluation.py', '    return 100.0 * (1.0 - 1.0 / (1.0 + r) ** 2)', '    return 100.0 * (1.0 - 1.0 / (1.0 + r))'),
    ('efw_evaluation.py', '    return ["brake" if f < -COAST_F else "coast" if abs(f) <= COAST_F else "drive" for f in F]', '    return ["brake" if f < -COAST_F else "coast" if abs(f) < COAST_F / 2 else "drive" for f in F]'),
    ('efw_evaluation.py', '    supply = b["traction"] + max(-b["lift"], 0.0)\n    return 100.0 * b["brake"] / supply if supply else float("nan")\n\n\ndef messages', '    supply = b["traction"]\n    return 100.0 * b["brake"] / supply if supply else float("nan")\n\n\ndef messages'),
    ('efw_evaluation.py', '    return 100.0 * (1.0 - run["results"][key]["E"] / run["results"]["fast"]["E"])', '    return 100.0 * (1.0 - run["results"]["fast"]["E"] / run["results"][key]["E"])'),
    ('efw_evaluation.py', '    return 100.0 * (1.0 - run["results"]["dp"]["E"] / run["results"][ref]["E"])', '    return 100.0 * (1.0 - run["results"][ref]["E"] / run["results"]["dp"]["E"])'),
    ('efw_evaluation.py', '    Tb = T0 * (1.0 + reserve / 100.0)', '    Tb = T0 * (1.0 + reserve / 10.0)'),
    ('efw_evaluation.py', '    eta = C.REGEN_ETA if settings["regen"] == "mit" else 0.0', '    eta = 0.0'),
    ('efw_evaluation.py', '    if abs(gap) < 1.0:', '    if abs(gap) < 2.0:'),
    ('efw_evaluation.py', 'if s_dp - s_naive >= 10.0 else "info"', 'if s_dp - s_naive >= 20.0 else "info"'),
    ('efw_results.py', '    out["dev_a"], out["dev_a_se"] = mean_se(form - saving(r, "a") for r in rows)', '    out["dev_a"], out["dev_a_se"] = mean_se(saving(r, "a") - form for r in rows)'),
    ('efw_results.py', '    return 100.0 * (1.0 - row[f"E_{key}"] / row[f"E_{ref}"])', '    return 100.0 * (1.0 - row[f"E_{ref}"] / row[f"E_{key}"])'),
    ('efw_results.py', '    ok_coast = [r for r in rows if r["E_coast"] is not None]', '    ok_coast = rows'),
    ('efw_results.py', '    return [r for r in res["rows"] if r["type"] == typ and abs(r["reserve"] - reserve) < 1e-9 and bool(r["regen"]) == regen]', '    return [r for r in res["rows"] if r["type"] == typ and abs(r["reserve"] - reserve) < 1e-9]'),
    ('efw_presets.py', '    q, r = divmod(v - lo, step)\n    return (lo + step * (q + (1 if 2 * r > step else 0))) / 100.0', '    q, r = divmod(v - lo, step)\n    return (lo + step * (q + (1 if 2 * r >= step else 0))) / 100.0'),
    ('efw_presets.py', '                    if value not in spec.options:', '                    if False:'),
    ('efw_stories.py', 'lambda f: f["dp_vs_coast"] >= 3.0)', 'lambda f: f["dp_vs_coast"] > 3.0)'),
    ('efw_stories.py', 'lambda f: abs(f["dp_vs_coast"]) < 1.0),\n        ("coast_saves"', 'lambda f: abs(f["dp_vs_coast"]) <= 1.0),\n        ("coast_saves"'),
    ('efw_visualization.py', '        vs += [v[k] * 3.6, v[k + 1] * 3.6, None]', '        vs += [v[k], v[k + 1], None]'),
    ('efw_visualization.py', 'marker_color=["#c77700" if g > 0 else "#2a6fb0" for g in prof["grad"]]', 'marker_color=["#2a6fb0" if g > 0 else "#c77700" for g in prof["grad"]]'),
    ('efw_visualization.py', '        xs += [k * C.UNIT_M / 1000.0, (k + 1) * C.UNIT_M / 1000.0]', '        xs += [k * C.UNIT_M, (k + 1) * C.UNIT_M]'),
    ('efw_pdf_export.py', '            out[-1] = (p, out[-1][1], x[k + 1] / 1000.0, out[-1][3], v[k + 1] * 3.6)', '            out[-1] = (p, out[-1][1], x[k + 1] / 1000.0, out[-1][3], out[-1][4])'),
]


def check_unique():
    bad = []
    for n, (name, old, new) in enumerate(MUTANTS, 1):
        text = (ROOT / name).read_bytes().decode("utf-8").replace("\r\n", "\n")
        if text.count(old) != 1:
            bad.append((n, name, old[:70], text.count(old)))
        if old == new:
            bad.append((n, name, "alt == neu", 0))
    return bad


def run_one(args):
    n, name, old, new, base = args
    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"abl_mut{n}_"))
    try:
        shutil.copytree(base, tmp, dirs_exist_ok=True)
        path = tmp / name
        original = path.read_bytes().decode("utf-8")
        path.write_bytes(original.replace(old, new).encode("utf-8"))
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        files = [f"tests/{f}" for f in TEST_ORDER + (["test_app.py"] if WITH_APP else [])]
        try:
            r = subprocess.run([PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *files], cwd=tmp, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT)
            return n, name, old, new, r.returncode == 0, False
        except subprocess.TimeoutExpired:
            return n, name, old, new, False, True                 # Endlosschleife oder zu langsam: gilt als gefunden
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = args[0] if args else ""
    jobs = 6
    if "--jobs" in sys.argv:
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1])
        only = "" if only == str(jobs) else only
    wanted = None
    if "--indices" in sys.argv:
        spec = sys.argv[sys.argv.index("--indices") + 1]
        only = "" if only == spec else only
        wanted = set()
        for part in spec.split(","):
            lo, _, hi = part.partition("-")
            wanted.update(range(int(lo), int(hi or lo) + 1))
    bad = check_unique()
    for b in bad:
        print("FEHLER (Stelle nicht eindeutig gefunden):", b)
    if "--dry-run" in sys.argv:
        print(f"{len(MUTANTS)} Mutanten, {len(bad)} Fehler in der Mutantenliste")
        return
    base = pathlib.Path(tempfile.mkdtemp(prefix="abl_mut_base_"))
    for f in ROOT.glob("*.py"):
        (base / f.name).write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    shutil.copytree(ROOT / "tests", base / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(ROOT / "README.md", base / "README.md")
    shutil.copytree(ROOT / "data", base / "data")
    for f in (base / "tests").glob("*.py"):
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n"))
    bad_ids = {b[0] for b in bad}
    work = [(n, name, old, new, base) for n, (name, old, new) in enumerate(MUTANTS, 1) if n not in bad_ids and (not only or only in name) and (wanted is None or n in wanted)]
    survivors, killed = [], 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        for n, name, old, new, survived, timeout in pool.map(run_one, work):
            if timeout:
                print(f"[{n:3d}] Zeitüberschreitung (als gefunden gezählt)  {name}", flush=True)
            if survived:
                survivors.append((n, name, old[:70], new[:70]))
                print(f"[{n:3d}] ÜBERLEBT  {name}: {old[:70]!r} -> {new[:70]!r}", flush=True)
            else:
                killed += 1
                print(f"[{n:3d}] gefunden  {name}", flush=True)
    print(f"\n{killed} gefunden, {len(survivors)} überlebt, {len(bad)} Fehler in der Mutantenliste")
    shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    main()
