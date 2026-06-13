"""Generación de informes legibles (Markdown + CSV) en output/."""

import sqlite3

import pandas as pd

from config import OUTPUT_DIR, DB_PATH, GROUPS, GROUP_LETTERS


def _pct(x):
    return f"{x*100:4.1f}%"


def write_ratings(ratings_df):
    ratings_df.to_csv(OUTPUT_DIR / "team_ratings.csv", index=False)


def write_eval(eval_df, metrics):
    """Backtest del modelo en los partidos ya jugados."""
    eval_df.to_csv(OUTPUT_DIR / "backtest.csv", index=False)
    L = ["# 📏 Backtest — rendimiento del modelo en partidos ya jugados\n",
         f"Evaluado sobre **{metrics['n']} partidos** con el Elo **previo** a "
         "cada partido (sin información del futuro).\n",
         f"- **Acierto 1-X-2:** {metrics['acc_1x2']*100:.0f}%",
         f"- **Acierto marcador exacto:** {metrics['acc_exact']*100:.0f}%",
         f"- **Brier score:** {metrics['brier']:.3f} (0 = perfecto)",
         f"- **Log-loss:** {metrics['logloss']:.3f}\n",
         "| Fecha | Partido | Pred 1X2 | Real | P(1/X/2) | Pred. marcador | 1X2 | Exacto |",
         "|---|---|---|---|---|---|---|---|"]
    for _, r in eval_df.iterrows():
        L.append(f"| {r.date} | {r['match']} | {r.pred_1x2} | {r.real_1x2} | "
                 f"{r['p(1/X/2)']} | {r.pred_score} | {r.acierto_1x2} | {r.acierto_exacto} |")
    (OUTPUT_DIR / "backtest.md").write_text("\n".join(L), encoding="utf-8")


