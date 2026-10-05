"""Feste Annahmen, Regler-Stufen, Presets und Farben der Demo „Energieoptimale Fahrweise“ (eine Wahrheitsquelle)."""

# ------------------------------------------------------------------ Zug und Strecke (feste, willkürlich gewählte Annahmen; keine reale Baureihe)
MASS = 400e3                # Zugmasse (kg)
ROT = 1.06                  # Drehmassenzuschlag
RES_A, RES_B, RES_C = 4000.0, 60.0, 6.0      # Fahrwiderstand R(v) = A + B v + C v^2 in N, N s/m, N s^2/m^2
F_MAX = 200e3               # größte Zugkraft (N)
P_MAX = 3e6                 # größte Leistung (W)
DECEL = 0.7                 # Bremsverzögerung, netto (m/s^2)
G_ACC = 9.81
V_TOP = 40.0                # Höchsttempo der Strecke (m/s = 144 km/h)
UNIT_M = 500.0              # Länge einer Streckeneinheit (m); Steigung und Tempolimit gelten je Einheit
N_UNITS = 40                # Einheiten: 20 km
LENGTH_M = UNIT_M * N_UNITS
REGEN_ETA = 0.6             # Rückspeisewirkungsgrad der Variante „mit Rückspeisung“

# ------------------------------------------------------------------ Rechenraster (Live und Messreihe identisch)
DP_DX = 250.0               # Zellenlänge der dynamischen Programmierung (m)
DP_DV = 0.1                 # Geschwindigkeitsraster (m/s)
DP_ITERS = 18               # Bisektionsschritte auf dem Lagrange-Parameter
FB_H = 50.0                 # Zellenlänge des Vorwärts-Rückwärts-Simulators (m)
FB_CANDIDATES = 8           # Reisetempo-Kandidaten der Rollpunkt-Regel
FB_REFINE = 5
FB_COAST_ITERS = 14
FB_EDGE_ITERS = 14          # Bisektionsschritte auf den Rand des zulässigen Reisetempo-Bereichs der Rollpunkt-Regel
FB_A_ITERS = 22

# ------------------------------------------------------------------ Regler
RESERVE_MIN, RESERVE_MAX, RESERVE_STEP = 2.5, 20.0, 2.5      # Fahrzeitreserve in Prozent der schnellsten Fahrt
DEFAULT_RESERVE = 10.0
PROFILE_TYPES = ("flach", "wellig", "rampe", "tempolimit", "gefaelle")
PROFILE_LABELS = {"flach": "flach", "wellig": "wellig (Höhenunterschied null)", "rampe": "flach mit Rampe", "tempolimit": "flach mit Tempolimit-Zonen",
                  "gefaelle": "Gefälle (Extremfall)"}
DEFAULT_PROFILE = "wellig"
REGEN_OPTIONS = ("aus", "mit")
REGEN_LABELS = {"aus": "ohne Rückspeisung", "mit": f"mit Rückspeisung ({int(REGEN_ETA * 100)} %)"}
DEFAULT_REGEN = "aus"
SEED_MIN, SEED_MAX = 0, 9999
DEFAULT_SEED = 500
METHODS = ("fast", "naive", "coast", "dp")
VIEW_OPTIONS = ("naive", "coast", "dp")
DEFAULT_VIEW = "dp"
METHOD_LABELS = {"fast": "Schnellste Fahrt", "naive": "Gleichmäßig langsamer", "coast": "Rollpunkt-Regel", "dp": "Optimum (DP)"}
METHOD_COLORS = {"fast": "#7d8898", "naive": "#c0392b", "coast": "#c77700", "dp": "#2a6fb0", "formula": "#2e7d4f"}
PHASE_COLORS = {"drive": "#2a6fb0", "coast": "#2e7d4f", "brake": "#c0392b", "hold": "#7d8898"}

# ------------------------------------------------------------------ Messreihe
RESULTS_FILE = "data/efw_results.json"
SWEEP_SEEDS = range(100, 130)            # 30 Profile je Typ
SWEEP_RESERVES = (2.5, 5.0, 10.0, 15.0, 20.0)
REGEN_SWEEP_SEEDS = range(100, 108)
REGEN_SWEEP_TYPES = ("flach", "wellig")
REGEN_SWEEP_RESERVE = 10.0

# ------------------------------------------------------------------ Presets (Seeds liegen außerhalb der Messreihen-Seeds)
PRESET_ORDER = ["Standard", "Flache Strecke", "Rampe", "Tempolimit", "Starkes Gefälle", "Mit Rückspeisung"]
PRESETS = {
    "Standard": {"reserve": 10.0, "profile": "wellig", "regen": "aus", "seed": 500},
    "Flache Strecke": {"reserve": 10.0, "profile": "flach", "regen": "aus", "seed": 500},
    "Rampe": {"reserve": 10.0, "profile": "rampe", "regen": "aus", "seed": 500},
    "Tempolimit": {"reserve": 10.0, "profile": "tempolimit", "regen": "aus", "seed": 500},
    "Starkes Gefälle": {"reserve": 10.0, "profile": "gefaelle", "regen": "aus", "seed": 500},
    "Mit Rückspeisung": {"reserve": 10.0, "profile": "flach", "regen": "mit", "seed": 500},
}
PRESET_HELP = {
    "Standard": "Welliges Profil, 10 % Fahrzeitreserve: Rollen und Optimum sparen viel gegenüber gleichmäßigem Langsamfahren.",
    "Flache Strecke": "Auf flacher Strecke ist die einfache Rollpunkt-Regel schon so gut wie das Optimum: eine Rollphase genügt.",
    "Rampe": "Eine Rampe im Profil: Rollpunkt-Regel und Optimum fahren praktisch dasselbe.",
    "Tempolimit": "Tempolimit-Zonen: gleichmäßig langsamer spart schon viel, das Optimum spart trotzdem mehr.",
    "Starkes Gefälle": "Extremfall mit Netto-Gefälle: Das Optimum rollt weit und spart ein Vielfaches der einfachen Regel.",
    "Mit Rückspeisung": "Beim Bremsen wird ein Teil der Energie zurückgewonnen: Der Vorteil des Rollens halbiert sich ungefähr.",
}


def fmt_mj(x, digits=0):
    return f"{x:.{digits}f} MJ"
