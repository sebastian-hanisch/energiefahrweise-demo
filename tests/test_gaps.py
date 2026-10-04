"""Diagramm-Werte, Phasenstücke und feste Achsen der Figuren."""
import numpy as np
import pytest

import efw_constants as C
import efw_evaluation as E
import efw_results as R
import efw_visualization as V
from test_evaluation import fake
from test_results import RES


def run():
    r = fake()
    r["profile"] = {"grad": np.array([1.0, -2.0, 0.0] + [0.0] * 37), "lim": np.array([40.0] * 10 + [25.0] * 5 + [40.0] * 25), "L": 20000.0}
    for key, e in r["results"].items():
        e["x"] = [0.0, 250.0, 500.0, 750.0, 1000.0]
        e["v"] = [0.0, 10.0, 20.0, 20.0, 0.0]
        e["phase"] = ["drive", "drive", "coast", "brake"]
    r["results"]["dp"]["phase"] = ["drive", "coast", "drive", "brake"]
    return r


def test_phase_segments_collect_cells_with_gaps_between_stretches():
    segs = V.phase_segments(run()["results"]["fast"])
    assert segs["drive"] == ([0.0, 0.25, None, 0.25, 0.5, None], [0.0, 36.0, None, 36.0, 72.0, None])
    assert segs["coast"][0] == [0.5, 0.75, None] and segs["coast"][1] == [72.0, 72.0, None] and segs["brake"][0] == [0.75, 1.0, None] and segs["brake"][1] == [72.0, 0.0, None]
    split = V.phase_segments(run()["results"]["dp"])
    assert split["drive"][0] == [0.0, 0.25, None, 0.5, 0.75, None]


def test_speed_profile_has_reference_limit_phases_and_gradient():
    fig = V.build_speed_profile(run(), "dp")
    names = [t.name for t in fig.data]
    assert names == ["schnellste Fahrt", "Tempolimit", "Antrieb / Halten", "Rollen", "Bremsen", "Steigung"]
    lim = next(t for t in fig.data if t.name == "Tempolimit")
    assert list(lim.y)[:2] == [144.0, 144.0] and 90.0 in list(lim.y) and list(lim.x)[0] == 0.0 and list(lim.x)[-1] == 20.0
    grad = fig.data[-1]
    assert len(grad.y) == 40 and list(grad.y)[:3] == [1.0, -2.0, 0.0] and grad.marker.color[0] == "#c77700" and grad.marker.color[1] == "#2a6fb0"
    assert [t.name for t in V.build_speed_profile(run(), "naive").data if t.name in ("Rollen",)] == ["Rollen"]


def test_speed_profile_omits_phases_that_do_not_occur():
    r = run()
    r["results"]["naive"]["phase"] = ["drive", "drive", "drive", "brake"]
    assert "Rollen" not in [t.name for t in V.build_speed_profile(r, "naive").data]


def test_energy_bars_show_the_savings_and_the_formula_line():
    r = run()
    fig = V.build_energy_bars(r)
    assert list(fig.data[0].x) == [C.METHOD_LABELS[k] for k in C.METHODS] and list(fig.data[0].y) == [600.0, 500.0, 420.0, 400.0]
    assert list(fig.data[0].text) == ["", "−17 %", "−30 %", "−33 %"] and fig.layout.shapes[0].y0 == pytest.approx(r["formula_E"])


def test_balance_bars_stack_resistance_lift_and_brake_loss():
    r = run()
    fig = V.build_balance_bars(r)
    assert [t.name for t in fig.data] == ["Widerstandsarbeit", "Hubarbeit (bergab negativ)", "Bremsverlust"] and fig.layout.barmode == "relative"
    assert list(fig.data[2].y) == [r["results"][k]["balance"]["brake"] for k in C.METHODS] and list(fig.data[0].y)[0] == 300.0


def test_type_bars_use_the_summary_and_the_formula():
    fig = V.build_type_bars(RES, 10.0)
    s = [R.summary(RES, t, 10.0) for t in RES["meta"]["types"]]
    assert [t.name for t in fig.data] == [C.METHOD_LABELS["naive"], C.METHOD_LABELS["coast"], C.METHOD_LABELS["dp"]] and list(fig.data[2].y) == [x["saving_dp"] for x in s]
    assert list(fig.data[0].x) == [C.PROFILE_LABELS["flach"], C.PROFILE_LABELS["wellig"]] and fig.layout.shapes[0].y0 == pytest.approx(E.formula_saving(10.0))


def test_saving_curve_has_one_line_per_method_and_the_formula():
    fig = V.build_saving_curve(RES, "flach")
    assert [t.name for t in fig.data] == [C.METHOD_LABELS["naive"], C.METHOD_LABELS["coast"], C.METHOD_LABELS["dp"], "v²-Formel"]
    assert list(fig.data[0].x) == [10.0] and list(fig.data[2].y) == [pytest.approx(30.0)] and len(fig.data[3].x) == 41 and fig.data[3].y[20] == pytest.approx(E.formula_saving(10.0))


def test_gap_bars_show_the_optimum_against_the_coast_rule():
    fig = V.build_gap_bars(RES, 10.0)
    assert list(fig.data[0].y) == [R.summary(RES, t, 10.0)["dp_vs_coast"] for t in RES["meta"]["types"]]


@pytest.mark.parametrize("make", [lambda: V.build_speed_profile(run(), "dp"), lambda: V.build_energy_bars(run()), lambda: V.build_balance_bars(run()), lambda: V.build_type_bars(RES, 10.0),
                                  lambda: V.build_saving_curve(RES, "flach"), lambda: V.build_gap_bars(RES, 10.0)])
def test_all_axes_are_fixed_for_touch_scrolling(make):
    fig = make()
    assert fig.layout.xaxis.fixedrange is True and fig.layout.yaxis.fixedrange is True
