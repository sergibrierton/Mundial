"""Cálculo de ratings Elo (estilo World Football Elo) sobre todo el histórico.

Procesa todos los partidos jugados en orden cronológico y mantiene un rating
por selección. El factor K depende de la importancia del torneo y se ajusta por
la diferencia de goles. Devuelve:
  - ratings finales por selección (a fecha del último partido del dataset)
  - muestras de calibración (diferencia de Elo previa, goles local, goles visitante)
    usadas para ajustar el modelo de goles.
  - forma reciente (rendimiento en los últimos N partidos).
"""

import math
import sqlite3

import pandas as pd

from config import (
    DB_PATH, ELO_INITIAL, ELO_HOME_ADV,
    K_WORLD_CUP, K_CONTINENTAL_FINAL, K_CONFEDERATIONS, K_QUALIFIER,
    K_NATIONS_LEAGUE, K_MINOR_TOURNAMENT, K_FRIENDLY, MAJOR_CONTINENTAL,
    all_teams,
)


def k_factor(tournament):
    t = tournament
    if "FIFA World Cup" in t and "qualification" not in t:
        return K_WORLD_CUP
    if "Confederations Cup" in t:
        return K_CONFEDERATIONS
    if t in MAJOR_CONTINENTAL:
        return K_CONTINENTAL_FINAL
    if "Nations League" in t:
        return K_NATIONS_LEAGUE
    if "qualification" in t:
        return K_QUALIFIER
    if t == "Friendly":
        return K_FRIENDLY
    return K_MINOR_TOURNAMENT


def goal_diff_multiplier(home_score, away_score):
    """Multiplicador por margen de victoria (World Football Elo)."""
    diff = abs(home_score - away_score)
    if diff <= 1:
        return 1.0
    if diff == 2:
        return 1.5
    return (11.0 + diff) / 8.0


def expected_score(elo_home, elo_away, ha_side):
    """Probabilidad esperada (incluye empate como medio) para el local."""
    dr = elo_home - elo_away + ha_side * ELO_HOME_ADV
    return 1.0 / (1.0 + 10 ** (-dr / 400.0))


def compute(min_date_for_calibration="1990-01-01"):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date,home_team,away_team,home_score,away_score,tournament,neutral "
        "FROM matches WHERE played=1 ORDER BY date, id", conn)
    conn.close()

    ratings = {}
    last_played = {}
    calib = []   # (dr_efectiva, home_score, away_score)
    recent = {}  # team -> lista de (date, pts, gf, ga) recientes

    for row in df.itertuples(index=False):
        ht, at = row.home_team, row.away_team
        rh = ratings.get(ht, ELO_INITIAL)
        ra = ratings.get(at, ELO_INITIAL)
        ha_side = 0 if row.neutral else 1   # ventaja para el local si no es neutral

        dr = rh - ra + ha_side * ELO_HOME_ADV
        we = 1.0 / (1.0 + 10 ** (-dr / 400.0))

        if row.home_score > row.away_score:
            w = 1.0
        elif row.home_score == row.away_score:
            w = 0.5
        else:
            w = 0.0

        k = k_factor(row.tournament) * goal_diff_multiplier(row.home_score, row.away_score)
        delta = k * (w - we)
        ratings[ht] = rh + delta
        ratings[at] = ra - delta
        last_played[ht] = row.date
        last_played[at] = row.date

        # Muestras de calibración (sólo partidos con ambas selecciones ya
        # "asentadas" y a partir de 1990 para reflejar el fútbol moderno).
        if row.date >= min_date_for_calibration:
            calib.append((dr, int(row.home_score), int(row.away_score)))

        # Forma reciente
        recent.setdefault(ht, []).append(
            (row.date, 3 if w == 1 else (1 if w == 0.5 else 0),
             int(row.home_score), int(row.away_score)))
        recent.setdefault(at, []).append(
            (row.date, 3 if w == 0 else (1 if w == 0.5 else 0),
             int(row.away_score), int(row.home_score)))

    return {
        "ratings": ratings,
        "last_played": last_played,
        "calibration": calib,
        "recent": recent,
    }


def recent_form(recent, team, n=20):
    games = sorted(recent.get(team, []))[-n:]
    if not games:
        return {"games": 0, "ppg": 0.0, "gf": 0.0, "ga": 0.0}
    pts = sum(g[1] for g in games)
    gf = sum(g[2] for g in games)
    ga = sum(g[3] for g in games)
    return {
        "games": len(games),
        "ppg": round(pts / len(games), 2),
        "gf": round(gf / len(games), 2),
        "ga": round(ga / len(games), 2),
    }


def ratings_table(result):
    """Devuelve un DataFrame ordenado con el Elo de las 48 selecciones."""
    ratings = result["ratings"]
    recent = result["recent"]
    rows = []
    for team in all_teams():
        form = recent_form(recent, team, 20)
        rows.append({
            "team": team,
            "elo": round(ratings.get(team, ELO_INITIAL), 1),
            "form_ppg": form["ppg"],
            "form_gf": form["gf"],
            "form_ga": form["ga"],
            "last_played": result["last_played"].get(team, "—"),
        })
    df = pd.DataFrame(rows).sort_values("elo", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    return df


if __name__ == "__main__":
    res = compute()
    print(ratings_table(res).to_string(index=False))
