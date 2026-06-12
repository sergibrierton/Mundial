"""Construye la base de datos SQLite local a partir de los CSV crudos.

Tablas creadas:
  matches       - todos los partidos internacionales (1872-presente)
  goalscorers   - goleadores partido a partido
  shootouts     - tandas de penaltis
  former_names  - mapa de nombres antiguos -> actuales
  wc2026_fixtures - los 72 partidos de fase de grupos del Mundial 2026
  team_stats    - estadísticas históricas agregadas por selección
  head_to_head  - histórico de enfrentamientos directos

Aplica el mapa de nombres antiguos para dar continuidad histórica
(p.ej. Zaïre -> DR Congo, Netherlands Antilles -> Curaçao).
"""

import csv
import sqlite3
from datetime import date

import pandas as pd

from config import DB_PATH, RAW_DIR, GROUPS, all_teams


def _load_former_names():
    """Devuelve una función remap(name, fecha_iso) -> nombre canónico actual."""
    rows = []
    with open(RAW_DIR / "former_names.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append((r["former"], r["current"], r["start_date"], r["end_date"]))

    # Excepción: Czechoslovakia se mantiene como entidad histórica propia
    # (su sucesor moderno se divide en Chequia y Eslovaquia, ambos en el Mundial).
    by_former = {}
    for former, current, start, end in rows:
        if current == "Czechoslovakia":
            continue
        by_former.setdefault(former, []).append((current, start, end))

    def remap(name, d):
        if name in by_former:
            for current, start, end in by_former[name]:
                if start <= d <= end:
                    return current
        return name

    return remap


def build():
    remap = _load_former_names()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS goalscorers;
        DROP TABLE IF EXISTS shootouts;
        DROP TABLE IF EXISTS former_names;
        DROP TABLE IF EXISTS wc2026_fixtures;
        DROP TABLE IF EXISTS team_stats;
        DROP TABLE IF EXISTS head_to_head;

        CREATE TABLE matches (
            id INTEGER PRIMARY KEY,
            date TEXT, home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            tournament TEXT, city TEXT, country TEXT, neutral INTEGER,
            played INTEGER
        );
        CREATE TABLE goalscorers (
            date TEXT, home_team TEXT, away_team TEXT, team TEXT,
            scorer TEXT, minute REAL, own_goal INTEGER, penalty INTEGER
        );
        CREATE TABLE shootouts (
            date TEXT, home_team TEXT, away_team TEXT, winner TEXT, first_shooter TEXT
        );
        CREATE TABLE former_names (
            current TEXT, former TEXT, start_date TEXT, end_date TEXT
        );
        CREATE TABLE wc2026_fixtures (
            id INTEGER PRIMARY KEY,
            date TEXT, grp TEXT, home_team TEXT, away_team TEXT,
            city TEXT, country TEXT, neutral INTEGER
        );
        """
    )

    # ---- matches ----
    n = 0
    with open(RAW_DIR / "results.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            d = r["date"]
            home = remap(r["home_team"], d)
            away = remap(r["away_team"], d)
            hs, as_ = r["home_score"], r["away_score"]
            played = 1 if hs not in ("", "NA") else 0
            cur.execute(
                "INSERT INTO matches(date,home_team,away_team,home_score,away_score,"
                "tournament,city,country,neutral,played) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    d, home, away,
                    int(hs) if played else None,
                    int(as_) if played else None,
                    r["tournament"], r["city"], r["country"],
                    1 if r["neutral"].upper() == "TRUE" else 0,
                    played,
                ),
            )
            n += 1
    print(f"  matches: {n} filas")

    # ---- goalscorers ----
    with open(RAW_DIR / "goalscorers.csv", newline="", encoding="utf-8") as fh:
        g = 0
        for r in csv.DictReader(fh):
            d = r["date"]
            cur.execute(
                "INSERT INTO goalscorers VALUES (?,?,?,?,?,?,?,?)",
                (
                    d, remap(r["home_team"], d), remap(r["away_team"], d),
                    remap(r["team"], d), r["scorer"],
                    float(r["minute"]) if r["minute"] not in ("", "NA") else None,
                    1 if r["own_goal"].upper() == "TRUE" else 0,
                    1 if r["penalty"].upper() == "TRUE" else 0,
                ),
            )
            g += 1
    print(f"  goalscorers: {g} filas")

    # ---- shootouts ----
    with open(RAW_DIR / "shootouts.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            d = r["date"]
            cur.execute(
                "INSERT INTO shootouts VALUES (?,?,?,?,?)",
                (d, remap(r["home_team"], d), remap(r["away_team"], d),
                 remap(r["winner"], d), r.get("first_shooter", "")),
            )

    # ---- former_names ----
    with open(RAW_DIR / "former_names.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cur.execute("INSERT INTO former_names VALUES (?,?,?,?)",
                        (r["current"], r["former"], r["start_date"], r["end_date"]))

    conn.commit()

    # ---- wc2026_fixtures: los 72 partidos de fase de grupos ----
    teams = set(all_teams())
    cur.execute(
        "SELECT date,home_team,away_team,city,country,neutral FROM matches "
        "WHERE tournament='FIFA World Cup' AND date>='2026-01-01' ORDER BY date,id"
    )
    fixtures = []
    for d, home, away, city, country, neutral in cur.fetchall():
        if home in teams and away in teams:
            grp = None
            for gl, members in GROUPS.items():
                if home in members and away in members:
                    grp = gl
                    break
            fixtures.append((d, grp, home, away, city, country, neutral))
    for i, (d, grp, home, away, city, country, neutral) in enumerate(fixtures, 1):
        cur.execute(
            "INSERT INTO wc2026_fixtures(id,date,grp,home_team,away_team,city,country,neutral)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (i, d, grp, home, away, city, country, neutral),
        )
    print(f"  wc2026_fixtures: {len(fixtures)} partidos de fase de grupos")

    conn.commit()
    _build_stats(conn)
    conn.close()


def _build_stats(conn):
    """Calcula estadísticas históricas agregadas para las 48 selecciones."""
    df = pd.read_sql_query(
        "SELECT date,home_team,away_team,home_score,away_score,tournament,neutral "
        "FROM matches WHERE played=1", conn)

    teams = all_teams()
    rows = []
    for team in teams:
        h = df[df.home_team == team]
        a = df[df.away_team == team]
        gf = h.home_score.sum() + a.away_score.sum()
        ga = h.away_score.sum() + a.home_score.sum()
        wins = (h.home_score > h.away_score).sum() + (a.away_score > a.home_score).sum()
        draws = (h.home_score == h.away_score).sum() + (a.away_score == a.home_score).sum()
        losses = (h.home_score < h.away_score).sum() + (a.away_score < a.home_score).sum()
        played = len(h) + len(a)
        wc = pd.concat([h[h.tournament == "FIFA World Cup"],
                        a[a.tournament == "FIFA World Cup"]])
        rows.append({
            "team": team,
            "played": int(played),
            "wins": int(wins),
            "draws": int(draws),
            "losses": int(losses),
            "goals_for": int(gf),
            "goals_against": int(ga),
            "win_pct": round(100.0 * wins / played, 1) if played else 0.0,
            "wc_matches": int(len(wc)),
            "first_match": df[(df.home_team == team) | (df.away_team == team)].date.min(),
        })
    pd.DataFrame(rows).to_sql("team_stats", conn, if_exists="replace", index=False)
    print(f"  team_stats: {len(rows)} selecciones")

    # head_to_head entre las 48 selecciones del Mundial
    tset = set(teams)
    h2h = {}
    for _, r in df.iterrows():
        ht, at = r.home_team, r.away_team
        if ht not in tset or at not in tset:
            continue
        key = tuple(sorted((ht, at)))
        d = h2h.setdefault(key, {"matches": 0, key[0] + "_w": 0, key[1] + "_w": 0, "draws": 0})
        d["matches"] += 1
        if r.home_score > r.away_score:
            d[ht + "_w"] = d.get(ht + "_w", 0) + 1
        elif r.home_score < r.away_score:
            d[at + "_w"] = d.get(at + "_w", 0) + 1
        else:
            d["draws"] += 1
    h2h_rows = []
    for (t1, t2), d in h2h.items():
        h2h_rows.append({
            "team_a": t1, "team_b": t2, "matches": d["matches"],
            "team_a_wins": d.get(t1 + "_w", 0),
            "team_b_wins": d.get(t2 + "_w", 0),
            "draws": d["draws"],
        })
    pd.DataFrame(h2h_rows).to_sql("head_to_head", conn, if_exists="replace", index=False)
    print(f"  head_to_head: {len(h2h_rows)} emparejamientos")
    conn.commit()


if __name__ == "__main__":
    build()
