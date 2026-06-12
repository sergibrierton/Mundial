"""Generación de informes legibles (Markdown + CSV) en output/."""

import sqlite3

import pandas as pd

from config import OUTPUT_DIR, DB_PATH, GROUPS, GROUP_LETTERS


def _pct(x):
    return f"{x*100:4.1f}%"


def write_ratings(ratings_df):
    ratings_df.to_csv(OUTPUT_DIR / "team_ratings.csv", index=False)


def write_group_predictions(pred_df):
    pred_df.to_csv(OUTPUT_DIR / "group_stage_predictions.csv", index=False)
    lines = ["# Predicciones — Fase de grupos (Mundial 2026)\n",
             "Probabilidades 1-X-2, goles esperados (xG) y marcador más probable "
             "para los 72 partidos.\n"]
    for g in GROUP_LETTERS:
        sub = pred_df[pred_df.group == g]
        lines.append(f"\n## Grupo {g}\n")
        lines.append("| Fecha | Partido | 1 | X | 2 | xG | Marcador | Pronóstico |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for _, r in sub.iterrows():
            lines.append(
                f"| {r.date} | {r.home} vs {r.away} | {r.p_home}% | {r.p_draw}% | "
                f"{r.p_away}% | {r.xg_home:.1f}-{r.xg_away:.1f} | "
                f"{r.likely_score} ({r.likely_score_pct}%) | {r.prediction} |")
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
        L.append("| Fecha | Partido | **Resultado** | Prob. | Alternativos | 1 / X / 2 | xG | Goleadores probables |")
        L.append("|---|---|---|---|---|---|---|---|")
        for _, r in sub.iterrows():
            L.append(
                f"| {r.date} | {r.home} – {r.away} | **{r.exact_score}** | "
                f"{r.exact_prob}% | {r.alt_scores} | {r.p_home}/{r.p_draw}/{r.p_away} | "
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


def write_forecast(sim_df):
    sim_df.to_csv(OUTPUT_DIR / "tournament_forecast.csv", index=False)


def write_summary(sim_df, ratings_df, model, n_sims):
    """Informe maestro en español: PREDICCIONES.md."""
    L = []
    L.append("# 🏆 Predicción Mundial 2026 — Informe maestro\n")
    L.append(f"Simulación Monte Carlo de **{n_sims:,} torneos** completos, basada en "
             "ratings Elo calculados sobre **todo el histórico de partidos "
             "internacionales (1872–2026)** y un modelo de goles de Poisson "
             "con corrección de Dixon-Coles.\n")
    L.append(f"> Parámetros del modelo de goles: a={model.a:.3f}, "
             f"b={model.b:.5f} (por punto Elo), ρ={model.rho:.3f}.\n")

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
