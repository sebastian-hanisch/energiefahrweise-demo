# Energieoptimale Fahrweise: Rollen schlägt Langsamfahren (Streamlit-Demo)

**[→ Demo live ausprobieren](https://sebastianhanisch-energiefahrweise-demo.streamlit.app/)**

Interaktive **Fall-Demo** zur energieoptimalen Fahrweise eines Zuges im Portfolio von [Sebastian Hanisch](https://sebastianhanisch.net) (Operations Research und Machine Learning).
**Sechster Baustein der Reihe Bahn/Schienenverkehr** nach dem [Taktfahrplan](https://github.com/sebastian-hanisch/taktfahrplan-demo), dem [Trassenkonflikt](https://github.com/sebastian-hanisch/trassenkonflikt-demo) und der
[Fahrzeitreserve](https://github.com/sebastian-hanisch/fahrzeitreserve-demo) (dort geht es um die Verteilung der Reserve, hier um ihre Nutzung).

Ein Zug fährt 20 km von Halt zu Halt, und der Fahrplan lässt ihm eine **Fahrzeitreserve**. Die Demo vergleicht bei gleicher Fahrzeit **gleichmäßig langsamer fahren**, eine **einfache Rollpunkt-Regel**
(Beschleunigen, Beharren, Rollen, Bremsen) und das **Optimum** (dynamische Programmierung über Ort und Geschwindigkeit) und fragt, **was Rollen bringt** und **wo die einfache Regel schon genügt**.

## Kernfrage

Wie viel Energie spart eine Fahrzeitreserve, wenn der Zug Masse, Steigungen und Bremsen hat? Die bekannte Formel „Energie je Strecke ~ v²“ der [slow-steaming-demo](https://github.com/sebastian-hanisch/slow-steaming-demo)
(Schiff, kubischer Verbrauch, keine Dynamik) sagt für eine um den Faktor 1 + r längere Fahrzeit eine Ersparnis von 1 − 1/(1 + r)² voraus. Ein Zug verliert aber in der schnellsten Fahrt einen großen Teil seiner
Energie in der Bremse; **Rollen** (Zugkraft abschalten) macht daraus Strecke. Das ist kein Slow-Steaming-Effekt: Dort sinkt die Energie nur mit dem Tempo, hier kommt es auf die Dynamik an. Die Struktur der optimalen
Fahrt (Beschleunigen mit voller Zugkraft, Geschwindigkeit halten, Rollen, Bremsen) ist aus der Literatur bekannt: Howlett, *The optimal control of a train*, Annals of Operations Research 98 (2000); Khmelnitsky,
*On an optimal control problem of train operation*, IEEE Transactions on Automatic Control 45(7) (2000); Howlett und Pudney, *Energy-Efficient Train Control*, Springer 1995; Albrecht u. a., *The key principles of optimal
train control*, Transportation Research Part B 94 (2016). Neu ist hier die Messreihe gegen die Formel und gegen eine einfache Fahrerregel.

## Befunde und Korrekturen gegenüber dem Plan

- **Die Formel liegt beim Optimum auf allen Profiltypen weit daneben, beim Langsamfahren aber nicht.** Das war die Vorab-Frage („Dopplung zur Slow-Steaming-Demo?“); sie ist mit Nein beantwortet: gleichmäßig
  Langsamfahren folgt der Formel auf flacher Strecke bis auf 1,6 Punkte, das Optimum spart 8,2 bis 40,5 Punkte mehr (bei 10 % Reserve).
- **Der Hook sitzt woanders als erwartet.** Der Vorteil der **dynamischen Programmierung** gegenüber der einfachen Rollpunkt-Regel ist auf flacher Strecke und mit Rampe null; er liegt bei welligen Profilen,
  Tempolimit-Zonen und im Gefälle. Die ehrliche Erzählung lautet deshalb „Rollen schlägt Langsamfahren, die Optimierung bringt auf profilreicher Strecke noch einmal etwas obendrauf“.
- **Ein Entwicklungsfehler der Vorab-Messreihe, hier übernommen als Regel:** Eine DP nur mit Rasterzielen war bei kleinen Zellen um 15 % zu langsam, weil die Geschwindigkeitsänderung je Zelle kleiner als der
  Rasterschritt ist. Erst Sonderübergänge mit freiem Zielzustand und interpolierter Wertfunktion (Rollen, volle Zugkraft, volle Bremsung) machten sie brauchbar; die Tests prüfen die DP deshalb gegen eine
  Vollaufzählung und gegen einen unabhängigen Zeitintegrator.
- Gegenüber der Vorab-Messreihe gröberes Raster (250-m-Zellen, 0,1 m/s statt 0,05 m/s) und ein ganzzahliger Profilgenerator (SplitMix64); die Zahlen sind neu gemessen und stimmen in der Größenordnung überein.
- Port 8971.

## Modell

- **Zug:** 400 t, Drehmassenzuschlag 6 %, Fahrwiderstand R(v) = 4000 N + 60 N·s/m · v + 6 N·s²/m² · v², Zugkraft F ≤ min(200 kN, 3 MW / v), Bremsverzögerung höchstens 0,7 m/s², Höchsttempo 144 km/h.
  Alle Werte sind willkürlich gewählt und nicht an eine reale Baureihe angelehnt.
- **Strecke:** 20 km aus 40 Einheiten zu 500 m, je Einheit Steigung in Promille und Tempolimit. Fünf zufällige Profiltypen: **flach**, **wellig** (Höhenunterschied null), **rampe**, **tempolimit** (flach mit ein bis zwei
  Zonen mit 20, 25 oder 30 m/s), **gefälle** (Extremfall mit Netto-Gefälle von rund 125 m). Alles ganzzahlig mit **SplitMix64** (`efw_rng.py`, `efw_track.py`).
- **Energie:** Traktionsarbeit am Rad in MJ; Bremsen kostet nichts und gewinnt nichts zurück, außer in der Variante mit Rückspeisung (Gutschrift 60 % der Bremsarbeit).
- **Fahrzeitreserve r:** Das Budget ist (1 + r) mal die schnellste Fahrt eines unabhängigen Simulators; r = 2,5 bis 20 %.

## Methodik

- **Gleichmäßig langsamer** und **Rollpunkt-Regel** (`efw_strategies.py`): Vorwärts-Rückwärts-Simulator (volle Zugkraft, spätestes Bremsen). Gleichmäßig langsamer senkt das Höchsttempo per Bisektion, bis die Fahrzeit
  das Budget erreicht. Die Rollpunkt-Regel schaltet ab einem Rollpunkt die Zugkraft ab; der Rollpunkt trifft das Budget, das Reisetempo ist unter einigen Kandidaten energieminimal (die stärkste Regel mit ein bis zwei Parametern).
- **Optimum** (`efw_dp.py`): dynamische Programmierung über Ort (250-m-Zellen) und Geschwindigkeit (0,1 m/s) mit einem Lagrange-Parameter auf der Zeit: Minimiert wird Energie plus λ mal Zeit, λ per Bisektion so, dass die Fahrzeit das
  Budget erreicht. Übergänge: Halten, Beschleunigen und Bremsen auf Rasterzielen sowie Rollen, volle Zugkraft und volle Bremsung mit interpoliertem Zielzustand; die Vorwärtsspur läuft im kontinuierlichen Zustand.
  Gewählt wird die zulässige Spur, der Wert ist eine obere Schranke des wahren Optimums.
- **Nachprüfung:** `efw_physics.replay` fährt die Steuerfolge des Optimums unabhängig per Zeitintegration (Runge-Kutta 4. Ordnung) nach; die Demo bietet das im Tab „Optimum nachprüfen“ an.
- **Vorgerechnete Messreihe** (`tools/sweep.py` → `data/efw_results.json`, rund 5 Minuten parallel): fünf Profiltypen zu je 30 Profilen (Seeds 100–129), fünf Reserven (2,5 / 5 / 10 / 15 / 20 %), alle Verfahren;
  dazu je 8 Profile flach und wellig mit Rückspeisung bei 10 %. Live läuft die gewählte Strecke mit dem gewählten Budget (einige Sekunden).

## Befunde (gemessen, keine Behauptungen)

Alle Zahlen stehen in `tests/test_claims.py`. 30 Profile je Typ (Seeds 100–129), Mittel ± Standardfehler; **Ersparnis** in Prozent der Energie der schnellsten Fahrt, bei 10 % Fahrzeitreserve, ohne Rückspeisung.
Die Formel „Energie je Strecke ~ v²“ sagt bei 10 % **17.4 %** voraus.

| Profiltyp | gleichmäßig langsamer | Rollpunkt-Regel | Optimum (DP) | Optimum gegen Rollpunkt-Regel |
|---|---|---|---|---|
| flach | **18.9 ± 0.1 %** | **31.9 ± 0.2 %** | **31.6 ± 0.2 %** | **−0.4 ± 0.0 %** |
| wellig | **14.1 ± 0.4 %** | **32.5 ± 1.1 %** | **35.7 ± 1.2 %** | **4.8 ± 1.1 %** |
| rampe | **14.4 ± 0.2 %** | **25.5 ± 0.5 %** | **25.5 ± 0.5 %** | **−0.0 ± 0.0 %** |
| tempolimit | **36.7 ± 1.5 %** | **41.4 ± 1.3 %** | **47.7 ± 1.0 %** | **10.5 ± 0.8 %** |
| gefaelle | **20.9 ± 0.6 %** | **32.6 ± 1.0 %** | **57.9 ± 2.2 %** | **37.3 ± 3.3 %** |

| Frage | Befund |
|---|---|
| Wo liegt die Formel richtig? | Beim gleichmäßigen Langsamfahren auf flacher Strecke: Sie liegt **1.6 Punkte** neben der Messung (17.4 gegen 18.9 %). |
| Und beim Optimum? | Das Optimum spart auf flacher Strecke **14.3 Punkte** mehr als die Formel, bei welligem Profil **18.4**, mit Rampe **8.2**, bei Tempolimit **30.3** und im Gefälle **40.5 Punkte**. |
| Wie sieht die Kurve aus? | Auf flacher Strecke sparen schon die ersten 2,5 % Reserve **16.3 %** (Formel: **4.8 %**); die nächsten 7,5 % bringen nur weitere 15 Punkte. |
| Warum? | In der schnellsten Fahrt gehen **52 %** der eingesetzten Energie (flach) bzw. **58 %** (wellig) in der Bremse verloren; Rollen wandelt kinetische Energie in Strecke um. Das Optimum rollt auf flacher Strecke auf **63 %** der Länge. |
| Wo genügt die einfache Regel? | Auf flacher Strecke und mit Rampe: Das Optimum liegt dort höchstens **0.4 %** neben der Rollpunkt-Regel, Unterschiede unter 0,5 % sind nicht belastbar (Fehlerboden der DP). |
| Und mit Rückspeisung? | Der Vorsprung des Optimums gegenüber gleichmäßigem Langsamfahren sinkt auf flacher Strecke von **15.7 %** auf **8.0 %**, bei welligem Profil von **25.1 %** auf **12.8 %** (8 Profile je Typ). |

## Ehrliche Grenzen

- **Die Parameter sind willkürlich** (Masse, Widerstand, 3 MW, 0,7 m/s², 144 km/h). Die Struktur (Rollen spart Bremsenergie) hängt nicht daran, die Zahlen schon.
- **Die Rollpunkt-Regel ist eine Heuristik** mit ein bis zwei Parametern; eine klügere Regel mit mehreren Rollphasen würde die Lücke zum Optimum auf welligen Profilen und im Gefälle verkleinern. „Optimum gegen Rollpunkt-Regel“
  ist daher eine obere Schranke dessen, was Optimierung gegenüber einer Fahrerregel bringt; gegenüber gleichmäßigem Langsamfahren ist die Aussage robust.
- **Die DP hat einen Fehlerboden von etwa 0,3 bis 0,5 %** (Raster, Zugkraftgrenze in Zellmitte); auf flacher Strecke liegt sie deshalb knapp *hinter* der Rollpunkt-Regel.
- **Das Gefälle ist ein Extremfall** (im Mittel −6 ‰ über 20 km): Die Prozentzahlen sind dort schlecht konditioniert, weil die Energie der schnellsten Fahrt klein ist; die Tempolimit-Zonen sind nicht mit den anderen Typen
  vergleichbar, weil dort schon gleichmäßiges Langsamfahren viel spart.
- Ein Zug, eine Strecke, keine Signale, kein Fahrplan, ohne Schlupf; mit Rückspeisung nur zwei Profiltypen mit je 8 Profilen. Die Standardfehler gelten für Zufallsprofile dieser Generatoren, nicht für reale Strecken.
- **Nicht belegt:** konkrete Praxis-Einsparquoten (etwa aus Fahrerassistenzsystemen) und der Vergleich mit DP-Ansätzen aus der Literatur.

## Tests

Siehe `tests/`: Zugphysik von Hand gerechnet (Widerstand, Zelle, Rollen, volle Zugkraft, Bremsen), Profile eingefroren, **DP gegen eine Vollaufzählung aller 78 125 Geschwindigkeitsfolgen auf einer winzigen Strecke**
(`tests/test_dp.py`), die Steuerfolge der DP gegen einen unabhängigen Zeitintegrator, Vorwärts-Rückwärts-Simulator mit Energiebilanz, Meldungen an ihren Schwellen mit künstlichen Zahlen, Statistik an einer von Hand gerechneten
Mini-Ergebnisdatei, Preset-Kriterien (jedes Kriterium kippt einzeln), `test_claims.py` (jede README-Zahl gegen die Ergebnisdatei), AppTest-Rauchtests (Voreinstellung, jedes Preset, Randwerte, Permalink, Nachprüfen-Tab).
Keine Wall-Clock-Assertions. `tools/mutation_check.py` baut einzelne Fehler in die Module ein und prüft, ob die Tests sie finden.

```
python -m pytest tests -q
```

## Dateistruktur

| Datei | Inhalt |
|---|---|
| `app.py` | Streamlit-Oberfläche |
| `efw_constants.py` | feste Annahmen, Regler-Stufen, Rechenraster, Presets |
| `efw_rng.py`, `efw_track.py` | SplitMix64; Profile aus 500-m-Einheiten |
| `efw_physics.py` | Zugphysik je Zelle, Sondersteuerungen, Interpolation, unabhängiger Zeitintegrator |
| `efw_dp.py` | dynamische Programmierung über (Ort, Geschwindigkeit) mit Lagrange-Parameter |
| `efw_strategies.py` | Vorwärts-Rückwärts-Simulator, gleichmäßig langsamer, Rollpunkt-Regel |
| `efw_evaluation.py` | Live-Rechnung, Energiebilanz, v²-Formel, Meldungen |
| `efw_results.py`, `efw_stories.py`, `efw_presets.py` | Auswertung der Messreihe; Preset-Kriterien; Permalink und Presets |
| `efw_visualization.py`, `efw_pdf_export.py` | Plotly-Figuren; Fahrbefehle als PDF |
| `data/efw_results.json` | Ergebnisse der Messreihe |
| `tools/` | `sweep.py`, `preset_search.py`, `mutation_check.py`, `PRESET_SWEEP.md` |

## Bewusst nicht umgesetzt

Mehrere Rollphasen als Heuristik, Zugbildung und Schlupf, Signale und Fahrplan, reale Baureihen und Strecken, Regelung gegen Störungen während der Fahrt, mehrere Züge (siehe dazu die Fahrzeitreserve),
Optimierung der Reserve selbst (Verteilung entlang der Strecke: Fahrzeitreserve).

## Lokal ausführen

```
pip install -r requirements.txt
streamlit run app.py
```

Die Messreihe neu erzeugen: `python tools/sweep.py`.

Gebaut mit Streamlit, Plotly, NumPy, pandas und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Schienenverkehr optimieren](https://sebastianhanisch.net/schienenverkehr-optimierung.html).
