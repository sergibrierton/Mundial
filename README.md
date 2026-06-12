# ⚽ Mundial 2026 — Base de datos histórica + sistema de predicciones

Proyecto que genera **en local** una base de datos con **todo el histórico de
partidos internacionales** de las 48 selecciones del Mundial 2026, calcula
estadísticas de todo tipo y produce un **sistema de predicción** del torneo lo
más verídico posible mediante ratings Elo, un modelo de goles de Poisson
(con corrección de Dixon-Coles) y simulación Monte Carlo del cuadro completo.

---

## 🚀 Uso rápido

```bash
pip install -r requirements.txt
python run_all.py            # pipeline completo (50.000 torneos simulados)
```

Opciones:

```bash
python run_all.py --sims 100000     # más simulaciones (más precisión)
python run_all.py --skip-download   # no volver a descargar los datos
python run_all.py --rebuild-db      # regenerar la base de datos
```

Todo termina en unos segundos. Los resultados se escriben en `output/`.

---

## 📊 Resultados (lo que se genera)

| Fichero | Contenido |
|---|---|
| `output/PREDICCIONES.md` | **Informe maestro**: favoritos al título, ranking Elo de las 48, probabilidades por grupo y pronóstico. |
| `output/group_stage_predictions.md` / `.csv` | Predicción 1-X-2, goles esperados y marcador más probable de los **72 partidos** de fase de grupos. |
| `output/tournament_forecast.csv` | Probabilidad por selección de ganar grupo, clasificar y alcanzar cada ronda hasta el título. |
| `output/team_ratings.csv` | Rating Elo y forma reciente de cada selección. |
| `output/team_historical_stats.csv` | Estadísticas históricas agregadas (PJ, V/E/D, GF/GA, % victorias, partidos de Mundial). |

La base de datos SQLite `data/mundial.db` queda disponible para consultas
propias (tablas `matches`, `goalscorers`, `shootouts`, `head_to_head`,
`team_stats`, `wc2026_fixtures`).

---

## 🗄️ Datos

Fuente: **[martj42/international_results](https://github.com/martj42/international_results)**,
dataset abierto con **todos los partidos internacionales de selecciones masculinas
desde 1872** (49.000+ partidos), goleadores y tandas de penaltis. Se descarga
automáticamente.

- Se aplica el mapa de **nombres antiguos → actuales** para dar continuidad
  histórica (p. ej. *Zaïre → DR Congo*, *Netherlands Antilles → Curaçao*,
  *Unión Soviética → Rusia*).
- El **calendario real del Mundial 2026** (72 partidos de grupos, con sedes) ya
  viene codificado en el dataset; los 12 grupos se derivan de los propios
  enfrentamientos y se han **verificado de forma cruzada con el sorteo oficial
  de la FIFA**.

### Estructura del torneo (verificada)

- **48 selecciones**, **12 grupos** (A–L) de 4 equipos.
- Avanzan **1.º y 2.º de cada grupo + los 8 mejores terceros** → Dieciseisavos
  (Round of 32).
- Cuadro de eliminatorias oficial: 16avos → Octavos → Cuartos → Semis → Final,
  con la asignación de terceros a cada hueco respetando las **restricciones
  oficiales de elegibilidad por grupo**.

---

## 🧠 Metodología de predicción

1. **Ratings Elo** (estilo *World Football Elo*) calculados recorriendo
   cronológicamente los 49.000+ partidos:
   - Factor **K** según la importancia del partido (Mundial 60, finales
     continentales 50, clasificatorios/Nations League 40, amistosos 20…).
   - Ajuste por **margen de goles** y por **ventaja de campo**.
   - El Elo capta intrínsecamente la **forma reciente** (se actualiza partido a
     partido).

2. **Modelo de goles** (Poisson + Dixon-Coles): se ajusta sobre el fútbol
   moderno (≥1990) la relación entre la diferencia de Elo y los goles esperados:

   ```
   log(λ_local)     = a + b · Δelo
   log(λ_visitante) = a − b · Δelo
   ```

   con corrección de Dixon-Coles (ρ) para marcadores bajos. De ahí salen las
   probabilidades 1-X-2 y el marcador más probable de cada partido.

3. **Simulación Monte Carlo** (50.000 torneos): se juegan los 72 partidos de
   grupos (con sus sedes y ventaja de campo reales), se aplican los
   **desempates FIFA** (puntos → diferencia de goles → goles a favor), se
   eligen los 8 mejores terceros y se resuelve **todo el cuadro de
   eliminatorias**. Los empates en eliminatoria se deciden con una moneda
   ponderada por Elo (prórroga + penaltis).

4. **Incertidumbre de forma**: en cada simulación se perturba el Elo de cada
   selección con ruido gaussiano (σ≈40 puntos), reflejando que el rating es una
   estimación y no una certeza (lesiones, estado de forma, factor sorteo). Esto
   ensancha la distribución de resultados de forma realista.

---

## ⚠️ Limitaciones (honestidad metodológica)

- Es un modelo **probabilístico**: ninguna selección está garantizada. Una
  probabilidad de campeón del 25 % significa que en 3 de cada 4 mundiales
  simulados ese equipo **no** gana.
- Al estar basado en Elo, el modelo tiende a **favorecer al equipo mejor
  valorado**; las casas de apuestas suelen mostrar un reparto algo más plano.
- No modela explícitamente lesiones de jugadores concretos, bajas, ni el valor
  de plantilla a nivel individual; trabaja a nivel de **selección**.
- Los desempates de grupo implementan puntos/DG/GF (no el head-to-head completo
  ni el fair-play), con impacto marginal en las probabilidades agregadas.

---

## 📁 Estructura del proyecto

```
Mundial/
├── run_all.py            # pipeline completo
├── requirements.txt
├── src/
│   ├── config.py         # grupos, sedes, cuadro y parámetros del modelo
│   ├── download_data.py  # descarga de datasets
│   ├── build_database.py # construcción de SQLite + estadísticas
│   ├── ratings.py        # ratings Elo + forma reciente
│   ├── model.py          # modelo de goles Poisson + Dixon-Coles
│   ├── fixtures.py       # carga de los 72 partidos con ventaja de campo
│   ├── predict.py        # predicción partido a partido
│   ├── simulate.py       # simulación Monte Carlo del torneo
│   └── report.py         # generación de informes
├── data/                 # (generado) datos crudos + mundial.db
└── output/               # (generado) predicciones e informes
```
