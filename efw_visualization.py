"""Plotly-Figuren der Demo „Energieoptimale Fahrweise“. Alle Achsen fest (fixedrange), damit Touch-Scrollen nicht am Chart hängen bleibt."""
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

import efw_constants as C
import efw_evaluation as E
import efw_results as R

PHASE_LABELS = {"drive": "Antrieb / Halten", "coast": "Rollen", "brake": "Bremsen"}


def _lock(fig, height=360, **layout):
    fig.update_layout(height=height, margin=dict(l=55, r=20, t=40, b=55), font=dict(size=12), legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0), **layout)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def phase_segments(entry: dict) -> dict:
    """Je Fahrphase die Linienstücke (x in km, v in km/h) mit Lücken (None) zwischen getrennten Zellen, damit eine Spur je Phase genügt."""
    segs = {p: ([], []) for p in PHASE_LABELS}
    x, v = entry["x"], entry["v"]
    for k, p in enumerate(entry["phase"]):
        xs, vs = segs[p]
        xs += [x[k] / 1000.0, x[k + 1] / 1000.0, None]
        vs += [v[k] * 3.6, v[k + 1] * 3.6, None]
    return segs


def build_speed_profile(run: dict, key: str) -> go.Figure:
    """Oben: Geschwindigkeit über dem Weg der gewählten Fahrweise (Farbe = Fahrphase) gegen die schnellste Fahrt, Tempolimit gestrichelt. Unten: Steigungsprofil in Promille."""
    prof = run["profile"]
    entry, fast = run["results"][key], run["results"]["fast"]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=[a / 1000.0 for a in fast["x"]], y=[a * 3.6 for a in fast["v"]], mode="lines", name="schnellste Fahrt", line=dict(color="#c9ced6", width=2),
                             hovertemplate="%{x:.1f} km: %{y:.0f} km/h<extra>schnellste Fahrt</extra>"), row=1, col=1)
    xs, ys = [], []
    for k, lim in enumerate(prof["lim"]):
        xs += [k * C.UNIT_M / 1000.0, (k + 1) * C.UNIT_M / 1000.0]
        ys += [lim * 3.6, lim * 3.6]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", name="Tempolimit", line=dict(color="#555", width=1.5, dash="dash"), hoverinfo="skip"), row=1, col=1)
    segs = phase_segments(entry)
    for phase, label in PHASE_LABELS.items():
        sx, sy = segs[phase]
        if sx:
            fig.add_trace(go.Scatter(x=sx, y=sy, mode="lines", name=label, line=dict(color=C.PHASE_COLORS[phase], width=3.5), connectgaps=False,
                                     hovertemplate="%{x:.1f} km: %{y:.0f} km/h<extra>" + label + "</extra>"), row=1, col=1)
    fig.add_trace(go.Bar(x=[(k + 0.5) * C.UNIT_M / 1000.0 for k in range(len(prof["grad"]))], y=list(prof["grad"]), width=C.UNIT_M / 1000.0,
                         marker_color=["#c77700" if g > 0 else "#2a6fb0" for g in prof["grad"]], name="Steigung", showlegend=False,
                         hovertemplate="%{x:.1f} km: %{y:.1f} ‰<extra>Steigung</extra>"), row=2, col=1)
    fig.update_yaxes(title_text="km/h", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="‰", row=2, col=1)
    fig.update_xaxes(title_text="Weg (km)", row=2, col=1)
    return _lock(fig, 470)


def build_energy_bars(run: dict) -> go.Figure:
    """Energie je Fahrweise bei gleicher Fahrzeit (MJ); die gestrichelte Linie ist, was die v²-Formel der Slow-Steaming-Demo für gleichmäßiges Langsamfahren vorhersagt."""
    keys = C.METHODS
    fig = go.Figure(go.Bar(x=[C.METHOD_LABELS[k] for k in keys], y=[run["results"][k]["E"] for k in keys], marker_color=[C.METHOD_COLORS[k] for k in keys],
                           text=[("" if k == "fast" else f"−{E.saving_pct(run, k):.0f} %") for k in keys], textposition="outside", hovertemplate="%{x}: %{y:.0f} MJ<extra></extra>"))
    fig.add_hline(y=run["formula_E"], line_dash="dash", line_color=C.METHOD_COLORS["formula"], annotation_text="v²-Formel", annotation_position="top right")
    top = max(run["results"][k]["E"] for k in keys)
    fig.update_yaxes(title_text="Energie (MJ)", range=[0, 1.18 * top])
    return _lock(fig, 340, showlegend=False)


