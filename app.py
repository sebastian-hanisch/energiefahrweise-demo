"""Energieoptimale Fahrweise: Rollen schlägt Langsamfahren - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Sechster Baustein der Reihe Bahn/Schienenverkehr: Ein Zug fährt 20 km mit einer Fahrzeitreserve im Fahrplan. Die Demo vergleicht bei gleicher Fahrzeit „gleichmäßig langsamer“, eine einfache
Rollpunkt-Regel und das Optimum (dynamische Programmierung über Ort und Geschwindigkeit) und zeigt, dass die Formel „Energie je km ~ v²“ der Slow-Steaming-Demo hier nicht reicht: Rollen spart die
Bremsenergie.

Lauffähig mit: streamlit run app.py
"""

import pandas as pd
import streamlit as st

import efw_constants as C
import efw_evaluation as E
import efw_results as R
import efw_track as TR
from efw_dp import KIND_BRAKE, KIND_COAST, KIND_DRIVE
from efw_pdf_export import generate_plan_pdf
from efw_physics import replay
from efw_presets import (apply_preset, bounds, init_session_state_defaults, load_permalink_settings, randomize_seed, settings_from_state,
                         sync_query_params)
from efw_visualization import build_balance_bars, build_energy_bars, build_gap_bars, build_saving_curve, build_speed_profile, build_type_bars

