"""Predicciones partido a partido de la fase de grupos del Mundial 2026.

Para cada uno de los 72 partidos calcula de forma analítica (sin simulación):
  - probabilidad de victoria local / empate / victoria visitante (1-X-2),
  - goles esperados de cada equipo,
  - marcador más probable y su probabilidad.
"""

import numpy as np
import pandas as pd

from config import ELO_INITIAL
from players import likely_scorers


def predict_group_matches(ratings, model, fixtures):
    rows = []
    for fx in fixtures:
        eh = ratings.get(fx["home"], ELO_INITIAL)
        ea = ratings.get(fx["away"], ELO_INITIAL)
        out = model.outcome_probs(eh, ea, fx["ha_points"])
        ls = out["likely_score"]
        played = fx.get("played")
        rows.append({
            "date": fx["date"],
            "group": fx["grp"],
            "home": fx["home"],
            "away": fx["away"],
            "status": "JUGADO" if played else "pendiente",
            "real_score": f"{fx['home_score']}-{fx['away_score']}" if played else "",
            "p_home": round(out["p_home"] * 100, 1),
            "p_draw": round(out["p_draw"] * 100, 1),
            "p_away": round(out["p_away"] * 100, 1),
            "xg_home": round(out["exp_home"], 2),
            "xg_away": round(out["exp_away"], 2),
            "likely_score": f"{ls[0]}-{ls[1]}",
            "likely_score_pct": round(out["likely_score_prob"] * 100, 1),
            "prediction": _verdict(fx, out),
        })
    return pd.DataFrame(rows)


def predict_exact(ratings, model, fixtures, team_players):
    """Marcador exacto previsto (modal) + alternativos + goleadores probables."""
    rows = []
    for fx in fixtures:
        eh = ratings.get(fx["home"], ELO_INITIAL)
        ea = ratings.get(fx["away"], ELO_INITIAL)
        m, lam, mu = model.score_matrix(eh, ea, fx["ha_points"])
        p_home = float(np.tril(m, -1).sum())
        p_draw = float(np.trace(m))
        p_away = float(np.triu(m, 1).sum())
        flat = np.argsort(m, axis=None)[::-1][:3]
        tops = []
        for i in flat:
            h, a = divmod(int(i), m.shape[1])
            tops.append(((h, a), float(m.flat[i])))
        (mh, ma), mp = tops[0]

        sc_home = likely_scorers(team_players, fx["home"], 2)
        sc_away = likely_scorers(team_players, fx["away"], 2)
        played = fx.get("played")
        rows.append({
            "date": fx["date"],
            "group": fx["grp"],
            "home": fx["home"],
            "away": fx["away"],
            "status": "JUGADO" if played else "pendiente",
            "real_score": f"{fx['home_score']}-{fx['away_score']}" if played else "",
            "exact_score": f"{mh}-{ma}",
            "exact_prob": round(mp * 100, 1),
            "alt_scores": "  ·  ".join(f"{h}-{a} ({p*100:.0f}%)" for (h, a), p in tops[1:]),
            "p_home": round(p_home * 100, 1),
            "p_draw": round(p_draw * 100, 1),
            "p_away": round(p_away * 100, 1),
            "xg_home": round(lam, 2),
            "xg_away": round(mu, 2),
            "scorer_home": _fmt_scorers(sc_home),
            "scorer_away": _fmt_scorers(sc_away),
            "result": _result_text(fx, mh, ma),
        })
    return pd.DataFrame(rows)


def _fmt_scorers(sc):
    if not sc:
        return "—"
    return ", ".join(name for name, _ in sc)


def _result_text(fx, mh, ma):
    if mh > ma:
        return f"Victoria {fx['home']} {mh}-{ma}"
    if mh < ma:
        return f"Victoria {fx['away']} {ma}-{mh} (visitante)"
    return f"Empate {mh}-{ma}"


def _verdict(fx, out):
    p = {"1": out["p_home"], "X": out["p_draw"], "2": out["p_away"]}
    best = max(p, key=p.get)
    if best == "1":
        return f"Gana {fx['home']}"
    if best == "2":
        return f"Gana {fx['away']}"
    return "Empate"
