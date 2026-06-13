"""Simulación Monte Carlo del Mundial 2026 completo.

Para cada simulación:
  1. Fase de grupos: se juegan los 72 partidos reales (sedes/ventaja de campo
     incluidas). Clasificación por puntos -> diferencia de goles -> goles a favor.
  2. Avanzan 1.º y 2.º de cada grupo + los 8 mejores terceros (ranking FIFA).
  3. Los terceros se asignan a sus huecos del cuadro respetando las
     restricciones oficiales de elegibilidad por grupo.
  4. Eliminatorias: Dieciseisavos -> Octavos -> Cuartos -> Semis -> Final
     siguiendo el cuadro oficial. Los empates en eliminatoria se resuelven con
     una moneda ponderada por Elo (prórroga + penaltis).

Se agregan probabilidades por selección: ganar grupo, clasificar, y alcanzar
cada ronda hasta levantar el título.
"""

import math
from collections import defaultdict
from functools import lru_cache

import numpy as np

from config import (
    GROUPS, GROUP_LETTERS, all_teams, HOSTS, HOST_KO_EXTRA,
    ELO_SIM_SIGMA, R32, R16, QF, SF, THIRD_PLACE_SLOTS, THIRD_PLACE_MATCH,
    FINAL_MATCH,
)

THIRD_SLOT_MATCHES = [m for m in R32 if R32[m][1][0] == "3"]


def _bipartite_match(slots, eligible, qualifying):
    """Asigna cada hueco-de-tercero a un grupo clasificado respetando elegibilidad.

    slots: lista de match_no.  eligible: {match_no: set(letras)}.
    qualifying: tupla ordenada de letras de grupos cuyo tercero clasificó.
    Devuelve {match_no: letra} o None si no hay emparejamiento perfecto.
    """
    assignment = {}
    used = set()

    def candidates(slot):
        return [g for g in eligible[slot] if g in qualifying]

    order = sorted(slots, key=lambda s: len(candidates(s)))  # heurística

    def backtrack(i):
        if i == len(order):
            return True
        slot = order[i]
        for g in candidates(slot):
            if g not in used:
                used.add(g)
                assignment[slot] = g
                if backtrack(i + 1):
                    return True
                used.remove(g)
                del assignment[slot]
        return False

    if backtrack(0):
        return dict(assignment)
    return None


