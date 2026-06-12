"""Carga los 72 partidos de fase de grupos del Mundial 2026 desde la BD,
calculando la ventaja de campo (ha_side) según la sede real.

ha_side (perspectiva del equipo local del registro):
   +1  el equipo local es anfitrión y juega en su país
   -1  el equipo visitante es anfitrión y juega en su país
    0  sede neutral
"""

import sqlite3

from config import DB_PATH, HOSTS

HOST_COUNTRY = {"Mexico": "Mexico", "United States": "United States", "Canada": "Canada"}


def load_fixtures():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id,date,grp,home_team,away_team,city,country,neutral "
        "FROM wc2026_fixtures ORDER BY date, id")
    fixtures = []
    for fid, d, grp, home, away, city, country, neutral in cur.fetchall():
        ha = 0
        if home in HOSTS and HOST_COUNTRY[home] == country:
            ha = 1
        elif away in HOSTS and HOST_COUNTRY[away] == country:
            ha = -1
        fixtures.append({
            "id": fid, "date": d, "grp": grp, "home": home, "away": away,
            "city": city, "country": country, "neutral": neutral, "ha_side": ha,
        })
    conn.close()
    return fixtures


if __name__ == "__main__":
    for fx in load_fixtures():
        print(fx)
