#!/usr/bin/env python3
"""Pipeline completo del proyecto Mundial 2026.

Ejecuta de principio a fin:
  1. Descarga de los datasets históricos.
  2. Construcción de la base de datos SQLite + estadísticas.
  3. Cálculo de ratings Elo sobre todo el histórico.
  4. Ajuste del modelo de goles (Poisson + Dixon-Coles).
  5. Predicciones partido a partido de la fase de grupos.
  6. Simulación Monte Carlo del torneo completo.
  7. Generación de informes (Markdown + CSV) en output/.

Uso:
    python run_all.py [--sims N] [--seed S] [--skip-download]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from config import DEFAULT_SIMULATIONS, RANDOM_SEED  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=DEFAULT_SIMULATIONS)
    ap.add_argument("--seed", type=int, default=RANDOM_SEED)
    ap.add_argument("--sigma", type=float, default=None,
                    help="incertidumbre Elo por simulación (calibra la concentración)")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--rebuild-db", action="store_true")
    args = ap.parse_args()

    import download_data
    import build_database
    import ratings as ratings_mod
    import players as players_mod
    import fifa_ranking
    from model import GoalModel
    from fixtures import load_fixtures
    from predict import predict_group_matches, predict_exact
    from simulate import TournamentSimulator
    from evaluation import evaluate
    import report
    from config import DB_PATH

    t0 = time.time()

    print("\n[1/7] Descargando datasets históricos…")
    if not args.skip_download:
        if not download_data.download():
            sys.exit("No se pudieron descargar los datos.")
    else:
        print("  (omitido)")

    print("\n[2/7] Construyendo base de datos SQLite…")
    if args.rebuild_db or not Path(DB_PATH).exists():
        build_database.build()
    else:
        print("  (BD ya existe; usa --rebuild-db para regenerar)")

    print("\n[3/8] Calculando ratings Elo sobre todo el histórico…")
    res = ratings_mod.compute()
    ratings_df = ratings_mod.ratings_table(res)
    print(f"  {len(res['calibration'])} partidos de calibración (>=1990).")

    print("\n[4/8] Análisis jugador a jugador (forma ofensiva)…")
    pl = players_mod.analyze()
    adj = pl["elo_adj"]
    # Rating combinado: Elo histórico + calidad/forma ofensiva de la plantilla.
    ratings = {t: res["ratings"][t] + adj.get(t, 0.0) for t in res["ratings"]}
    # Anclaje al Ranking Mundial FIFA oficial (fuente externa independiente):
    # corrige infravaloraciones y comprime la cima hacia la paridad real.
    ratings = fifa_ranking.blend(ratings)
    ratings_df["elo_hist"] = ratings_df["elo"]
    ratings_df["player_adj"] = ratings_df["team"].map(adj).round(1)
    ratings_df["elo"] = ratings_df["team"].map(lambda t: round(ratings[t], 1))
    ratings_df = ratings_df.sort_values("elo", ascending=False).reset_index(drop=True)
    ratings_df["rank"] = ratings_df.index + 1
    top_attack = pl["summary"].sort_values("elo_adj", ascending=False).head(3)
    print("  Mayor amenaza ofensiva:",
          ", ".join(f"{r.team} ({r.star})" for _, r in top_attack.iterrows()))
    print("  Top 5 rating combinado:",
          ", ".join(f"{r.team} {r.elo:.0f}" for _, r in ratings_df.head(5).iterrows()))

    print("\n[5/8] Ajustando modelo de goles (Poisson + Dixon-Coles)…")
    model = GoalModel.fit(res["calibration"])
    print(f"  a={model.a:.4f}  b={model.b:.6f}  rho={model.rho:.4f}")

    fixtures = load_fixtures()
    n_played = sum(1 for fx in fixtures if fx["played"])
    if n_played:
        print(f"\n[BACKTEST] Evaluando el modelo en los {n_played} partidos ya jugados…")
        eval_df, metrics = evaluate(res["wc_prematch"], adj, model, fixtures)
        print(eval_df.to_string(index=False))
        print(f"  Acierto 1-X-2: {metrics['acc_1x2']*100:.0f}%  |  "
              f"marcador exacto: {metrics['acc_exact']*100:.0f}%  |  "
              f"Brier: {metrics['brier']:.3f}  |  log-loss: {metrics['logloss']:.3f}")
        report.write_eval(eval_df, metrics)

    print(f"\n[6/8] Prediciendo los 72 partidos ({n_played} jugados, "
          f"{72 - n_played} pendientes)…")
    pred_df = predict_group_matches(ratings, model, fixtures)
    exact_df = predict_exact(ratings, model, fixtures, pl["team_players"])
    report.write_group_predictions(pred_df)
    report.write_exact_predictions(exact_df)
    report.write_players(pl["summary"])
    print(f"  {len(pred_df)} partidos predichos (con goleadores probables).")

    print(f"\n[7/8] Simulando {args.sims:,} torneos completos (Monte Carlo)…")
    sim = TournamentSimulator(ratings, model, fixtures, args.sims, args.seed,
                              sigma=args.sigma)
    sim_df = sim.run()
    print("  Top 5 candidatos al título:")
    for _, r in sim_df.head(5).iterrows():
        print(f"    {r.team:<16} campeón {r.champion*100:5.1f}%  "
              f"final {r.reach_final*100:5.1f}%  clasifica {r.advance*100:5.1f}%")

    print("\n[8/8] Generando informes en output/…")
    report.write_ratings(ratings_df)
    report.write_forecast(sim_df)
    report.write_stats()
    consensus = report.write_consensus(sim_df)
    report.write_summary(sim_df, ratings_df, model, args.sims, consensus)
    print("  Consenso (modelo+Opta+mercado) top 3: " +
          ", ".join(f"{t} {consensus[t]*100:.1f}%"
                    for t in sorted(consensus, key=lambda x: -consensus[x])[:3]))
    print("  Escritos: PREDICCIONES.md, group_stage_predictions.{csv,md}, "
          "group_stage_exact_results.{csv,md}, player_analysis.{csv,md}, "
          "team_ratings.csv, tournament_forecast.csv, team_historical_stats.csv")

    print(f"\n✅ Completado en {time.time()-t0:.1f}s. Revisa output/PREDICCIONES.md")


if __name__ == "__main__":
    main()
