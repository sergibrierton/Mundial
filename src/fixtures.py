"""Carga los 72 partidos de fase de grupos del Mundial 2026 desde la BD.

Para cada partido calcula la ventaja del local en puntos Elo (`ha_points`),
que combina:
  - la ventaja de campo general (ELO_HOME_ADV) cuando no es sede neutral,
  - el bonus de anfitrión (HOST_EXTRA) cuando juega un país anfitrión, por la
    infravaloración sistemática de su Elo (ver config.py).

Incluye además el resultado real de los partidos ya disputados (`played`,
`home_score`, `away_score`) para condicionar predicciones y simulación.
"""

import sqlite3

from config import DB_PATH, HOSTS, ELO_HOME_ADV, HOST_EXTRA

HOST_COUNTRY = {"Mexico": "Mexico", "United States": "United States", "Canada": "Canada"}


def _ha_points(home, away, country, neutral):
    """Ventaja del local en puntos Elo."""
    home_is_host = home in HOSTS
    away_is_host = away in HOSTS
    home_at_home = home_is_host and HOST_COUNTRY[home] == country
    away_at_home = away_is_host and HOST_COUNTRY[away] == country

    if home_at_home:
        return ELO_HOME_ADV + HOST_EXTRA      # anfitrión local: campo + bonus
    if away_at_home:
        return -(ELO_HOME_ADV + HOST_EXTRA)
    # Sede neutral dentro del torneo: el anfitrión conserva medio bonus (afición).
    pts = 0.0
    if home_is_host:
        pts += HOST_EXTRA * 0.5
    if away_is_host:
        pts -= HOST_EXTRA * 0.5
    if not neutral and pts == 0.0:
        # partido no neutral entre no anfitriones (no ocurre en grupos, por robustez)
        pts = ELO_HOME_ADV
    return pts


def load_fixtures():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id,date,grp,home_team,away_team,city,country,neutral,"
        "home_score,away_score,played FROM wc2026_fixtures ORDER BY date, id")
    fixtures = []
    for (fid, d, grp, home, away, city, country, neutral,
         hs, as_, played) in cur.fetchall():
        fixtures.append({
            "id": fid, "date": d, "grp": grp, "home": home, "away": away,
            "city": city, "country": country, "neutral": neutral,
            "ha_points": _ha_points(home, away, country, neutral),
            "played": bool(played),
            "home_score": hs, "away_score": as_,
        })
    conn.close()
    return fixtures


if __name__ == "__main__":
    for fx in load_fixtures():
        flag = f"  -> {fx['home_score']}-{fx['away_score']}" if fx["played"] else ""
        print(f"{fx['date']} G{fx['grp']} {fx['home']} vs {fx['away']} "
              f"ha={fx['ha_points']:+.0f}{flag}")
