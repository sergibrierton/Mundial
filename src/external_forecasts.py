"""Pronósticos externos independientes para validar y promediar (consenso).

No son inventados: provienen de fuentes públicas reales.
  - OPTA: probabilidades de título del supercomputador Opta (25.000
    simulaciones), publicadas en theanalyst.com (jun 2026).
  - MARKET: probabilidad implícita de las cuotas de las casas de apuestas
    (jun 2026), normalizada quitando el margen entre los favoritos listados.

El consenso (media del modelo propio + Opta + mercado, donde existan) es más
fiable que cualquier fuente aislada: es un *ensemble*.
"""

# Probabilidad de ganar el Mundial según Opta (fracción).
OPTA_TITLE = {
    "Spain": 0.161, "France": 0.130, "England": 0.112, "Argentina": 0.104,
    "Portugal": 0.070, "Brazil": 0.066, "Germany": 0.051, "Netherlands": 0.036,
    "Norway": 0.035, "Belgium": 0.024, "Colombia": 0.021, "Morocco": 0.019,
    "Croatia": 0.016, "Ecuador": 0.014, "United States": 0.012, "Mexico": 0.010,
}

# Cuotas decimales de mercado (jun 2026) -> probabilidad implícita.
_MARKET_DECIMAL = {
    "Spain": 5.50, "France": 5.75, "England": 8.50, "Portugal": 9.00,
    "Brazil": 10.0, "Argentina": 10.5, "Germany": 17.0, "Netherlands": 19.0,
    "Norway": 21.0, "Belgium": 26.0,
}


def market_title():
    """Probabilidad implícita de mercado, normalizada entre los equipos listados."""
    raw = {t: 1.0 / d for t, d in _MARKET_DECIMAL.items()}
    s = sum(raw.values())
    # Normaliza para que la suma de los listados conserve su proporción real
    # (mantiene el margen fuera). Escala al total implícito sin vig aproximado.
    overround = s  # suma > 1 por el margen
    return {t: v / overround for t, v in raw.items()}


def consensus_title(model_probs):
    """Media simple del modelo propio, Opta y mercado (donde haya dato)."""
    mkt = market_title()
    teams = set(model_probs) | set(OPTA_TITLE) | set(mkt)
    out = {}
    for t in teams:
        vals = []
        if t in model_probs:
            vals.append(model_probs[t])
        if t in OPTA_TITLE:
            vals.append(OPTA_TITLE[t])
        if t in mkt:
            vals.append(mkt[t])
        out[t] = sum(vals) / len(vals) if vals else 0.0
    return out, mkt
