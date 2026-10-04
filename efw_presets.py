"""SETTING_SPECS-Permalink-Muster, Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio).
Alle Regler sind immer sichtbar mit festen Grenzen - kein ausblendbarer Regler, kein KEPT-Muster."""

import random
from dataclasses import dataclass

import streamlit as st

import efw_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    options: tuple | None = None
    lo: int | None = None
    hi: int | None = None


SETTING_SPECS = {
    "reserve_slider": SettingSpec("reserve", float, C.DEFAULT_RESERVE),
    "profile_select": SettingSpec("profile", str, C.DEFAULT_PROFILE, C.PROFILE_TYPES),
    "regen_select": SettingSpec("regen", str, C.DEFAULT_REGEN, C.REGEN_OPTIONS),
    "seed_input": SettingSpec("seed", int, C.DEFAULT_SEED, None, C.SEED_MIN, C.SEED_MAX),
    "view_select": SettingSpec("view", str, C.DEFAULT_VIEW, C.VIEW_OPTIONS),
}
PRESET_KEYS = {"reserve": "reserve_slider", "profile": "profile_select", "regen": "regen_select", "seed": "seed_input"}


def snap_reserve(value: float) -> float:
    """Reserve auf das Raster 2,5 / 5 / ... / 20 einrasten (Gleichstand: der kleinere Wert); Ganzzahl-Arithmetik in Hundertstel-Prozent gegen Gleitkomma-Rauschen."""
    lo, step = int(round(C.RESERVE_MIN * 100)), int(round(C.RESERVE_STEP * 100))
    v = max(lo, min(int(round(C.RESERVE_MAX * 100)), int(round(value * 100))))
    q, r = divmod(v - lo, step)
    return (lo + step * (q + (1 if 2 * r > step else 0))) / 100.0


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def load_permalink_settings():
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            try:
                value = spec.caster(qp[spec.url_param])
                if state_key == "reserve_slider":
                    value = snap_reserve(value)
                elif spec.caster is str:
                    if value not in spec.options:
                        continue
                else:
                    value = max(spec.lo, min(spec.hi, value))
                st.session_state[state_key] = value
            except (ValueError, TypeError):
                pass
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    for key, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name][key]


def randomize_seed():
    st.session_state["seed_input"] = random.randint(C.SEED_MIN, C.SEED_MAX)


def settings_from_state(values: dict) -> dict:
    return {"reserve": float(values["reserve_slider"]), "profile": str(values["profile_select"]), "regen": str(values["regen_select"]), "seed": int(values["seed_input"])}
