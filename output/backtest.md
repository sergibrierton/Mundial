# 📏 Backtest — rendimiento del modelo en partidos ya jugados

Evaluado sobre **8 partidos** con el Elo **previo** a cada partido (sin información del futuro).

- **Acierto 1-X-2:** 50%
- **Acierto marcador exacto:** 25%
- **Brier score:** 0.707 (0 = perfecto)
- **Log-loss:** 1.112

| Fecha | Partido | Pred 1X2 | Real | P(1/X/2) | Pred. marcador | 1X2 | Exacto |
|---|---|---|---|---|---|---|---|
| 2026-06-11 | Mexico 2-0 South Africa | 1 | 1 | 84/12/4 | 2-0 | ✓ | ✓ |
| 2026-06-11 | South Korea 2-1 Czech Republic | 1 | 1 | 44/28/28 | 1-1 | ✓ | ✗ |
| 2026-06-12 | Canada 1-1 Bosnia and Herzegovina | 1 | X | 77/16/7 | 2-0 | ✗ | ✗ |
| 2026-06-12 | United States 4-1 Paraguay | 1 | 1 | 41/29/30 | 1-1 | ✓ | ✗ |
| 2026-06-13 | Qatar 1-1 Switzerland | 2 | X | 6/14/81 | 0-2 | ✗ | ✗ |
| 2026-06-13 | Brazil 1-1 Morocco | 1 | X | 45/28/27 | 1-1 | ✗ | ✓ |
| 2026-06-13 | Haiti 0-1 Scotland | 2 | 2 | 20/26/54 | 1-1 | ✓ | ✗ |
| 2026-06-13 | Australia 2-0 Turkey | 2 | 1 | 27/28/45 | 1-1 | ✗ | ✗ |