"""Predicciones partido a partido de la fase de grupos del Mundial 2026.

Para cada uno de los 72 partidos calcula de forma analítica (sin simulación):
  - probabilidad de victoria local / empate / victoria visitante (1-X-2),
  - goles esperados de cada equipo,
  - marcador más probable y su probabilidad.
"""

import pandas as pd

from config import ELO_INITIAL


def predict_group_matches(ratings, model, fixtures):
    rows = []
    for fx in fixtures:
        eh = ratings.get(fx["home"], ELO_INITIAL)
        ea = ratings.get(fx["away"], ELO_INITIAL)
        out = model.outcome_probs(eh, ea, fx["ha_side"])
        ls = out["likely_score"]
        rows.append({
            "date": fx["date"],
            "group": fx["grp"],
            "home": fx["home"],
            "away": fx["away"],
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


def _verdict(fx, out):
    p = {"1": out["p_home"], "X": out["p_draw"], "2": out["p_away"]}
    best = max(p, key=p.get)
    if best == "1":
        return f"Gana {fx['home']}"
    if best == "2":
        return f"Gana {fx['away']}"
    return "Empate"