st.set_page_config(page_title="Energieoptimale Fahrweise – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _results():
    return R.load_results()


@st.cache_data(show_spinner=False)
def _live(reserve, profile, regen, seed):
    return E.run_live({"reserve": reserve, "profile": profile, "regen": regen, "seed": seed})


st.title("🚄 Energieoptimale Fahrweise: Rollen schlägt Langsamfahren")
st.markdown(
    """
Ein Zug fährt **20 km** von Halt zu Halt, und der Fahrplan lässt ihm eine **Fahrzeitreserve**. Wie spart man damit Energie? Die naheliegende Antwort ist **gleichmäßig langsamer fahren**; die bekannte
Formel „Energie je Strecke ~ v²“ (Slow Steaming) sagt dafür eine feste Ersparnis voraus. Aber ein Zug hat Masse und Bremsen: Ein großer Teil seiner Energie geht beim **Bremsen** verloren. **Rollen** (Zugkraft
abschalten) macht daraus Strecke. Die Demo vergleicht bei **gleicher Fahrzeit** gleichmäßiges Langsamfahren, eine **einfache Rollpunkt-Regel** (Beschleunigen, Beharren, Rollen, Bremsen) und das **Optimum**
(dynamische Programmierung über Ort und Geschwindigkeit) und zeigt, **wo die Formel falsch liegt** und **wo die einfache Regel schon genügt**.
"""
)

# erklaerseite:einfach:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/energiefahrweise-erklaert.json, nicht von Hand ändern)
with st.expander("💬 In einfachen Worten"):
    st.markdown(
        """
Ein Zug darf zwischen zwei Halten etwas länger brauchen als in der schnellsten Fahrt. Diese Fahrzeitreserve lässt sich nutzen, um Energie zu sparen. Gleichmäßig langsamer zu fahren hilft, aber weniger als möglich: In der schnellsten Fahrt geht ein großer Teil der Energie in der Bremse verloren. Besser ist **Rollen**: Der Zug schaltet früher die Zugkraft ab und läuft aus, so wird Bewegungsenergie zu Strecke. Die Demo vergleicht gleichmäßiges Langsamfahren, eine einfache Regel mit einem Rollpunkt und das Optimum aus der dynamischen Programmierung und zeigt, wo die einfache Regel schon genügt. Die Zugwerte sind willkürlich gewählt: Die Aussagen gelten im Modell.

[Ausführlich und verständlich erklärt, mit Fachteil](https://sebastianhanisch.net/energiefahrweise-erklaert.html)
        """
    )
# erklaerseite:einfach:end
st.caption(
    "Sechster Baustein der Reihe Bahn/Schienenverkehr nach [Taktfahrplan](https://sebastianhanisch-taktfahrplan-demo.streamlit.app/), "
    "[Fahrzeitreserve](https://sebastianhanisch-fahrzeitreserve-demo.streamlit.app/) (dort geht es um die Verteilung der Reserve, hier um ihre Nutzung) und "
    "[Trassenkonflikt](https://sebastianhanisch-streckenkonflikt-demo.streamlit.app/). Gegenstück zu [slow-steaming-demo](https://sebastianhanisch-slow-steaming-demo.streamlit.app/) "
    "(Schiff, kubischer Verbrauch ohne Dynamik): Hier kommen Beschleunigung, Steigung und Bremsverlust dazu."
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
preset_cols = st.columns(3)
for i, name in enumerate(C.PRESET_ORDER):
    with preset_cols[i % 3]:
        st.button(name, key=f"preset_{name}", width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP[name])

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.slider("Fahrzeitreserve (%)", C.RESERVE_MIN, C.RESERVE_MAX, step=C.RESERVE_STEP, key="reserve_slider", format="%.1f",
              help="Wie viel länger der Zug als in der schnellsten Fahrt brauchen darf (Prozent). Alle Fahrweisen werden auf diese Fahrzeit gerechnet.")
    st.select_slider("Streckenprofil", options=C.PROFILE_TYPES, key="profile_select", format_func=lambda t: C.PROFILE_LABELS[t],
                     help="Steigungsprofil der 20 km. Wellig: Höhenunterschied null. Gefälle ist ein Extremfall mit Netto-Gefälle (rund 125 m Höhenverlust).")
    st.select_slider("Rückspeisung", options=C.REGEN_OPTIONS, key="regen_select", format_func=lambda o: C.REGEN_LABELS[o],
                     help="Mit Rückspeisung wird ein Teil der Bremsenergie zurückgewonnen und der Energie gutgeschrieben.")
    st.number_input("Zufalls-Seed", min_value=bounds("seed_input")[0], max_value=bounds("seed_input")[1], step=1, key="seed_input",
                    help="Bestimmt das zufällige Profil des gewählten Typs (Steigungen und Tempolimits).")
    st.button("🎲 Neues Profil würfeln", on_click=randomize_seed)

values = {k: st.session_state[k] for k in ("reserve_slider", "profile_select", "regen_select", "seed_input", "view_select")}
sync_query_params(values)
settings = settings_from_state(values)

res = _results()
with st.spinner("Rechne die vier Fahrweisen (die dynamische Programmierung braucht beim ersten Aufruf einige Sekunden) …"):
    run = _live(settings["reserve"], settings["profile"], settings["regen"], settings["seed"])
results, prof = run["results"], run["profile"]
st.caption(
    f"Profil „{C.PROFILE_LABELS[settings['profile']]}“, Seed {settings['seed']}: {int(prof['L'] / 1000)} km, Höhenunterschied {TR.height_profile(prof)[-1]:+.0f} m, höchstens {C.V_TOP * 3.6:.0f} km/h. "
    f"Schnellste Fahrt {run['T_min']:.0f} s, Fahrzeitbudget {run['T_budget']:.0f} s. Rechenzeit dieses Laufs {run['seconds']:.1f} s (beim ersten Aufruf; danach aus dem Zwischenspeicher)."
)

st.markdown("---")
st.markdown("## 🚄 Was spart das Rollen?")
cols = st.columns(4)
for col, key in zip(cols, C.METHODS):
    delta = None if key == "fast" else f"{-E.saving_pct(run, key):.0f} % gegen schnellste Fahrt"
    col.metric(C.METHOD_LABELS[key], f"{results[key]['E']:.0f} MJ", delta=delta, delta_color="inverse",
               help="Traktionsarbeit am Rad bei gleicher Fahrzeit (Energie der schnellsten Fahrt bei der schnellsten Fahrt). Delta = diese Energie gegen die der schnellsten Fahrt.")
for state, text in E.messages(run, settings):
    (st.success if state == "success" else st.warning if state == "warning" else st.info)(f"💡 {text}")

rows = []
for key in C.METHODS:
    r = results[key]
    rows.append({"Fahrweise": C.METHOD_LABELS[key], "Energie (MJ)": round(r["E"], 1), "Ersparnis": "–" if key == "fast" else f"{E.saving_pct(run, key):.1f} %", "Fahrzeit (s)": round(r["T"], 1),
                 "Rollanteil der Strecke": f"{E.coast_share_pct(r):.0f} %", "Bremsverlust": f"{r['balance']['brake']:.0f} MJ ({E.brake_share_pct(r):.0f} %)"})
rows.append({"Fahrweise": "v²-Formel (Slow Steaming)", "Energie (MJ)": round(run["formula_E"], 1), "Ersparnis": f"{E.formula_saving(run['reserve']):.1f} %", "Fahrzeit (s)": round(run["T_budget"], 1),
             "Rollanteil der Strecke": "–", "Bremsverlust": "–"})
st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
st.caption("Ersparnis in Prozent der Energie der schnellsten Fahrt. Bremsverlust = Bremsarbeit der negativen Zugkraft, in Klammern als Anteil der eingesetzten Energie (Traktion plus beim Bergabfahren frei werdende Lageenergie).")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Energie bei gleicher Fahrzeit**")
    st.plotly_chart(build_energy_bars(run), width="stretch", key=f"energy_{settings}")
with c2:
    st.markdown("**Wohin geht die Energie?**")
    st.plotly_chart(build_balance_bars(run), width="stretch", key=f"balance_{settings}")
st.caption("Traktionsarbeit = Widerstandsarbeit + Hubarbeit + Bremsverlust (der Zug steht am Anfang und am Ende). Je weniger Bremsverlust, desto weniger Energie: Rollen wandelt kinetische Energie in Strecke um, statt sie zu vernichten.")

st.markdown("### Die Fahrt im Detail")
view = st.radio("Fahrweise anzeigen", C.VIEW_OPTIONS, key="view_select", horizontal=True, format_func=lambda k: C.METHOD_LABELS[k],
                help="Reine Anzeigewahl: welche Fahrweise als Geschwindigkeitsverlauf gezeigt wird (keine Einstellung der Rechnung).")
st.plotly_chart(build_speed_profile(run, view), width="stretch", key=f"speed_{settings}_{view}")
st.caption("Farbe = Fahrphase der gewählten Fahrweise (blau Antrieb oder Halten, grün Rollen, rot Bremsen); grau die schnellste Fahrt, gestrichelt das Tempolimit; unten das Steigungsprofil (orange bergauf, blau bergab).")
summary_lines = [f"Profil {C.PROFILE_LABELS[settings['profile']]}, Seed {settings['seed']}, Fahrzeitreserve {run['reserve']:g} %, {C.REGEN_LABELS[settings['regen']]}",
                 f"Fahrweise {C.METHOD_LABELS[view]}: {results[view]['E']:.0f} MJ ({E.saving_pct(run, view):.0f} % weniger als die schnellste Fahrt), Fahrzeit {results[view]['T']:.0f} s."]
st.download_button("📄 Fahrbefehle als PDF herunterladen", data=generate_plan_pdf(results[view], "Fahrbefehle", summary_lines), file_name="fahrbefehle.pdf", mime="application/pdf", key="pdf_download")

# ------------------------------------------------------------------ Kernabschnitt: Messreihe
st.markdown("---")
st.subheader("📐 Was die Messreihe zeigt")
typ = settings["profile"]
s10 = R.summary(res, typ, 10.0)
st.caption(f"Vorgerechnet (tools/sweep.py): {s10['n']} Zufallsprofile je Profiltyp und Reserve (Seeds {res['meta']['seeds'][0]}–{res['meta']['seeds'][1] - 1}), Mittel ± Standardfehler; Ersparnis in Prozent der Energie der schnellsten Fahrt. "
           f"Gezeigt ist der gewählte Profiltyp „{C.PROFILE_LABELS[typ]}“ bei 10 % Reserve.")
d1, d2, d3, d4 = st.columns(4)
d1.metric("Gleichmäßig langsamer", f"{s10['saving_a']:.0f} ± {s10['saving_a_se']:.0f} %", help="Mittlere Ersparnis bei 10 % Fahrzeitreserve.")
d2.metric("Rollpunkt-Regel", f"{s10['saving_coast']:.0f} ± {s10['saving_coast_se']:.0f} %")
d3.metric("Optimum (DP)", f"{s10['saving_dp']:.0f} ± {s10['saving_dp_se']:.0f} %")
d4.metric("v²-Formel sagt", f"{s10['formula']:.0f} %", help="Slow-Steaming-Formel 1 − 1/(1+r)² bei r = 10 %.")
st.markdown("**Ersparnis gegen Fahrzeitreserve (gewählter Profiltyp)**")
st.plotly_chart(build_saving_curve(res, typ), width="stretch", key=f"sweep_curve_{typ}")
st.caption("Die gestrichelte Linie ist die Formel „Energie je Strecke ~ v²“. Sie trifft das gleichmäßige Langsamfahren ungefähr, liegt aber beim Optimum auf allen Profiltypen weit darunter: schon die ersten 2,5 % Reserve sparen mehr, als die Formel für 5 % verspricht.")
st.markdown("**Alle Profiltypen bei 10 % Reserve**")
st.plotly_chart(build_type_bars(res, 10.0), width="stretch", key="sweep_types")
st.markdown("**Was bringt das Optimum gegenüber der einfachen Regel?**")
st.plotly_chart(build_gap_bars(res, 10.0), width="stretch", key="sweep_gap")
st.caption("Auf flacher Strecke und mit Rampe ist das Optimum nicht besser als die Rollpunkt-Regel (Unterschiede unter 0,5 % sind nicht belastbar). Der Vorsprung liegt bei welligen Profilen, Tempolimit-Zonen und im Gefälle.")
table = []
for t in res["meta"]["types"]:
    s = R.summary(res, t, 10.0)
    table.append({"Profiltyp": C.PROFILE_LABELS[t], "Gleichmäßig langsamer": f"{s['saving_a']:.1f} ± {s['saving_a_se']:.1f} %", "Rollpunkt-Regel": f"{s['saving_coast']:.1f} ± {s['saving_coast_se']:.1f} %",
                  "Optimum": f"{s['saving_dp']:.1f} ± {s['saving_dp_se']:.1f} %", "Optimum gg. Rollpunkt": f"{s['dp_vs_coast']:.1f} ± {s['dp_vs_coast_se']:.1f} %",
                  "v²-Formel": f"{s['formula']:.1f} %", "Bremsverlust schnellste Fahrt": f"{s['brake_fast']:.0f} %", "Rollanteil Optimum": f"{s['coast_share']:.0f} %"})
st.dataframe(pd.DataFrame(table), width="stretch", hide_index=True)

# ------------------------------------------------------------------ Methodenvergleich
st.markdown("---")
with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich", expanded=False):
    tabs = st.tabs(["🚆 Fahrweisen", "🧪 Optimum nachprüfen", "📈 Messreihe"])

    with tabs[0]:
        st.markdown(
            "**Schnellste Fahrt:** mit voller Zugkraft beschleunigen, das Tempo halten, so spät wie möglich bremsen. **Gleichmäßig langsamer:** dasselbe mit einem gesenkten Höchsttempo, so gewählt, dass die Fahrzeit das Budget erreicht. "
            "**Rollpunkt-Regel:** Beschleunigen, Beharren, ab einem Rollpunkt Zugkraft aus (Rollen), dann Bremsen; der Rollpunkt trifft das Budget, das Reisetempo ist unter einigen Kandidaten energieminimal. "
            "**Optimum:** dynamische Programmierung über Ort (250-m-Zellen) und Geschwindigkeit (0,1 m/s) mit einem Lagrange-Parameter auf der Zeit: Sie minimiert Energie plus λ mal Zeit; λ wird so gesucht, dass die Fahrzeit das Budget erreicht. "
            "Übergänge sind Halten, Beschleunigen und Bremsen auf Rasterzielen sowie Rollen, volle Zugkraft und volle Bremsung mit interpoliertem Zielzustand."
        )
        st.dataframe(pd.DataFrame([{"Fahrweise": C.METHOD_LABELS[k], "Energie (MJ)": round(results[k]["E"], 1), "Fahrzeit (s)": round(results[k]["T"], 1), "Traktion (MJ)": round(results[k]["balance"]["traction"], 1),
                                    "Widerstand (MJ)": round(results[k]["balance"]["resist"], 1), "Hub (MJ)": round(results[k]["balance"]["lift"], 1), "Bremsverlust (MJ)": round(results[k]["balance"]["brake"], 1)}
                                   for k in C.METHODS]), width="stretch", hide_index=True)

    with tabs[1]:
        st.caption("Die Steuerfolge des Optimums wird unabhängig vom Optimierer nachgefahren: Zeitintegration (Runge-Kutta 4. Ordnung, Schritt 0,2 s) mit konstanter Zugkraft je Zelle; die Energie läuft als Integral von F·v mit. "
                   "Sie muss Zeit und Energie des Optimums und den Stillstand am Ziel reproduzieren.")
        key = tuple(sorted(settings.items()))
        if st.button("🧪 Optimum nachfahren (Zeitintegration)", key="replay_button"):
            with st.spinner("Integriere die Fahrt …"):
                dpr = results["dp"]
                kind = [{"drive": KIND_DRIVE, "brake": KIND_BRAKE, "coast": KIND_COAST}[p] for p in dpr["phase"]]
                G, _ = TR.cell_arrays(prof, dpr["dx"])
                st.session_state["replay_result"] = {"key": key, "res": replay(G, dpr["dx"], dpr["v"], dpr["F"], kind)}
        rp = st.session_state.get("replay_result")
        if rp and rp["key"] == key:
            r = rp["res"]
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Zeitunterschied", f"{abs(r['T'] - results['dp']['T']):.2f} s", help="Nachgefahrene gegen geplante Fahrzeit.")
            q2.metric("Energieunterschied", f"{abs(r['E'] - results['dp']['E']) / max(results['dp']['E'], 1e-9) * 100:.2f} %" if settings["regen"] == "aus" else "nur ohne Rückspeisung",
                      help="Nachgefahrene gegen geplante Traktionsenergie; mit Rückspeisung wird die Gutschrift im Replay nicht gerechnet.")
            q3.metric("Endgeschwindigkeit", f"{r['vend']:.3f} m/s")
            q4.metric("größte Verzögerung", f"{r['maxdec']:.2f} m/s²", help=f"Grenze {C.DECEL} m/s².")
        elif rp:
            st.caption("Die Einstellungen haben sich seit dem letzten Lauf geändert - bitte erneut nachfahren.")

    with tabs[2]:
        st.caption("Alle Zellen der Messreihe: mittlere Ersparnis (% der Energie der schnellsten Fahrt) je Profiltyp und Reserve.")
        out = []
        for t in res["meta"]["types"]:
            for rsv in res["meta"]["reserves"]:
                s = R.summary(res, t, rsv)
                out.append({"Profiltyp": C.PROFILE_LABELS[t], "Reserve": f"{rsv:g} %", "gleichmäßig langsamer": round(s["saving_a"], 1), "Rollpunkt": round(s["saving_coast"], 1), "Optimum": round(s["saving_dp"], 1),
                            "v²-Formel": round(s["formula"], 1), "Optimum gg. Rollpunkt": round(s["dp_vs_coast"], 1)})
        st.dataframe(pd.DataFrame(out), width="stretch", hide_index=True)
        rg = [R.regen_summary(res, t) for t in res["meta"]["regen_types"]]
        st.markdown(f"**Mit Rückspeisung ({int(100 * C.REGEN_ETA)} %), {rg[0]['n']} Profile je Typ, 10 % Reserve**")
        st.dataframe(pd.DataFrame([{"Profiltyp": C.PROFILE_LABELS[t], "gleichmäßig langsamer": f"{s['saving_a']:.1f} %", "Rollpunkt": f"{s['saving_coast']:.1f} %", "Optimum": f"{s['saving_dp']:.1f} %",
                                    "Optimum gg. gleichmäßig langsamer": f"{s['dp_vs_a']:.1f} %"} for t, s in zip(res["meta"]["regen_types"], rg)]), width="stretch", hide_index=True)

with st.expander("Wie funktioniert diese Demo?"):
    st.markdown(
        f"""
**Zug.** {C.MASS / 1000:.0f} t Masse (mit {int((C.ROT - 1) * 100)} % Drehmassenzuschlag), Fahrwiderstand R(v) = {C.RES_A:.0f} N + {C.RES_B:.0f} N·s/m · v + {C.RES_C:.0f} N·s²/m² · v², größte Zugkraft {C.F_MAX / 1000:.0f} kN, größte Leistung {C.P_MAX / 1e6:.0f} MW,
Bremsverzögerung {C.DECEL} m/s², Höchsttempo {C.V_TOP * 3.6:.0f} km/h. Alle Werte sind willkürlich gewählt und nicht an eine reale Baureihe angelehnt; die Struktur der Aussagen (Rollen spart Bremsenergie) hängt nicht daran, die Zahlen schon.

**Strecke.** {int(C.LENGTH_M / 1000)} km aus {C.N_UNITS} Einheiten zu {int(C.UNIT_M)} m; je Einheit eine Steigung in Promille und ein Tempolimit. Fünf Profiltypen werden zufällig erzeugt (flach, wellig mit Höhenunterschied null, flach mit einer Rampe, flach mit Tempolimit-Zonen, Gefälle als Extremfall).

**Energie.** Traktionsarbeit am Rad in MJ; Bremsen kostet nichts und gewinnt nichts zurück, außer in der Variante mit Rückspeisung (Gutschrift {int(100 * C.REGEN_ETA)} % der Bremsarbeit). **Fahrzeitreserve** r: Das Budget ist (1 + r) mal die schnellste Fahrt des Simulators.

**Grenzen.** Ein Zug, eine Strecke, keine Signale und kein Fahrplan; keine Zugbildung, kein Schlupf. Die DP hat einen Fehlerboden von etwa 0,3 bis 0,5 %: Unterschiede darunter sind nicht belastbar. Die Rollpunkt-Regel ist eine Heuristik; das Optimum ist deshalb
eine obere Schranke dessen, was Optimierung gegenüber einer Fahrerregel bringt.
"""
    )

with st.expander("📐 Mathematische Formulierung"):
    # erklaerseite:lesehilfe:start (erzeugt von tools/set_demo_explainer.py (Website-Repo) aus tools/content/explainers/energiefahrweise-erklaert.json, nicht von Hand ändern)
    st.markdown(
        r"""
**Lesehilfe.** Gegeben sind der Zug, die Strecke mit Steigungen und Tempolimits und die Fahrzeitreserve $r$. Gesucht ist die Fahrweise mit der geringsten Energie bei gleicher Fahrzeit und ihre Ersparnis gegen die schnellste Fahrt.

| Symbol | Bedeutung |
|---|---|
| $F$ | mittlere Zugkraft in einer Zelle (negativ beim Bremsen) |
| $m_\mathrm{eff}$, $a$ | wirksame Masse (mit Drehmassenzuschlag), Beschleunigung |
| $R(v)$ | Fahrwiderstand bei Geschwindigkeit $v$ |
| $m g \sin\alpha$ | Kraft durch die Steigung (Steigungswinkel $\alpha$) |
| $dx$, $dt$ | Länge der Zelle, Fahrzeit in der Zelle |
| $\eta$ | Anteil der Bremsarbeit, der gutgeschrieben wird (ohne Rückspeisung null) |
| $E_k$, $dt_k$ | Energie und Fahrzeit in Zelle $k$ |
| $\lambda$ | Preis der Zeit (Lagrange-Parameter) |
| $r$ | Fahrzeitreserve gegen die schnellste Fahrt |

[Schritt für Schritt erklärt, mit Herleitung und Literatur](https://sebastianhanisch.net/energiefahrweise-erklaert.html#fachleute)
        """
    )
    # erklaerseite:lesehilfe:end
    st.markdown(
        r"""
**Bewegung.** Je Zelle konstante Beschleunigung $a$: $F = m_\mathrm{eff}\, a + R(v) + m g \sin\alpha$ mit mittlerer Zugkraft $F$, Zeit $dt = 2\,dx/(v_i + v_j)$ und Energie $\max(F, 0)\,dx - \eta\, \max(-F, 0)\,dx$.
Zugkraft $F \le \min(F_\mathrm{max}, P_\mathrm{max}/v)$, Verzögerung $\ge -0{,}7$ m/s², Tempolimit je Zelle.

**Optimum.** $\min \sum_k E_k$ unter $\sum_k dt_k \le T_b$ löst man über $\min \sum_k (E_k + \lambda\, dt_k)$ mit Bellman-Rückwärtsrechnung über (Ort, Geschwindigkeit); $\lambda \ge 0$ per Bisektion, gewählt wird die zulässige Spur ($T \le T_b$).
Die Energie als Funktion der Reserve ist für das Optimum konvex fallend (gemessen).

**Formel.** Slow Steaming: Energie je Strecke $\propto v^2$, Fahrzeit $\propto 1/v$, also Energie $= E_\mathrm{schnellst} / (1 + r)^2$ und Ersparnis $1 - 1/(1+r)^2$.
"""
    )

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Schienenverkehr optimieren](https://sebastianhanisch.net/schienenverkehr-optimierung.html)."
)
