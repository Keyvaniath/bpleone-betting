"""
EdgeStat - Team rating system (Elo + Glicko-2).

Two iterative team-strength systems:

  • Elo: simple, fast, robust. Standard 1500 baseline, K=6 for MLB.
  • Glicko-2: tracks uncertainty (RD) AND volatility. More information-dense,
    pricier per update. We use Glicko-2 for the headline rating and Elo for
    bootstrapped lower-bound rating.

Both are trained season-by-season over a synthetic 5-year game log. In
production, swap in real game results from the MLB Stats API.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# --------------------------- Elo ---------------------------

ELO_K = 6.0
ELO_HFA = 24.0   # home-field advantage in rating points


@dataclass
class EloRating:
    rating: float = 1500.0
    games: int = 0


def elo_expected(r_a: float, r_b: float) -> float:
    """Expected probability A beats B given their ratings."""
    return 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))


def elo_update_pair(ratings: Dict[str, EloRating],
                    home: str, away: str,
                    home_score: int, away_score: int,
                    k: float = ELO_K, hfa: float = ELO_HFA) -> None:
    """Update both teams' ratings after a single game."""
    rh = ratings[home].rating + hfa
    ra = ratings[away].rating
    expected_h = elo_expected(rh, ra)
    actual_h = 1.0 if home_score > away_score else 0.0
    # Margin-of-victory bump (modest, anti-overreaction).
    mov = abs(home_score - away_score)
    mov_mult = math.log(max(mov, 1) + 1) * 1.0
    delta = k * mov_mult * (actual_h - expected_h)
    ratings[home].rating += delta
    ratings[away].rating -= delta
    ratings[home].games += 1
    ratings[away].games += 1


def elo_run(games: List[Tuple[str, str, int, int]], teams: List[str],
            initial: float = 1500.0) -> Dict[str, EloRating]:
    """Replay a list of (home, away, hs, as) games through Elo and return final."""
    ratings = {t: EloRating(rating=initial) for t in teams}
    for home, away, hs, as_ in games:
        if home not in ratings: ratings[home] = EloRating()
        if away not in ratings: ratings[away] = EloRating()
        elo_update_pair(ratings, home, away, hs, as_)
    return ratings


# --------------------------- Glicko-2 ---------------------------
#
# Reference: Mark Glickman's "The Glicko System" + Glicko-2.
# Glicko-2 tracks rating, rating deviation (RD), and volatility (sigma).
# All three update after each rating period (we use weekly = ~6 games).

GLICKO_TAU = 0.5            # constrains volatility change
GLICKO_INIT_RATING = 1500.0
GLICKO_INIT_RD = 200.0
GLICKO_INIT_VOL = 0.06