def build_balance_bars(run: dict) -> go.Figure:
    """Energiebilanz je Fahrweise: Traktionsarbeit = Widerstandsarbeit + Hubarbeit (Höhenunterschied, bergab negativ) + Bremsverlust."""
    keys = C.METHODS
    labels = [C.METHOD_LABELS[k] for k in keys]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=[run["results"][k]["balance"]["resist"] for k in keys], name="Widerstandsarbeit", marker_color="#2a6fb0"))
    fig.add_trace(go.Bar(x=labels, y=[run["results"][k]["balance"]["lift"] for k in keys], name="Hubarbeit (bergab negativ)", marker_color="#c77700"))
    fig.add_trace(go.Bar(x=labels, y=[run["results"][k]["balance"]["brake"] for k in keys], name="Bremsverlust", marker_color="#c0392b"))
    fig.update_layout(barmode="relative")
    fig.update_yaxes(title_text="Energie (MJ)")
    return _lock(fig, 340)


def build_type_bars(res: dict, reserve: float) -> go.Figure:
    """Messreihe: Ersparnis (% der Energie der schnellsten Fahrt) je Profiltyp bei einer Reserve; Mittel ± Standardfehler über 30 Profile; gestrichelt die v²-Formel."""
    rows = [R.summary(res, t, reserve) for t in res["meta"]["types"]]
    names = [C.PROFILE_LABELS[t] for t in res["meta"]["types"]]
    fig = go.Figure()
    for key, label in (("a", C.METHOD_LABELS["naive"]), ("coast", C.METHOD_LABELS["coast"]), ("dp", C.METHOD_LABELS["dp"])):
        color = {"a": C.METHOD_COLORS["naive"], "coast": C.METHOD_COLORS["coast"], "dp": C.METHOD_COLORS["dp"]}[key]
        fig.add_trace(go.Bar(x=names, y=[r[f"saving_{key}"] for r in rows], name=label, marker_color=color, error_y=dict(type="data", array=[r[f"saving_{key}_se"] for r in rows], visible=True)))
    fig.add_hline(y=E.formula_saving(reserve), line_dash="dash", line_color=C.METHOD_COLORS["formula"], annotation_text="v²-Formel", annotation_position="top left")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Ersparnis gegenüber der schnellsten Fahrt (%)", rangemode="tozero")
    return _lock(fig, 400)


def build_saving_curve(res: dict, typ: str) -> go.Figure:
    """Messreihe: mittlere Ersparnis gegen die Fahrzeitreserve für einen Profiltyp, mit der v²-Formel als gestrichelter Linie (die Lücke zwischen Formel und Rollen ist der Befund)."""
    rs = res["meta"]["reserves"]
    fig = go.Figure()
    for key, color, label in (("a", C.METHOD_COLORS["naive"], C.METHOD_LABELS["naive"]), ("coast", C.METHOD_COLORS["coast"], C.METHOD_LABELS["coast"]), ("dp", C.METHOD_COLORS["dp"], C.METHOD_LABELS["dp"])):
        fig.add_trace(go.Scatter(x=rs, y=R.curve(res, typ, key), mode="lines+markers", name=label, line=dict(color=color, width=3)))
    fig.add_trace(go.Scatter(x=[x / 2 for x in range(0, 41)], y=[E.formula_saving(x / 2) for x in range(0, 41)], mode="lines", name="v²-Formel", line=dict(color=C.METHOD_COLORS["formula"], dash="dash", width=2)))
    fig.update_xaxes(title_text="Fahrzeitreserve (% der schnellsten Fahrt)", range=[0, 20.5])
    fig.update_yaxes(title_text="Ersparnis (%)", rangemode="tozero")
    return _lock(fig, 360)


def build_gap_bars(res: dict, reserve: float) -> go.Figure:
    """Messreihe: wie viel Prozent weniger Energie das Optimum als die Rollpunkt-Regel braucht, je Profiltyp (Mittel ± Standardfehler)."""
    rows = [R.summary(res, t, reserve) for t in res["meta"]["types"]]
    fig = go.Figure(go.Bar(x=[C.PROFILE_LABELS[t] for t in res["meta"]["types"]], y=[r["dp_vs_coast"] for r in rows], marker_color=C.METHOD_COLORS["dp"],
                           error_y=dict(type="data", array=[r["dp_vs_coast_se"] for r in rows], visible=True)))
    fig.update_yaxes(title_text="Optimum spart gegenüber der Rollpunkt-Regel (%)", zeroline=True)
    return _lock(fig, 340, showlegend=False)