class TournamentSimulator:
    def __init__(self, ratings, model, fixtures, n_sims, seed, sigma=None):
        self.teams = all_teams()
        self.idx = {t: i for i, t in enumerate(self.teams)}
        self.nT = len(self.teams)
        self.elo = np.array([ratings.get(t, 1500.0) for t in self.teams])
        self.host = np.array([1.0 if t in HOSTS else 0.0 for t in self.teams])
        self.a = model.a
        self.b = model.b
        self.N = n_sims
        self.rng = np.random.default_rng(seed)
        self.rows = np.arange(n_sims)
        self.fixtures = fixtures  # lista de dicts con grp, home, away, ha_points

        sig = ELO_SIM_SIGMA if sigma is None else sigma
        # Nivel "real" de cada selección en cada simulación: Elo + ruido
        # gaussiano (incertidumbre de forma/lesiones/sorteo).
        self.elo_sim = (self.elo[None, :]
                        + self.rng.normal(0.0, sig, size=(n_sims, self.nT)))

        # cuenta de resultados
        self.cnt = {k: np.zeros(self.nT) for k in
                    ("win_group", "runner", "third_q", "r32", "r16",
                     "qf", "sf", "final", "champion")}
        self._assign_cache = {}

    # ---- muestreo de goles ----
    def _lambdas(self, dr):
        return np.exp(self.a + self.b * dr), np.exp(self.a - self.b * dr)

    def _play_vec(self, idh, ida, host_neutral=True):
        """Juega N partidos (eliminatoria, sede neutral). Devuelve ganador/perdedor."""
        eh = self.elo_sim[self.rows, idh]
        ea = self.elo_sim[self.rows, ida]
        dr = eh - ea
        if host_neutral:
            dr = dr + HOST_KO_EXTRA * (self.host[idh] - self.host[ida])
        lam, mu = self._lambdas(dr)
        gh = self.rng.poisson(lam)
        ga = self.rng.poisson(mu)
        home_win = gh > ga
        away_win = ga > gh
        tie = ~(home_win | away_win)
        # desempate por moneda ponderada por Elo (prórroga + penaltis)
        p_home = 1.0 / (1.0 + 10 ** (-dr / 400.0))
        coin = self.rng.random(len(idh)) < p_home
        home_adv = home_win | (tie & coin)
        winner = np.where(home_adv, idh, ida)
        loser = np.where(home_adv, ida, idh)
        return winner, loser

    # ---- fase de grupos ----
    def _simulate_groups(self):
        N = self.N
        winners, runners = {}, {}
        third_team = {}    # letra -> array global id del 3.º
        third_key = {}     # letra -> array clave de ranking del 3.º

        fx_by_group = defaultdict(list)
        for fx in self.fixtures:
            fx_by_group[fx["grp"]].append(fx)

        for g in GROUP_LETTERS:
            members = GROUPS[g]
            gid = np.array([self.idx[m] for m in members])
            local = {m: i for i, m in enumerate(members)}
            pts = np.zeros((N, 4))
            gf = np.zeros((N, 4))
            ga = np.zeros((N, 4))

            for fx in fx_by_group[g]:
                i = local[fx["home"]]
                j = local[fx["away"]]
                if fx.get("played"):
                    # Resultado real: hecho consumado, no se muestrea.
                    hg = np.full(N, int(fx["home_score"]))
                    ag = np.full(N, int(fx["away_score"]))
                else:
                    eh = self.elo_sim[:, gid[i]]
                    ea = self.elo_sim[:, gid[j]]
                    dr = eh - ea + fx["ha_points"]
                    lam, mu = self._lambdas(dr)
                    hg = self.rng.poisson(lam)
                    ag = self.rng.poisson(mu)
                hw = hg > ag
                aw = ag > hg
                dr_tie = hg == ag
                pts[:, i] += hw * 3 + dr_tie * 1
                pts[:, j] += aw * 3 + dr_tie * 1
                gf[:, i] += hg; ga[:, i] += ag
                gf[:, j] += ag; ga[:, j] += hg

            gd = gf - ga
            noise = self.rng.random((N, 4)) * 1e-3
            key = pts * 1e6 + (gd + 200) * 1e3 + gf + noise
            order = np.argsort(-key, axis=1)  # columnas locales ordenadas
            w_local = order[:, 0]
            r_local = order[:, 1]
            t_local = order[:, 2]
            rows = np.arange(N)
            winners[g] = gid[w_local]
            runners[g] = gid[r_local]
            third_team[g] = gid[t_local]
            # clave del tercero para el ranking entre grupos
            tp = pts[rows, t_local]
            tgd = gd[rows, t_local]
            tgf = gf[rows, t_local]
            third_key[g] = tp * 1e6 + (tgd + 200) * 1e3 + tgf + self.rng.random(N) * 1e-3

            self.cnt["win_group"] += np.bincount(gid[w_local], minlength=self.nT)
            self.cnt["runner"] += np.bincount(gid[r_local], minlength=self.nT)

        return winners, runners, third_team, third_key

    # ---- selección de los 8 mejores terceros ----
    def _rank_thirds(self, third_team, third_key):
        N = self.N
        keys = np.stack([third_key[g] for g in GROUP_LETTERS], axis=1)  # (N,12)
        order = np.argsort(-keys, axis=1)
        top8_cols = order[:, :8]   # índices de grupo (0..11) clasificados
        # marcar terceros clasificados
        for k in range(8):
            cols = top8_cols[:, k]
            for gi, g in enumerate(GROUP_LETTERS):
                mask = cols == gi
                if mask.any():
                    ids = third_team[g][mask]
                    self.cnt["third_q"] += np.bincount(ids, minlength=self.nT)
        return top8_cols

    def _assign_thirds_to_slots(self, top8_cols, third_team):
        """Devuelve {match_no: array(N) global id del tercero asignado}."""
        N = self.N
        slot_team = {m: np.full(N, -1) for m in THIRD_SLOT_MATCHES}
        eligible = {m: set(THIRD_PLACE_SLOTS[m]) for m in THIRD_SLOT_MATCHES}

        # agrupar simulaciones por combinación de grupos clasificados
        letters_arr = np.array(GROUP_LETTERS)
        combos = defaultdict(list)
        for s in range(N):
            qual = tuple(sorted(letters_arr[top8_cols[s]]))
            combos[qual].append(s)

        for qual, sims in combos.items():
            key = qual
            if key not in self._assign_cache:
                self._assign_cache[key] = _bipartite_match(
                    THIRD_SLOT_MATCHES, eligible, set(qual))
            assign = self._assign_cache[key]
            sims = np.array(sims)
            if assign is None:
                # respaldo (no debería ocurrir): orden directo
                assign = dict(zip(THIRD_SLOT_MATCHES, qual))
            for m, g in assign.items():
                slot_team[m][sims] = third_team[g][sims]
        return slot_team

    # ---- eliminatorias ----
    def _resolve_slot(self, slot, winners, runners, slot_team):
        kind, val = slot
        if kind == "W":
            return winners[val]
        if kind == "R":
            return runners[val]
        # kind == "3": val es el frozenset; usamos el match_no del slot
        raise RuntimeError("slot de tercero debe resolverse por match_no")

    def _simulate_knockout(self, winners, runners, slot_team):
        # Dieciseisavos
        r32_winner = {}
        appeared_r32 = np.zeros(self.nT)
        for m, (sa, sb) in R32.items():
            ta = slot_team[m] if sa[0] == "3" else self._resolve_slot(sa, winners, runners, slot_team)
            tb = slot_team[m] if sb[0] == "3" else self._resolve_slot(sb, winners, runners, slot_team)
            appeared_r32 += np.bincount(ta, minlength=self.nT)
            appeared_r32 += np.bincount(tb, minlength=self.nT)
            w, _ = self._play_vec(ta, tb)
            r32_winner[m] = w
        self.cnt["r32"] += appeared_r32

        def play_bracket(bracket, src):
            res = {}
            for m, (x, y) in bracket.items():
                w, l = self._play_vec(src[x], src[y])
                res[m] = (w, l)
            return res

        # ganadores de R32 -> Octavos
        r16 = {}
        for m, (x, y) in R16.items():
            w, _ = self._play_vec(r32_winner[x], r32_winner[y])
            r16[m] = w
            self.cnt["r16"] += np.bincount(r32_winner[x], minlength=self.nT)
            self.cnt["r16"] += np.bincount(r32_winner[y], minlength=self.nT)

        qf = {}
        for m, (x, y) in QF.items():
            self.cnt["qf"] += np.bincount(r16[x], minlength=self.nT)
            self.cnt["qf"] += np.bincount(r16[y], minlength=self.nT)
            w, _ = self._play_vec(r16[x], r16[y])
            qf[m] = w

        sf = {}
        sf_losers = {}
        for m, (x, y) in SF.items():
            self.cnt["sf"] += np.bincount(qf[x], minlength=self.nT)
            self.cnt["sf"] += np.bincount(qf[y], minlength=self.nT)
            w, l = self._play_vec(qf[x], qf[y])
            sf[m] = w
            sf_losers[m] = l

        a, b = list(SF.keys())
        self.cnt["final"] += np.bincount(sf[a], minlength=self.nT)
        self.cnt["final"] += np.bincount(sf[b], minlength=self.nT)
        champ, _ = self._play_vec(sf[a], sf[b])
        self.cnt["champion"] += np.bincount(champ, minlength=self.nT)

    # ---- orquestación ----
    def run(self):
        winners, runners, third_team, third_key = self._simulate_groups()
        top8 = self._rank_thirds(third_team, third_key)
        slot_team = self._assign_thirds_to_slots(top8, third_team)
        self._simulate_knockout(winners, runners, slot_team)
        return self.results()

    def results(self):
        import pandas as pd
        N = self.N
        rows = []
        for t in self.teams:
            i = self.idx[t]
            rows.append({
                "team": t,
                "win_group": self.cnt["win_group"][i] / N,
                "runner_up": self.cnt["runner"][i] / N,
                "qualify_3rd": self.cnt["third_q"][i] / N,
                "advance": self.cnt["r32"][i] / N,           # llega a Dieciseisavos
                "reach_R16": self.cnt["r16"][i] / N,
                "reach_QF": self.cnt["qf"][i] / N,
                "reach_SF": self.cnt["sf"][i] / N,
                "reach_final": self.cnt["final"][i] / N,
                "champion": self.cnt["champion"][i] / N,
            })
        df = pd.DataFrame(rows).sort_values("champion", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", df.index + 1)
        return df
