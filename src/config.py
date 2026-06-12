"""
Configuración central del proyecto Mundial 2026.

Contiene:
  - Rutas y fuentes de datos.
  - Parámetros del modelo (Elo, ventaja de campo).
  - Estructura oficial del Mundial 2026: equipos, 12 grupos (A-L),
    sedes anfitrionas y el cuadro completo de eliminatorias
    (Dieciseisavos / Octavos / Cuartos / Semis / Final).

Toda la estructura del torneo está verificada de forma cruzada entre el
calendario real (dataset martj42) y el sorteo oficial de la FIFA.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = ROOT / "output"
DB_PATH = DATA_DIR / "mundial.db"

for _d in (RAW_DIR, OUTPUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Fuentes de datos abiertas (international football results, martj42)
DATA_BASE_URL = "https://raw.githubusercontent.com/martj42/international_results/master"
DATA_FILES = {
    "results": f"{DATA_BASE_URL}/results.csv",
    "shootouts": f"{DATA_BASE_URL}/shootouts.csv",
    "goalscorers": f"{DATA_BASE_URL}/goalscorers.csv",
    "former_names": f"{DATA_BASE_URL}/former_names.csv",
}

# --------------------------------------------------------------------------
# Parámetros del modelo
# --------------------------------------------------------------------------
ELO_INITIAL = 1500.0      # rating inicial de una selección nueva
ELO_HOME_ADV = 65.0       # ventaja de campo en puntos Elo (sólo no-neutral)
ELO_REVERSION = 0.0       # reversión a la media entre temporadas (0 = desactivado)

# Factores K de importancia del partido (estilo World Football Elo)
K_WORLD_CUP = 60.0
K_CONTINENTAL_FINAL = 50.0
K_CONFEDERATIONS = 50.0
K_QUALIFIER = 40.0
K_NATIONS_LEAGUE = 40.0
K_MINOR_TOURNAMENT = 30.0
K_FRIENDLY = 20.0

# Campeonatos continentales principales -> finales de máxima importancia (K=50)
MAJOR_CONTINENTAL = {
    "UEFA Euro",
    "Copa América",
    "African Cup of Nations",
    "AFC Asian Cup",
    "Gold Cup",
    "CONCACAF Championship",
    "Oceania Nations Cup",
}

# Simulación Monte Carlo
DEFAULT_SIMULATIONS = 50000
RANDOM_SEED = 20260611
# Incertidumbre sobre el nivel "real" de cada selección en el torneo
# (lesiones, estado de forma, factor sorteo). Ruido gaussiano en puntos Elo
# aplicado por equipo y por simulación. Refleja que el Elo es una estimación,
# no una certeza; ensancha la distribución de resultados de forma realista.
ELO_SIM_SIGMA = 40.0

# Ventaja de campo reducida para los anfitriones en partidos de eliminatoria
# (sedes neutrales, pero con apoyo de afición local).
HOST_KO_BONUS = 0.5  # fracción de ELO_HOME_ADV aplicada a anfitriones en KO

# --------------------------------------------------------------------------
# Mundial 2026 — Anfitriones
# --------------------------------------------------------------------------
HOSTS = {"Mexico", "United States", "Canada"}

# --------------------------------------------------------------------------
# Mundial 2026 — Grupos oficiales (A-L)
# Verificado con el sorteo oficial FIFA y con el calendario real.
# --------------------------------------------------------------------------
GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

GROUP_LETTERS = list(GROUPS.keys())


def all_teams():
    teams = []
    for g in GROUP_LETTERS:
        teams.extend(GROUPS[g])
    return teams


def team_group(team):
    for g, members in GROUPS.items():
        if team in members:
            return g
    return None


# --------------------------------------------------------------------------
# Mundial 2026 — Cuadro de eliminatorias
# --------------------------------------------------------------------------
# Round of 32 (Dieciseisavos). Cada entrada:
#   match_no: (slotA, slotB)
# donde un slot es:
#   ("W", "A")  -> ganador del grupo A
#   ("R", "B")  -> segundo del grupo B
#   ("3", frozenset({...})) -> uno de los mejores terceros de esos grupos
R32 = {
    73: (("R", "A"), ("R", "B")),
    74: (("W", "E"), ("3", frozenset("ABCDF"))),
    75: (("W", "F"), ("R", "C")),
    76: (("W", "C"), ("R", "F")),
    77: (("W", "I"), ("3", frozenset("CDFGH"))),
    78: (("R", "E"), ("R", "I")),
    79: (("W", "A"), ("3", frozenset("CEFHI"))),
    80: (("W", "L"), ("3", frozenset("EHIJK"))),
    81: (("W", "D"), ("3", frozenset("BEFIJ"))),
    82: (("W", "G"), ("3", frozenset("AEHIJ"))),
    83: (("R", "K"), ("R", "L")),
    84: (("W", "H"), ("R", "J")),
    85: (("W", "B"), ("3", frozenset("EFGIJ"))),
    86: (("W", "J"), ("R", "H")),
    87: (("W", "K"), ("3", frozenset("DEIJL"))),
    88: (("R", "D"), ("R", "G")),
}

# Slots de eliminatoria que requieren un mejor-tercero, con sus grupos elegibles.
THIRD_PLACE_SLOTS = {m: list(R32[m][1][1]) for m in R32 if R32[m][1][0] == "3"}

# Octavos de final (Round of 16): match_no -> (ganador_de, ganador_de)
R16 = {
    89: (74, 77),
    90: (73, 75),
    91: (76, 78),
    92: (79, 80),
    93: (83, 84),
    94: (81, 82),
    95: (86, 88),
    96: (85, 87),
}

# Cuartos de final
QF = {
    97: (89, 90),
    98: (93, 94),
    99: (91, 92),
    100: (95, 96),
}

# Semifinales
SF = {
    101: (97, 98),
    102: (99, 100),
}

THIRD_PLACE_MATCH = 103   # perdedores de 101 y 102
FINAL_MATCH = 104         # ganadores de 101 y 102
