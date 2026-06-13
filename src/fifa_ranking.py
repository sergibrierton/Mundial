"""Anclaje al Ranking Mundial FIFA oficial (fuente externa e independiente).

El Elo basado en resultados puede desviarse de la valoración FIFA (estándar
oficial). Anclar a FIFA:
  - corrige infravaloraciones e inflados puntuales (p. ej. el modelo inflaba a
    Noruega #31 y Ecuador #23, y comprimía a Inglaterra #4),
  - lleva la cima a la paridad real (Argentina/España/Francia casi empatadas).

Datos: puntos FIFA exactos del top-20 (actualización 11 jun 2026) y posición
FIFA de las 48 selecciones (junio 2026 / sorteo nov 2025). Para los equipos sin
punto exacto se estima a partir de la posición mediante interpolación calibrada
con la curva real de puntos FIFA. Fuentes: FIFA, Wikipedia, ESPN.
"""

import numpy as np

# Puntos FIFA exactos (top-20, jun 2026) de selecciones del Mundial.
FIFA_POINTS_EXACT = {
    "Argentina": 1877.27, "Spain": 1874.71, "France": 1870.70,
    "England": 1828.02, "Portugal": 1767.85, "Brazil": 1765.86,
    "Morocco": 1755.10, "Netherlands": 1753.57, "Belgium": 1742.24,
    "Germany": 1735.77, "Croatia": 1714.87, "Colombia": 1698.35,
    "Mexico": 1687.48, "Senegal": 1684.07, "Uruguay": 1673.07,
    "United States": 1671.23, "Japan": 1661.58, "Switzerland": 1650.06,
    "Iran": 1619.58,
}

# Posición FIFA de las 48 selecciones (jun 2026; algunas del sorteo nov 2025).
FIFA_RANK = {
    "Argentina": 1, "Spain": 2, "France": 3, "England": 4, "Portugal": 5,
    "Brazil": 6, "Morocco": 7, "Netherlands": 8, "Belgium": 9, "Germany": 10,
    "Croatia": 11, "Colombia": 13, "Mexico": 14, "Senegal": 15, "Uruguay": 16,
    "United States": 17, "Japan": 18, "Switzerland": 19, "Iran": 20,
    "Ecuador": 23, "Austria": 24, "South Korea": 25, "Turkey": 26,
    "Australia": 27, "Algeria": 28, "Egypt": 29, "Canada": 30, "Norway": 31,
    "Ivory Coast": 33, "Panama": 34, "Sweden": 38, "Paraguay": 41,
    "Scotland": 42, "Czech Republic": 43, "Tunisia": 45, "DR Congo": 46,
    "Uzbekistan": 50, "Qatar": 56, "Iraq": 57, "South Africa": 60,
    "Saudi Arabia": 61, "Jordan": 63, "Bosnia and Herzegovina": 64,
    "Cape Verde": 67, "Ghana": 73, "Curaçao": 82, "Haiti": 83,
    "New Zealand": 85,
}

# Anclas (rango -> puntos) para estimar puntos donde no hay valor exacto.
# Calibradas con el top-20 real y la curva típica de puntos FIFA.
_ANCHORS = [(1, 1880), (4, 1828), (11, 1715), (20, 1620), (24, 1585),
            (30, 1540), (35, 1505), (42, 1460), (50, 1420), (60, 1370),
            (70, 1330), (85, 1280)]


def _points_from_rank(rank):
    xs = [a[0] for a in _ANCHORS]
    ys = [a[1] for a in _ANCHORS]
    return float(np.interp(rank, xs, ys))


def fifa_points():
    """Puntos FIFA (exactos o estimados por posición) para las 48 selecciones."""
    pts = {}
    for team, rank in FIFA_RANK.items():
        pts[team] = FIFA_POINTS_EXACT.get(team, _points_from_rank(rank))
    return pts


def blend(ratings, weight_fifa=0.50):
    """Combina el rating propio con FIFA (en la escala del propio Elo).

        rating' = mu_e + sd_e * ((1-w)*z_elo + w*z_fifa)

    Se aplica a todas las selecciones con dato FIFA (las 48), manteniendo una
    única escala coherente.
    """
    pts = fifa_points()
    teams = list(ratings)
    elo = np.array([ratings[t] for t in teams])
    mu_e, sd_e = elo.mean(), elo.std() or 1.0

    fifa_teams = [t for t in teams if t in pts]
    fp = np.array([pts[t] for t in fifa_teams])
    mu_f, sd_f = fp.mean(), fp.std() or 1.0

    out = dict(ratings)
    for t in fifa_teams:
        z_elo = (ratings[t] - mu_e) / sd_e
        z_fifa = (pts[t] - mu_f) / sd_f
        z = (1 - weight_fifa) * z_elo + weight_fifa * z_fifa
        out[t] = mu_e + sd_e * z
    return out
