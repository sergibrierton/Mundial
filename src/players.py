"""Análisis jugador a jugador a partir de la tabla real de goleadores.

Usa los 47.606 goles del dataset (autor, fecha, penalti) para, por selección:
  - identificar a los goleadores ACTIVOS y su peso (con decaimiento temporal),
  - medir la amenaza ofensiva y la profundidad goleadora de la plantilla,
  - estimar la dependencia de su estrella,
  - derivar un pequeño ajuste de rating (refina el Elo de resultados con la
    calidad/forma ofensiva individual),
  - predecir el goleador más probable de cada equipo.

Normaliza los nombres (acentos) para fusionar duplicados
(p. ej. "Julián Álvarez" / "Julián Alvarez").
"""

import sqlite3
import unicodedata
from collections import defaultdict

import numpy as np
import pandas as pd

from config import DB_PATH, all_teams

# Ventana de actividad y pesos por antigüedad (forma reciente del jugador)
RECENT_FROM = "2022-01-01"
YEAR_WEIGHTS = {2026: 1.0, 2025: 1.0, 2024: 0.8, 2023: 0.6, 2022: 0.45}
# Magnitud máxima (en puntos Elo) del ajuste por calidad ofensiva de plantilla
PLAYER_ELO_SPAN = 28.0


def _strip(name):
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    return "".join(c for c in n if not unicodedata.combining(c))


def analyze():
    conn = sqlite3.connect(DB_PATH)
    g = pd.read_sql_query(
        "SELECT date,team,scorer,penalty,own_goal FROM goalscorers "
        "WHERE date>=? AND own_goal=0 AND scorer IS NOT NULL AND scorer!=''",
        conn, params=(RECENT_FROM,))
    # partidos recientes por equipo (para normalizar por partido)
    m = pd.read_sql_query(
        "SELECT date,home_team,away_team FROM matches WHERE played=1 AND date>=?",
        conn, params=(RECENT_FROM,))
    conn.close()

    games = defaultdict(int)
    for _, r in m.iterrows():
        games[r.home_team] += 1
        games[r.away_team] += 1

    g["year"] = g.date.str[:4].astype(int)
    g["w"] = g.year.map(YEAR_WEIGHTS).fillna(0.4)
    g["key"] = g.scorer.map(_strip)

    teams = all_teams()
    team_players = {}     # team -> lista (display, goles_recientes, goles_ponderados, penaltis)
    attack_raw = {}       # team -> goles ponderados por partido

    for team in teams:
        sub = g[g.team == team]
        if sub.empty:
            team_players[team] = []
            attack_raw[team] = 0.0
            continue
        agg = sub.groupby("key").agg(
            display=("scorer", lambda s: s.value_counts().index[0]),
            goals=("scorer", "size"),
            wgoals=("w", "sum"),
            pens=("penalty", "sum"),
        ).sort_values("wgoals", ascending=False)
        players = [(r.display, int(r.goals), float(r.wgoals), int(r.pens))
                   for r in agg.itertuples()]
        team_players[team] = players
        ng = max(games.get(team, 1), 1)
        attack_raw[team] = float(sub.w.sum()) / ng

    # Índice de amenaza ofensiva -> z-score -> ajuste Elo (acotado)
    vals = np.array([attack_raw[t] for t in teams])
    mu, sd = vals.mean(), vals.std() or 1.0
    z = {t: (attack_raw[t] - mu) / sd for t in teams}
    # acotamos el z a [-2,2] y escalamos al span en puntos Elo
    elo_adj = {t: float(np.clip(z[t], -2, 2) / 2.0 * PLAYER_ELO_SPAN) for t in teams}

    summary = []
    for t in teams:
        pls = team_players[t]
        total_w = sum(p[2] for p in pls) or 1.0
        star_share = (pls[0][2] / total_w) if pls else 0.0
        summary.append({
            "team": t,
            "attack_index": round(attack_raw[t], 3),
            "elo_adj": round(elo_adj[t], 1),
            "active_scorers": len(pls),
            "star": pls[0][0] if pls else "—",
            "star_goals": pls[0][1] if pls else 0,
            "star_reliance": round(star_share, 2),
            "top_scorers": ", ".join(f"{p[0]} ({p[1]})" for p in pls[:5]),
        })

    return {
        "elo_adj": elo_adj,
        "team_players": team_players,
        "summary": pd.DataFrame(summary),
    }


def likely_scorers(team_players, team, n=2):
    """Devuelve los n goleadores más probables (por peso reciente) de un equipo."""
    pls = team_players.get(team, [])
    if not pls:
        return []
    total = sum(p[2] for p in pls) or 1.0
    return [(p[0], round(p[2] / total, 2)) for p in pls[:n]]


if __name__ == "__main__":
    res = analyze()
    print(res["summary"].sort_values("elo_adj", ascending=False).to_string(index=False))
