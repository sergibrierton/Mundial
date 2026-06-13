# 📏 Backtest — rendimiento del modelo en partidos ya jugados

Evaluado sobre **4 partidos** con el Elo **previo** a cada partido (sin información del futuro).

- **Acierto 1-X-2:** 75%
- **Acierto marcador exacto:** 25%
- **Brier score:** 0.583 (0 = perfecto)
- **Log-loss:** 0.929

| Fecha | Partido | Pred 1X2 | Real | P(1/X/2) | Pred. marcador | 1X2 | Exacto |
|---|---|---|---|---|---|---|---|
| 2026-06-11 | Mexico 2-0 South Africa | 1 | 1 | 84/12/4 | 2-0 | ✓ | ✓ |
| 2026-06-11 | South Korea 2-1 Czech Republic | 1 | 1 | 44/28/28 | 1-1 | ✓ | ✗ |
| 2026-06-12 | Canada 1-1 Bosnia and Herzegovina | 1 | X | 77/16/7 | 2-0 | ✗ | ✗ |
| 2026-06-12 | United States 4-1 Paraguay | 1 | 1 | 41/29/30 | 1-1 | ✓ | ✗ |