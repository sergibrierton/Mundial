"""Modelo de goles: convierte una diferencia de Elo en goles esperados.

Se ajusta sobre el histórico moderno (>=1990) un modelo de Poisson con
"supremacía" simétrica:

    log(lambda_local)     = a + b * dr
    log(lambda_visitante) = a - b * dr

donde dr es la diferencia de Elo efectiva (incluida la ventaja de campo).
Se añade la corrección de Dixon-Coles (rho) para los marcadores bajos, que
mejora el ajuste de empates y resultados 0-0 / 1-1.

Con los lambda se obtiene:
  - la matriz de probabilidades de marcador,
  - las probabilidades 1-X-2,
  - el marcador más probable.
"""

import math

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson


def _dc_tau(h, a, lam, mu, rho):
    """Factor de corrección de Dixon-Coles para marcadores bajos."""
    if h == 0 and a == 0:
        return 1.0 - lam * mu * rho
    if h == 0 and a == 1:
        return 1.0 + lam * rho
    if h == 1 and a == 0:
        return 1.0 + mu * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


class GoalModel:
    def __init__(self, a, b, rho):
        self.a = a
        self.b = b
        self.rho = rho

    # ---- ajuste ----
    @classmethod
    def fit(cls, calibration):
        dr = np.array([c[0] for c in calibration], dtype=float)
        hs = np.array([c[1] for c in calibration], dtype=float)
        as_ = np.array([c[2] for c in calibration], dtype=float)
        # Escalamos dr para estabilidad numérica del optimizador.
        scale = 400.0

        def nll(params):
            a, b, rho = params
            x = b * dr / scale
            lam = np.exp(a + x)
            mu = np.exp(a - x)
            ll = (hs * np.log(lam) - lam) + (as_ * np.log(mu) - mu)
            # Corrección Dixon-Coles sólo en celdas bajas
            low = (hs <= 1) & (as_ <= 1)
            if np.any(low):
                lam_l, mu_l = lam[low], mu[low]
                h_l, a_l = hs[low], as_[low]
                tau = np.ones_like(lam_l)
                m00 = (h_l == 0) & (a_l == 0)
                m01 = (h_l == 0) & (a_l == 1)
                m10 = (h_l == 1) & (a_l == 0)
                m11 = (h_l == 1) & (a_l == 1)
                tau[m00] = 1.0 - lam_l[m00] * mu_l[m00] * rho
                tau[m01] = 1.0 + lam_l[m01] * rho
                tau[m10] = 1.0 + mu_l[m10] * rho
                tau[m11] = 1.0 - rho
                tau = np.clip(tau, 1e-6, None)
                ll[low] += np.log(tau)
            return -np.sum(ll)

        res = minimize(nll, x0=[0.2, 1.0, 0.05], method="Nelder-Mead",
                       options={"maxiter": 5000, "xatol": 1e-6, "fatol": 1e-6})
        a, b, rho = res.x
        # b se ajustó sobre dr/scale -> guardamos b efectiva por unidad de dr.
        model = cls(a=a, b=b / scale, rho=rho)
        model.fit_result = res
        return model

    # ---- predicción ----
    # ha_points: ventaja del local en puntos Elo (ya incluye ventaja de campo
    # y, en su caso, bonus de anfitrión). 0 = sede neutral.
    def lambdas(self, elo_home, elo_away, ha_points):
        dr = elo_home - elo_away + ha_points
        x = self.b * dr
        lam = math.exp(self.a + x)
        mu = math.exp(self.a - x)
        return lam, mu

    def score_matrix(self, elo_home, elo_away, ha_points, max_goals=10):
        lam, mu = self.lambdas(elo_home, elo_away, ha_points)
        ph = poisson.pmf(np.arange(max_goals + 1), lam)
        pa = poisson.pmf(np.arange(max_goals + 1), mu)
        m = np.outer(ph, pa)
        # Corrección Dixon-Coles en las cuatro celdas bajas
        m[0, 0] *= 1.0 - lam * mu * self.rho
        m[0, 1] *= 1.0 + lam * self.rho
        m[1, 0] *= 1.0 + mu * self.rho
        m[1, 1] *= 1.0 - self.rho
        m /= m.sum()
        return m, lam, mu

    def outcome_probs(self, elo_home, elo_away, ha_points, max_goals=10):
        m, lam, mu = self.score_matrix(elo_home, elo_away, ha_points, max_goals)
        p_home = np.tril(m, -1).sum()   # local marca más
        p_draw = np.trace(m)
        p_away = np.triu(m, 1).sum()
        idx = np.unravel_index(np.argmax(m), m.shape)
        return {
            "p_home": float(p_home),
            "p_draw": float(p_draw),
            "p_away": float(p_away),
            "exp_home": float(lam),
            "exp_away": float(mu),
            "likely_score": (int(idx[0]), int(idx[1])),
            "likely_score_prob": float(m[idx]),
        }
