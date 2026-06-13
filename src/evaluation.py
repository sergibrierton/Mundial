"""Backtest honesto del modelo sobre los partidos del Mundial ya jugados.

Para cada partido disputado usa el Elo **previo al partido** (snapshot tomado
durante el cálculo cronológico de ratings) más el ajuste por plantilla y la
ventaja de campo/anfitrión, y compara la predicción con el resultado real.

Métricas:
  - acierto 1-X-2 (signo del resultado),
  - acierto del marcador exacto,
  - Brier score multiclase (0 = perfecto, menor es mejor),
  - log-loss.
"""

import math

import numpy as np
import pandas as pd


def evaluate(wc_prematch, player_adj, model, fixtures):
    rows = []
    brier_sum = 0.0
    logloss_sum = 0.0
    hit_1x2 = 0
    hit_exact = 0
    n = 0
    for fx in fixtures:
        if not fx.get("played"):
            continue
        key = (fx["date"], fx["home"], fx["away"])
        if key not in wc_prematch:
            continue
        rh, ra = wc_prematch[key]
        eh = rh + player_adj.get(fx["home"], 0.0)
        ea = ra + player_adj.get(fx["away"], 0.0)
        out = model.outcome_probs(eh, ea, fx["ha_points"])
        ph, pdr, pa = out["p_home"], out["p_draw"], out["p_away"]

        hs, as_ = int(fx["home_score"]), int(fx["away_score"])
        actual = "1" if hs > as_ else ("2" if hs < as_ else "X")
        probs = {"1": ph, "X": pdr, "2": pa}
        pred = max(probs, key=probs.get)
        ls = out["likely_score"]

        ok_1x2 = pred == actual
        ok_exact = (ls[0] == hs and ls[1] == as_)
        hit_1x2 += ok_1x2
        hit_exact += ok_exact
        n += 1

        y = {"1": 0.0, "X": 0.0, "2": 0.0}
        y[actual] = 1.0
        brier_sum += sum((probs[k] - y[k]) ** 2 for k in probs)
        logloss_sum += -math.log(max(probs[actual], 1e-9))

        rows.append({
            "date": fx["date"],
            "match": f"{fx['home']} {hs}-{as_} {fx['away']}",
            "pred_1x2": pred,
            "real_1x2": actual,
            "p(1/X/2)": f"{ph*100:.0f}/{pdr*100:.0f}/{pa*100:.0f}",
            "pred_score": f"{ls[0]}-{ls[1]}",
            "acierto_1x2": "✓" if ok_1x2 else "✗",
            "acierto_exacto": "✓" if ok_exact else "✗",
        })

    metrics = {
        "n": n,
        "acc_1x2": hit_1x2 / n if n else 0.0,
        "acc_exact": hit_exact / n if n else 0.0,
        "brier": brier_sum / n if n else 0.0,
        "logloss": logloss_sum / n if n else 0.0,
    }
    return pd.DataFrame(rows), metrics
