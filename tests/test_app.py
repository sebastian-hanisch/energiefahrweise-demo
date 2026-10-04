"""AppTest-Rauchtests: Voreinstellung, jedes Preset, Randwerte, Würfel-Knopf, Permalink, Abschnitte, Nachprüfen-Tab, Footer."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import efw_constants as C

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _run(**state):
    at = AppTest.from_file(APP, default_timeout=300)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def _ok(at):
    assert not at.exception, [e.value for e in at.exception]


def _has_metric(at, label):
    return any(m.label == label for m in at.metric)


def _texts(at):
    return [x.value for x in list(at.success) + list(at.info) + list(at.warning)]


def test_default_run_has_no_exception_and_shows_the_four_methods():
    at = _run()
    _ok(at)
    for key in C.METHODS:
        assert _has_metric(at, C.METHOD_LABELS[key]), key
    s = at.session_state
    assert (s["reserve_slider"], s["profile_select"], s["regen_select"], s["seed_input"]) == (10.0, "wellig", "aus", 500)
    assert any("Bei 10 % Fahrzeitreserve spart gleichmäßiges Langsamfahren" in t for t in _texts(at)) and any("v²-Formel sagt 17 % voraus" in t for t in _texts(at))


@pytest.mark.parametrize("name", C.PRESET_ORDER)
def test_every_preset_button_runs_and_sets_the_controls(name):
    at = _run()
    next(b for b in at.button if b.key == f"preset_{name}").click().run()
    _ok(at)
    p = C.PRESETS[name]
    s = at.session_state
    assert (s["reserve_slider"], s["profile_select"], s["regen_select"], s["seed_input"]) == (p["reserve"], p["profile"], p["regen"], p["seed"]) and _has_metric(at, C.METHOD_LABELS["dp"])


def test_flat_preset_says_the_simple_rule_is_enough_and_the_regeneration_preset_mentions_it():
    at = _run()
    next(b for b in at.button if b.key == "preset_Flache Strecke").click().run()
    _ok(at)
    assert any("Hier genügt die einfache Rollpunkt-Regel" in t for t in _texts(at))
    next(b for b in at.button if b.key == "preset_Mit Rückspeisung").click().run()
    _ok(at)
    assert any("Mit Rückspeisung (60 %)" in t for t in _texts(at))


@pytest.mark.parametrize("kw", [dict(reserve_slider=2.5), dict(reserve_slider=20.0), dict(profile_select="flach"), dict(profile_select="rampe"), dict(profile_select="tempolimit"),
                                 dict(profile_select="gefaelle"), dict(regen_select="mit"), dict(seed_input=C.SEED_MIN), dict(seed_input=C.SEED_MAX), dict(view_select="naive"), dict(view_select="coast")])
def test_extreme_settings_run(kw):
    _ok(_run(**kw))


def test_other_settings_change_the_result():
    std, flat = _run(), _run(profile_select="flach")
    assert [m.value for m in std.metric][:4] != [m.value for m in flat.metric][:4]


def test_dice_button_changes_the_seed():
    at = _run()
    old = at.session_state["seed_input"]
    next(b for b in at.button if b.label == "🎲 Neues Profil würfeln").click().run()
    _ok(at)
    assert at.session_state["seed_input"] != old


def test_permalink_values_are_clamped_and_snapped():
    at = AppTest.from_file(APP, default_timeout=300)
    for k, v in (("reserve", "11.3"), ("profile", "rampe"), ("regen", "mit"), ("seed", "99999"), ("view", "coast")):
        at.query_params[k] = v
    at.run()
    _ok(at)
    s = at.session_state
    assert (s["reserve_slider"], s["profile_select"], s["regen_select"], s["seed_input"], s["view_select"]) == (12.5, "rampe", "mit", C.SEED_MAX, "coast")


def test_permalink_ignores_garbage_and_roundtrips():
    at = AppTest.from_file(APP, default_timeout=300)
    at.query_params["reserve"] = "viel"
    at.query_params["profile"] = "berg"
    at.query_params["view"] = "xyz"
    at.run()
    _ok(at)
    s = at.session_state
    assert s["reserve_slider"] == C.DEFAULT_RESERVE and s["profile_select"] == C.DEFAULT_PROFILE and s["view_select"] == C.DEFAULT_VIEW
    next(b for b in at.button if b.key == "preset_Mit Rückspeisung").click().run()
    qp = at.query_params
    at2 = AppTest.from_file(APP, default_timeout=300)
    for k in ("reserve", "profile", "regen", "seed", "view"):
        v = qp[k]
        at2.query_params[k] = v[0] if isinstance(v, list) else v
    at2.run()
    _ok(at2)
    assert at2.session_state["regen_select"] == "mit" and at2.session_state["profile_select"] == "flach"


def test_sections_expanders_and_charts_are_present():
    at = _run()
    _ok(at)
    headers = [s.value for s in at.subheader] + [m.value for m in at.markdown]
    assert any("Was die Messreihe zeigt" in h for h in headers) and any("Was spart das Rollen" in h for h in headers) and any("Die Fahrt im Detail" in h for h in headers)
    titles = [e.label for e in at.expander]
    assert "🔧 Wie wir das erreichen – vollständiger Methodenvergleich" in titles and "Wie funktioniert diese Demo?" in titles and "📐 Mathematische Formulierung" in titles
    assert [t.label for t in at.tabs] == ["🚆 Fahrweisen", "🧪 Optimum nachprüfen", "📈 Messreihe"]
    assert len(at.get("plotly_chart")) == 6          # Energie, Bilanz, Geschwindigkeit, Messreihe: Kurve, Typen, Lücke


def test_replay_tab_reproduces_the_optimum():
    at = _run(profile_select="flach")
    _ok(at)
    next(b for b in at.button if b.key == "replay_button").click().run()
    _ok(at)
    assert _has_metric(at, "Zeitunterschied") and _has_metric(at, "größte Verzögerung")
    m = {x.label: x.value for x in at.metric}
    assert float(m["Zeitunterschied"].split()[0]) < 0.5 and float(m["Energieunterschied"].split()[0]) < 0.5 and float(m["Endgeschwindigkeit"].split()[0]) < 0.05
    at.select_slider(key="profile_select").set_value("rampe").run()
    assert not _has_metric(at, "Zeitunterschied") and any("erneut nachfahren" in c.value for c in at.caption)


def test_seed_control_uses_the_portfolio_wording():
    assert [n.label for n in _run().number_input] == ["Zufalls-Seed"]


def test_related_demos_are_linked_and_footer_is_present():
    at = _run()
    text = " ".join(c.value for c in at.caption)
    for name in ("taktfahrplan-demo", "fahrzeitreserve-demo", "streckenkonflikt-demo", "slow-steaming-demo"):
        assert name in text
    assert "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net)" in text
    assert "geplant" not in text and "noch nicht" not in text