@dataclass
class GlickoRating:
    rating: float = GLICKO_INIT_RATING
    rd: float = GLICKO_INIT_RD
    volatility: float = GLICKO_INIT_VOL

    def to_glicko2(self) -> Tuple[float, float]:
        """Convert from Glicko (1500/200) to Glicko-2 (0/1) units."""
        return ((self.rating - 1500.0) / 173.7178, self.rd / 173.7178)

    def from_glicko2(self, mu: float, phi: float) -> None:
        self.rating = 173.7178 * mu + 1500.0
        self.rd = 173.7178 * phi


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi ** 2 / math.pi ** 2)


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def glicko_update(self_: GlickoRating, opponents: List[Tuple[GlickoRating, float]],
                  tau: float = GLICKO_TAU) -> GlickoRating:
    """Update a single player's rating given list of (opp, score) outcomes for a period."""
    mu, phi = self_.to_glicko2()
    sigma = self_.volatility

    if not opponents:
        # No games: just inflate RD with volatility.
        phi_star = math.sqrt(phi ** 2 + sigma ** 2)
        out = GlickoRating()
        out.from_glicko2(mu, phi_star)
        out.volatility = sigma
        return out

    # Quantities v, delta
    v_inv = 0.0
    delta_sum = 0.0
    for opp, score in opponents:
        mu_j, phi_j = opp.to_glicko2()
        gp = _g(phi_j)
        ej = _E(mu, mu_j, phi_j)
        v_inv += gp ** 2 * ej * (1 - ej)
        delta_sum += gp * (score - ej)
    v = 1.0 / v_inv
    delta = v * delta_sum

    # Volatility update: Illinois algorithm for f(x) = 0.
    a = math.log(sigma ** 2)
    def f(x: float) -> float:
        ex = math.exp(x)
        return (ex * (delta ** 2 - phi ** 2 - v - ex)) / (2 * (phi ** 2 + v + ex) ** 2) \
               - (x - a) / (tau ** 2)
    A = a
    if delta ** 2 > phi ** 2 + v:
        B = math.log(delta ** 2 - phi ** 2 - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        B = a - k * tau
    fA, fB = f(A), f(B)
    for _ in range(100):
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB < 0:
            A, fA = B, fB
        else:
            fA = fA / 2
        B, fB = C, fC
        if abs(B - A) < 1e-6:
            break
    new_sigma = math.exp(A / 2)

    phi_star = math.sqrt(phi ** 2 + new_sigma ** 2)
    phi_new = 1.0 / math.sqrt(1.0 / phi_star ** 2 + 1.0 / v)
    mu_new = mu + phi_new ** 2 * delta_sum

    out = GlickoRating()
    out.from_glicko2(mu_new, phi_new)
    out.volatility = new_sigma
    return out


def glicko_win_prob(a: GlickoRating, b: GlickoRating, hfa: float = 24.0) -> float:
    """Probability A beats B (A is home if hfa > 0)."""
    mu_a, phi_a = a.to_glicko2()
    mu_b, phi_b = b.to_glicko2()
    # Apply HFA in Glicko units.
    mu_a = mu_a + hfa / 173.7178
    g = _g(math.sqrt(phi_a ** 2 + phi_b ** 2))
    return 1.0 / (1.0 + math.exp(-g * (mu_a - mu_b)))


# --------------------------- Synthetic season generator ---------------------------

def generate_synthetic_season(teams: List[str], seed: int = 7,
                              games_per_team: int = 162,
                              true_skills: Dict[str, float] = None
                              ) -> List[Tuple[str, str, int, int]]:
    """Generate a season of games from latent true skills.

    Output schedule respects games_per_team. Each game's result is from a
    Poisson model with the home team enjoying ~3% boost.
    """
    rng = random.Random(seed)
    if true_skills is None:
        true_skills = {t: rng.gauss(4.5, 0.5) for t in teams}
    games = []
    schedule = []
    # Round-robin schedule, repeated to fill games_per_team.
    while len(schedule) < games_per_team * len(teams) // 2:
        for i, h in enumerate(teams):
            for j, a in enumerate(teams):
                if i == j: continue
                schedule.append((h, a))
    rng.shuffle(schedule)
    schedule = schedule[: games_per_team * len(teams) // 2]
    for h, a in schedule:
        lam_h = true_skills[h] * 1.025
        lam_a = true_skills[a]
        hs = _poisson_sample(lam_h, rng)
        as_ = _poisson_sample(lam_a, rng)
        # No ties — extras until someone wins.
        while hs == as_:
            hs += _poisson_sample(0.5, rng)
            as_ += _poisson_sample(0.5, rng)
        games.append((h, a, hs, as_))
    return games


def _poisson_sample(lam: float, rng: random.Random) -> int:
    """Knuth's algorithm for sampling from Poisson."""
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


# --------------------------- Demo ---------------------------

TEAMS = ["LAD", "NYY", "ATL", "PHI", "HOU", "BOS", "SDP", "NYM", "CHC", "WSH",
         "TOR", "TBR", "SFG", "STL", "ARI", "CIN", "COL", "TEX", "DET", "MIL"]


def fit_full_season() -> Dict[str, EloRating]:
    games = generate_synthetic_season(TEAMS, seed=11, games_per_team=162)
    ratings = elo_run(games, TEAMS)
    return ratings


def fit_glicko_season(games: List[Tuple[str, str, int, int]],
                      teams: List[str],
                      period_games: int = 6) -> Dict[str, GlickoRating]:
    """Apply Glicko-2 to a season, treating every `period_games` per team as a period."""
    ratings = {t: GlickoRating() for t in teams}
    # Split games into rolling periods.
    period = []
    period_outcomes: Dict[str, List[Tuple[GlickoRating, float]]] = {t: [] for t in teams}
    for h, a, hs, as_ in games:
        period.append((h, a, hs, as_))
        period_outcomes[h].append((ratings[a], 1.0 if hs > as_ else 0.0))
        period_outcomes[a].append((ratings[h], 1.0 if as_ > hs else 0.0))
        # Flush periodically.
        if len(period) >= period_games * len(teams) // 2:
            new = {}
            for t in teams:
                new[t] = glicko_update(ratings[t], period_outcomes[t])
            ratings = new
            period_outcomes = {t: [] for t in teams}
            period = []
    # Final partial flush.
    if any(period_outcomes.values()):
        new = {}
        for t in teams:
            new[t] = glicko_update(ratings[t], period_outcomes[t])
        ratings = new
    return ratings


def write_artifact(path: str, ratings: Dict[str, EloRating], glicko: Dict[str, GlickoRating]) -> None:
    import json
    out = []
    for t in sorted(ratings, key=lambda x: -ratings[x].rating):
        out.append({
            "team": t,
            "elo": round(ratings[t].rating, 1),
            "elo_games": ratings[t].games,
            "glicko": round(glicko[t].rating, 1),
            "rd": round(glicko[t].rd, 1),
            "vol": round(glicko[t].volatility, 4),
        })
    with open(path, "w") as f:
        json.dump({"ratings": out}, f, indent=2)
    print(f"Wrote {path} ({len(out)} teams)")


if __name__ == "__main__":
    games = generate_synthetic_season(TEAMS, seed=42, games_per_team=162)
    elo = elo_run(games, TEAMS)
    glk = fit_glicko_season(games, TEAMS, period_games=6)
    print("=== Final Elo + Glicko Rankings ===")
    print(f"{'Team':<6}{'Elo':>9}{'Glicko':>10}{'RD':>8}{'Vol':>8}")
    for t in sorted(elo, key=lambda x: -elo[x].rating):
        print(f"{t:<6}{elo[t].rating:>9.1f}{glk[t].rating:>10.1f}"
              f"{glk[t].rd:>8.1f}{glk[t].volatility:>8.4f}")
    # Example head-to-head.
    p = glicko_win_prob(glk["LAD"], glk["SDP"])
    print(f"\nP(LAD home beats SDP) = {p:.3f}")
    write_artifact("../data/ratings.json", elo, glk)
