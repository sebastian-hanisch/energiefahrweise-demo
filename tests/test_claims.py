"""Jede Zahl aus dem README wird hier aus data/efw_results.json nachgerechnet; die formatierten Texte müssen im README stehen.

30 Profile je Typ (Seeds 100-129), Mittel ± Standardfehler, Reserve 10 % wo nicht anders angegeben; mit Rückspeisung 8 Profile je Typ.
"""
from pathlib import Path

import pytest

import efw_constants as C
import efw_evaluation as E
import efw_results as R
import efw_stories as S

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def res():
    return R.load_results()


@pytest.fixture(scope="module")
def s10(res):
    return {t: R.summary(res, t, 10.0) for t in res["meta"]["types"]}


def pm(x, se):
    return f"**{x:.1f} ± {se:.1f} %**"


def test_meta_and_counts(res):
    assert res["meta"]["types"] == list(C.PROFILE_TYPES) and res["meta"]["reserves"] == list(C.SWEEP_RESERVES) and res["meta"]["seeds"] == [100, 130]
    for t in C.PROFILE_TYPES:
        for r in C.SWEEP_RESERVES:
            assert len(R.rows_of(res, t, r)) == 30 and R.summary(res, t, r)["n_coast"] == 30 and R.summary(res, t, r)["n_dp"] == 30
    assert len(res["rows"]) == 5 * 30 * 5 + 2 * 8 and "Port 8971" in README
    assert "Seeds 100–129" in README and "30 Profile je Typ" in README


def test_the_table_in_the_readme(s10):
    for t, name in (("flach", "flach"), ("wellig", "wellig"), ("rampe", "rampe"), ("tempolimit", "tempolimit"), ("gefaelle", "gefaelle")):
        s = s10[t]
        line = f"| {name} | {pm(s['saving_a'], s['saving_a_se'])} | {pm(s['saving_coast'], s['saving_coast_se'])} | {pm(s['saving_dp'], s['saving_dp_se'])} | {pm(s['dp_vs_coast'], s['dp_vs_coast_se'])} |"
        assert line.replace("**−0.0", "**-0.0").replace("−", "-") in README.replace("−", "-"), line


def test_the_formula_in_the_readme(s10):
    f = E.formula_saving(10.0)
    assert f"sagt bei 10 % **{f:.1f} %** voraus" in README
    flat = s10["flach"]
    assert f"Sie liegt **{abs(flat['dev_a']):.1f} Punkte** neben der Messung ({f:.1f} gegen {flat['saving_a']:.1f} %)" in README
    assert f"bis auf {abs(flat['dev_a']):.1f} Punkte".replace(".", ",") in README


def test_the_optimum_against_the_formula_in_the_readme(s10):
    dev = {t: -s10[t]["dev_dp"] for t in s10}
    assert (f"auf flacher Strecke **{dev['flach']:.1f} Punkte** mehr als die Formel, bei welligem Profil **{dev['wellig']:.1f}**, mit Rampe **{dev['rampe']:.1f}**, bei Tempolimit **{dev['tempolimit']:.1f}** "
            f"und im Gefälle **{dev['gefaelle']:.1f} Punkte**") in README
    assert f"spart 8,2 bis 40,5 Punkte mehr (bei 10 % Reserve)" in README and f"{min(dev.values()):.1f}" == "8.2" and f"{max(dev.values()):.1f}" == "40.5"
    assert all(d > 8.0 for d in dev.values())


def test_the_curve_in_the_readme(res):
    r25, r10 = R.summary(res, "flach", 2.5), R.summary(res, "flach", 10.0)
    assert f"die ersten 2,5 % Reserve **{r25['saving_dp']:.1f} %** (Formel: **{r25['formula']:.1f} %**); die nächsten 7,5 % bringen nur weitere {round(r10['saving_dp'] - r25['saving_dp'])} Punkte" in README


def test_the_energy_loss_in_the_readme(s10):
    f, w = s10["flach"], s10["wellig"]
    assert f"**{f['brake_fast']:.0f} %** der eingesetzten Energie (flach) bzw. **{w['brake_fast']:.0f} %** (wellig)" in README and f"auf **{f['coast_share']:.0f} %** der Länge" in README
    assert f["brake_fast"] > 50 and w["brake_fast"] > f["brake_fast"]


def test_where_the_simple_rule_is_enough_in_the_readme(s10):
    worst = max(abs(s10[t]["dp_vs_coast"]) for t in ("flach", "rampe"))
    assert f"höchstens **{worst:.1f} %** neben der Rollpunkt-Regel" in README and worst < 0.5
    assert s10["wellig"]["dp_vs_coast"] > 4 and s10["tempolimit"]["dp_vs_coast"] > 8 and s10["gefaelle"]["dp_vs_coast"] > 25


def test_regeneration_in_the_readme(res, s10):
    f, w = R.regen_summary(res, "flach"), R.regen_summary(res, "wellig")
    assert (f"auf flacher Strecke von **{s10['flach']['dp_vs_a']:.1f} %** auf **{f['dp_vs_a']:.1f} %**, bei welligem Profil von **{s10['wellig']['dp_vs_a']:.1f} %** auf **{w['dp_vs_a']:.1f} %**" in README)
    assert f["n"] == 8 == w["n"] and f["dp_vs_a"] < 0.6 * s10["flach"]["dp_vs_a"] and w["dp_vs_a"] < 0.6 * s10["wellig"]["dp_vs_a"]


def test_every_trip_in_the_sweep_meets_its_budget(res):
    for r in res["rows"]:
        tb = r["T_min"] * (1 + r["reserve"] / 100)
        assert r["T_a"] <= tb + 1e-6 and r["T_dp"] <= tb + 1e-6 and (r["T_coast"] is None or r["T_coast"] <= tb + 1e-6)
        assert r["E_dp"] < r["E_fast"] and r["E_a"] < r["E_fast"]


def test_the_energy_falls_monotonically_with_the_reserve(res):
    for t in C.PROFILE_TYPES:
        for key in ("a", "coast", "dp"):
            c = R.curve(res, t, key)
            assert all(a < b for a, b in zip(c, c[1:])), (t, key)


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_every_preset_tells_its_story_on_the_shown_profile(res, name):
    p = C.PRESETS[name]
    settings = {"reserve": p["reserve"], "profile": p["profile"], "regen": p["regen"], "seed": p["seed"]}
    run = E.run_live(settings)
    ref = run if p["regen"] == "aus" else E.run_live({**settings, "regen": "aus"})
    failed = [text for _, text, ok in S.check(name, S.facts_for(run, ref, res, settings)) if not ok]
    assert not failed, (name, failed)
