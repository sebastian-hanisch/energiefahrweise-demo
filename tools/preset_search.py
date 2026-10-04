"""Sucht einen Seed außerhalb der Messreihen-Seeds, bei dem alle Abnahmekriterien aller Presets gelten, und schreibt den Messbericht nach tools/PRESET_SWEEP.md.

  python tools/preset_search.py [Anzahl Seeds (Standard 30)]
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import efw_constants as C  # noqa: E402
import efw_evaluation as E  # noqa: E402
import efw_results as R  # noqa: E402
import efw_stories as S  # noqa: E402

START = 500


def evaluate(seed):
    res = R.load_results()
    out = {}
    for name in C.PRESET_ORDER:
        p = C.PRESETS[name]
        settings = {"reserve": p["reserve"], "profile": p["profile"], "regen": p["regen"], "seed": seed}
        run = E.run_live(settings)
        ref = run if p["regen"] == "aus" else E.run_live({**settings, "regen": "aus"})
        out[name] = S.check(name, S.facts_for(run, ref, res, settings))
    return seed, out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    with ProcessPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(evaluate, range(START, START + n)))
    lines = ["# Preset-Abstimmung (tools/preset_search.py)", "", f"Seeds {START}..{START + n - 1}, außerhalb der Messreihen-Seeds ({C.SWEEP_SEEDS.start}-{C.SWEEP_SEEDS.stop - 1}). "
             "Jedes Preset zeigt das Profil seines Typs zu diesem Seed; ein Seed besteht, wenn alle Kriterien aller Presets gelten (`efw_stories.py`).", ""]
    good = [seed for seed, out in results if all(c for name in out for _, _, c in out[name])]
    lines += [f"Bestanden: {len(good)} von {len(results)} Seeds: {good}", ""]
    for name in C.PRESET_ORDER:
        fails = {}
        for _, out in results:
            for cid, _, ok in out[name]:
                fails[cid] = fails.get(cid, 0) + (not ok)
        lines.append(f"- {name}: durchgefallen je Kriterium " + ", ".join(f"{k} {v}x" for k, v in fails.items()))
    if good:
        lines += ["", f"Gewählt: Seed {good[0]}."]
    (ROOT / "tools" / "PRESET_SWEEP.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("bestanden:", good)


if __name__ == "__main__":
    main()