def write_group_predictions(pred_df):
    pred_df.to_csv(OUTPUT_DIR / "group_stage_predictions.csv", index=False)
    lines = ["# Predicciones — Fase de grupos (Mundial 2026)\n",
             "Probabilidades 1-X-2, goles esperados (xG) y marcador más probable. "
             "Los partidos ya jugados muestran su **resultado real**.\n"]
    for g in GROUP_LETTERS:
        sub = pred_df[pred_df.group == g]
        lines.append(f"\n## Grupo {g}\n")
        lines.append("| Fecha | Partido | Estado | 1 | X | 2 | xG | Predicción | Real |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for _, r in sub.iterrows():
            real = f"**{r.real_score}**" if r.status == "JUGADO" else "—"
            lines.append(
                f"| {r.date} | {r.home} vs {r.away} | {r.status} | {r.p_home}% | "
                f"{r.p_draw}% | {r.p_away}% | {r.xg_home:.1f}-{r.xg_away:.1f} | "
                f"{r.likely_score} | {real} |")
    (OUTPUT_DIR / "group_stage_predictions.md").write_text("\n".join(lines), encoding="utf-8")


def write_exact_predictions(exact_df):
    """Marcadores exactos de los 72 partidos (Markdown + CSV)."""
    exact_df.to_csv(OUTPUT_DIR / "group_stage_exact_results.csv", index=False)
    L = ["# 🎯 Marcadores exactos previstos — Fase de grupos (Mundial 2026)\n",
         "Marcador **exacto más probable** de cada partido (modal de la distribución "
         "de Poisson), con marcadores alternativos, probabilidades 1-X-2, goles "
         "esperados (xG) y goleadores más probables de cada selección.\n",
         "> Aviso: el marcador exacto es de baja probabilidad por naturaleza "
         "(~12–18%). Es el resultado **individual más probable**; el pronóstico "
         "1-X-2 es mucho más fiable.\n"]
    for g in GROUP_LETTERS:
        sub = exact_df[exact_df.group == g]
        L.append(f"\n## Grupo {g}\n")
        L.append("| Fecha | Partido | **Pronóstico** | Prob. | Real | 1 / X / 2 | xG | Goleadores probables |")
        L.append("|---|---|---|---|---|---|---|---|")
        for _, r in sub.iterrows():
            real = f"**{r.real_score}** ✅" if r.status == "JUGADO" else "—"
            L.append(
                f"| {r.date} | {r.home} – {r.away} | **{r.exact_score}** | "
                f"{r.exact_prob}% | {real} | {r.p_home}/{r.p_draw}/{r.p_away} | "
                f"{r.xg_home:.1f}-{r.xg_away:.1f} | {r.scorer_home} vs {r.scorer_away} |")
    (OUTPUT_DIR / "group_stage_exact_results.md").write_text("\n".join(L), encoding="utf-8")


def write_players(players_summary):
    """Análisis jugador a jugador por selección."""
    players_summary.to_csv(OUTPUT_DIR / "player_analysis.csv", index=False)
    df = players_summary.sort_values("elo_adj", ascending=False)
    L = ["# 👤 Análisis jugador a jugador (forma ofensiva 2022–2026)\n",
         "Goleadores activos de cada selección (goles internacionales desde 2022), "
         "índice de amenaza ofensiva, dependencia de la estrella y el ajuste de "
         "rating que aporta la calidad goleadora de la plantilla.\n",
         "| Selección | Ajuste Elo | Estrella | Goles | Dependencia | Goleadores activos (goles) |",
         "|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r.team} | {r.elo_adj:+.0f} | {r.star} | {r.star_goals} | "
                 f"{int(r.star_reliance*100)}% | {r.top_scorers} |")
    (OUTPUT_DIR / "player_analysis.md").write_text("\n".join(L), encoding="utf-8")


def write_consensus(sim_df):
    """Compara el modelo propio con Opta y el mercado, y calcula el consenso.

    Devuelve el dict de consenso para usarlo en el resumen.
    """
    from external_forecasts import OPTA_TITLE, consensus_title
    model_probs = dict(zip(sim_df.team, sim_df.champion))
    cons, mkt = consensus_title(model_probs)
    rows = []
    teams = sorted(cons, key=lambda t: -cons[t])
    for t in teams:
        if cons[t] < 0.005:
            continue
        rows.append({
            "team": t,
            "modelo": model_probs.get(t, float("nan")),
            "opta": OPTA_TITLE.get(t, float("nan")),
            "mercado": mkt.get(t, float("nan")),
            "consenso": cons[t],
        })
    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_DIR / "consensus_title.csv", index=False)

    def f(x):
        return "—" if x != x else f"{x*100:.1f}%"

    L = ["# 🤝 Consenso de pronósticos — Campeón del Mundial 2026\n",
         "Cruce del **modelo propio** (Elo histórico + plantilla + anclaje al "
         "Ranking FIFA) con el **supercomputador Opta** y el **mercado de "
         "apuestas**. El **consenso** es la media de las fuentes disponibles: "
         "es el pronóstico más fiable (ensemble), no depende de un solo método.\n",
         "| # | Selección | Modelo | Opta | Mercado | **Consenso** |",
         "|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i} | {r['team']} | {f(r['modelo'])} | {f(r['opta'])} | "
                 f"{f(r['mercado'])} | **{f(r['consenso'])}** |")
    L.append("\n> Fuentes: Opta (theanalyst.com, jun 2026); cuotas de mercado "
             "(jun 2026). El consenso reduce el sesgo de cualquier modelo aislado.\n")
    (OUTPUT_DIR / "consensus_title.md").write_text("\n".join(L), encoding="utf-8")
    return cons


def write_forecast(sim_df):
    sim_df.to_csv(OUTPUT_DIR / "tournament_forecast.csv", index=False)


