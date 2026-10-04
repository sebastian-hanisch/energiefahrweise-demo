"""Permalink-Einrasten, Presets und Konstanten-Konsistenz."""
import efw_constants as C
import efw_presets as PR


def test_snap_reserve_clamps_and_rounds_half_down():
    assert PR.snap_reserve(10.0) == 10.0 and PR.snap_reserve(11.2) == 10.0 and PR.snap_reserve(11.3) == 12.5 and PR.snap_reserve(100.0) == 20.0 and PR.snap_reserve(-3.0) == 2.5
    assert PR.snap_reserve(3.75) == 2.5 and PR.snap_reserve(3.8) == 5.0 and PR.snap_reserve(6.25) == 5.0 and PR.snap_reserve(2.5) == 2.5 and PR.snap_reserve(17.5) == 17.5


def test_every_preset_sets_every_control_with_valid_values():
    assert set(C.PRESET_ORDER) == set(C.PRESETS) == set(C.PRESET_HELP) and len(C.PRESET_ORDER) == 6
    for name, p in C.PRESETS.items():
        assert set(p) == set(PR.PRESET_KEYS)
        assert C.RESERVE_MIN <= p["reserve"] <= C.RESERVE_MAX and PR.snap_reserve(p["reserve"]) == p["reserve"] and p["profile"] in C.PROFILE_TYPES and p["regen"] in C.REGEN_OPTIONS
        assert C.SEED_MIN <= p["seed"] <= C.SEED_MAX and not (C.SWEEP_SEEDS.start <= p["seed"] < C.SWEEP_SEEDS.stop), name


def test_each_non_standard_preset_changes_the_lever_it_is_named_for():
    std = C.PRESETS["Standard"]
    changed = {n: sorted(k for k in std if k != "seed" and C.PRESETS[n][k] != std[k]) for n in C.PRESET_ORDER if n != "Standard"}
    assert changed == {"Flache Strecke": ["profile"], "Rampe": ["profile"], "Tempolimit": ["profile"], "Starkes Gefälle": ["profile"], "Mit Rückspeisung": ["profile", "regen"]}
    assert len({p["seed"] for p in C.PRESETS.values()}) == 1 and std["seed"] == C.DEFAULT_SEED
    assert C.PRESETS["Mit Rückspeisung"]["profile"] == "flach" and C.PRESETS["Standard"]["reserve"] in C.SWEEP_RESERVES


def test_options_labels_and_colors_are_complete():
    assert set(C.PROFILE_LABELS) == set(C.PROFILE_TYPES) and set(C.REGEN_LABELS) == set(C.REGEN_OPTIONS) and set(C.VIEW_OPTIONS) <= set(C.METHODS)
    assert set(C.METHOD_LABELS) == set(C.METHODS) and set(C.METHOD_COLORS) == set(C.METHODS) | {"formula"} and set(C.PHASE_COLORS) == {"drive", "coast", "brake", "hold"}
    assert C.DEFAULT_RESERVE in C.SWEEP_RESERVES and C.DEFAULT_PROFILE in C.PROFILE_TYPES and C.DEFAULT_VIEW in C.VIEW_OPTIONS


def test_settings_convert():
    s = PR.settings_from_state({"reserve_slider": 10, "profile_select": "wellig", "regen_select": "aus", "seed_input": 500.0})
    assert s == {"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 500} and isinstance(s["reserve"], float)