def write_summary(sim_df, ratings_df, model, n_sims, consensus=None):
    """Informe maestro en español: PREDICCIONES.md."""
    L = []
    L.append("# 🏆 Predicción Mundial 2026 — Informe maestro\n")
    L.append(f"Simulación Monte Carlo de **{n_sims:,} torneos** completos, basada en "
             "ratings Elo (histórico 1872–2026) + análisis de plantilla + "
             "**anclaje al Ranking Mundial FIFA**, con modelo de goles de Poisson "
             "(Dixon-Coles). Condicionada a los partidos ya jugados.\n")

    if consensus:
        from external_forecasts import OPTA_TITLE, market_title
        mkt = market_title()
        model_probs = dict(zip(sim_df.team, sim_df.champion))
        L.append("\n## 🤝 Consenso — Campeón (modelo + Opta + mercado)\n")
        L.append("Pronóstico más fiable: media de tres fuentes independientes.\n")
        L.append("| # | Selección | Modelo | Opta | Mercado | **Consenso** |")
        L.append("|---|---|---|---|---|---|")
        top = sorted(consensus, key=lambda t: -consensus[t])
        for i, t in enumerate([x for x in top if consensus[x] >= 0.005], 1):
            def f(x):
                return "—" if x is None else f"{x*100:.1f}%"
            L.append(f"| {i} | {t} | {f(model_probs.get(t))} | "
                     f"{f(OPTA_TITLE.get(t))} | {f(mkt.get(t))} | "
                     f"**{f(consensus[t])}** |")

    L.append(f"\n> Parámetros: modelo de goles a={model.a:.3f}, "
             f"b={model.b:.5f}/punto Elo, ρ={model.rho:.3f}; "
             "ventaja de campo 85 Elo; bonus anfitrión 35 Elo; "
             "incertidumbre σ=120 Elo (calibrada al consenso).\n")

    # ---- Favoritos al título ----
    L.append("\n## Favoritos al título\n")
    L.append("| # | Selección | Elo | Campeón | Final | Semis | Cuartos | Octavos | Clasifica |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    elo_map = dict(zip(ratings_df.team, ratings_df.elo))
    for _, r in sim_df.head(16).iterrows():
        L.append(
            f"| {r['rank']} | {r.team} | {elo_map.get(r.team, 0):.0f} | "
            f"**{_pct(r.champion)}** | {_pct(r.reach_final)} | {_pct(r.reach_SF)} | "
            f"{_pct(r.reach_QF)} | {_pct(r.reach_R16)} | {_pct(r.advance)} |")

    # ---- Ranking Elo completo ----
    L.append("\n## Ranking Elo de las 48 selecciones\n")
    L.append("| # | Selección | Elo | Forma (pts/partido) | GF | GA |")
    L.append("|---|---|---|---|---|---|")
    for _, r in ratings_df.iterrows():
        L.append(f"| {r['rank']} | {r.team} | {r.elo:.0f} | {r.form_ppg} | "
                 f"{r.form_gf} | {r.form_ga} |")

    # ---- Probabilidades por grupo ----
    L.append("\n## Clasificación por grupos (probabilidades)\n")
    sim_map = sim_df.set_index("team")
    for g in GROUP_LETTERS:
        L.append(f"\n### Grupo {g}\n")
        L.append("| Selección | Gana grupo | 2.º | Pasa como 3.º | Clasifica (top-2) | Avanza a 16avos |")
        L.append("|---|---|---|---|---|---|")
        members = sorted(GROUPS[g], key=lambda t: -sim_map.loc[t, "advance"])
        for t in members:
            r = sim_map.loc[t]
            top2 = r.win_group + r.runner_up
            L.append(f"| {t} | {_pct(r.win_group)} | {_pct(r.runner_up)} | "
                     f"{_pct(r.qualify_3rd)} | {_pct(top2)} | {_pct(r.advance)} |")

    # ---- Pronóstico narrativo ----
    champ = sim_df.iloc[0]
    runner = sim_df.iloc[1]
    L.append("\n## Pronóstico\n")
    L.append(f"- **Campeón más probable:** {champ.team} ({_pct(champ.champion)} de "
             f"ganar el título).")
    L.append(f"- **Principal rival:** {runner.team} ({_pct(runner.champion)}).")
    dark = sim_df.iloc[8:14]
    L.append("- **Tapados / outsiders con opciones:** " +
             ", ".join(f"{r.team} ({_pct(r.champion)})" for _, r in dark.iterrows()) + ".")
    L.append("\n> Metodología y limitaciones detalladas en `README.md`. "
             "Predicción probabilística: ninguna selección está garantizada.\n")

    (OUTPUT_DIR / "PREDICCIONES.md").write_text("\n".join(L), encoding="utf-8")


def write_stats():
    """Vuelca estadísticas históricas agregadas a output/."""
    conn = sqlite3.connect(DB_PATH)
    ts = pd.read_sql_query("SELECT * FROM team_stats ORDER BY win_pct DESC", conn)
    ts.to_csv(OUTPUT_DIR / "team_historical_stats.csv", index=False)
    conn.close()
    return ts
