"""
EdgeStat - probability & betting math primitives.

These are pure Python (no numpy required for the basics) implementations of the
math we lean on for every play recommendation. Plug them into the rest of the
pipeline (mlb_model.py, kelly.py, etc.).
"""
from __future__ import annotations

import math
from typing import Tuple, Iterable


# --------------------------- Odds conversions ---------------------------

def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.
    +150 -> 2.50, -150 -> 1.667
    """
    if odds == 0:
        return 1.0
    return 1.0 + odds / 100.0 if odds > 0 else 1.0 + 100.0 / abs(odds)


def decimal_to_american(dec: float) -> int:
    """Convert decimal odds to American odds."""
    if dec <= 1.0:
        return 0
    if dec >= 2.0:
        return int(round((dec - 1) * 100))
    return -int(round(100 / (dec - 1)))


def american_to_implied(odds: int) -> float:
    """Return naive implied probability from American odds (does NOT remove vig)."""
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def prob_to_american(p: float) -> int:
    """Fair American price for given probability."""
    if p <= 0 or p >= 1:
        return 0
    return decimal_to_american(1 / p)


def remove_vig(p_side_a: float, p_side_b: float) -> Tuple[float, float]:
    """Normalize two implied probabilities to sum to 1."""
    total = p_side_a + p_side_b
    return p_side_a / total, p_side_b / total


# --------------------------- EV & edge ---------------------------

def expected_value(model_prob: float, american_odds: int) -> float:
    """EV per $1 staked."""
    dec = american_to_decimal(american_odds)
    return model_prob * (dec - 1) - (1 - model_prob)


def edge_pct(model_prob: float, american_odds: int) -> float:
    """Edge as a percentage of stake."""
    return expected_value(model_prob, american_odds) * 100.0


# --------------------------- Kelly Criterion ---------------------------

def kelly_fraction(model_prob: float, american_odds: int) -> float:
    """Full Kelly fraction (can be negative, indicating no bet).
    f* = (bp - q) / b   where b = decimal_odds - 1, p = win prob, q = 1 - p
    """
    b = american_to_decimal(american_odds) - 1
    if b <= 0:
        return 0.0
    p = model_prob
    q = 1 - p
    return (b * p - q) / b


def kelly_stake_units(model_prob: float, american_odds: int,
                      fraction: float = 0.25, cap_units: float = 5.0) -> float:
    """Return recommended stake in units (1u = 1% of bankroll).

    Default is quarter-Kelly with a 5u cap.  Fractional Kelly is industry
    standard for sharps: it sacrifices a tiny bit of long-run growth for a
    massive reduction in variance.
    """
    f = kelly_fraction(model_prob, american_odds)
    if f <= 0:
        return 0.0
    return min(f * fraction * 100.0, cap_units)


# --------------------------- Poisson run model ---------------------------

def poisson(k: int, lam: float) -> float:
    """P(X = k | lambda) for a Poisson distribution."""
    return math.exp(-lam) * lam ** k / math.factorial(k)


def total_over_prob(away_lambda: float, home_lambda: float,
                    line: float, max_runs: int = 22) -> float:
    """Probability total runs > line, summing joint Poisson distribution."""
    p_over = 0.0
    p_push = 0.0
    for a in range(max_runs):
        pa = poisson(a, away_lambda)
        for h in range(max_runs):
            ph = poisson(h, home_lambda)
            total = a + h
            p = pa * ph
            if total > line:
                p_over += p
            elif total == line:
                p_push += p
    # Half-point lines: no push.  Whole-number lines: split push.
    return p_over + 0.5 * p_push


def home_win_prob(away_lambda: float, home_lambda: float, max_runs: int = 22) -> float:
    """Probability home wins (treating ties as 50/50 — close to extras reality)."""
    p_home = 0.0
    p_tie = 0.0
    for a in range(max_runs):
        pa = poisson(a, away_lambda)
        for h in range(max_runs):
            p = pa * poisson(h, home_lambda)
            if h > a:
                p_home += p
            elif h == a:
                p_tie += p
    return p_home + 0.5 * p_tie


# --------------------------- Bayesian shrinkage ---------------------------

def bayesian_talent(prior: float, sample: float, n: int, kappa: float = 50.0) -> float:
    """Shrink an observed sample toward a prior using a strength-of-prior kappa.

    posterior = prior + (sample - prior) * (n / (n + kappa))

    kappa = 50 is roughly "trust the sample after ~50 games" — good for
    half-season MLB priors.
    """
    return prior + (sample - prior) * (n / (n + kappa))


# --------------------------- Pythagorean & ELO ---------------------------

def pythag_win_pct(runs_for: float, runs_against: float, games: int = 162) -> float:
    """Bill James pythagorean win percentage, Pythagenpat exponent."""
    if runs_for + runs_against == 0:
        return 0.5
    rpg = (runs_for + runs_against) / games
    x = rpg ** 0.287
    return runs_for ** x / (runs_for ** x + runs_against ** x)


def elo_update(rating_a: float, rating_b: float, score_a: float,
               k: float = 6.0) -> float:
    """Update ELO rating for team A after observing actual score_a (1 win, 0 loss).
    Default K=6 is the rating mass-balance for MLB.
    """
    expected_a = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))
    return rating_a + k * (score_a - expected_a)


# --------------------------- Confidence buckets ---------------------------

def confidence_label(edge_percent: float) -> str:
    """Human-readable confidence bucket for a given edge."""
    if edge_percent >= 5.0:
        return "High"
    if edge_percent >= 3.0:
        return "Medium"
    if edge_percent >= 1.5:
        return "Low"
    return "Pass"


# --------------------------- Helpful aggregators ---------------------------

def closing_line_value(my_price: int, closing_price: int) -> float:
    """CLV in percentage points of implied probability."""
    return (american_to_implied(closing_price) - american_to_implied(my_price)) * 100.0


def vig_pct(odds_side_a: int, odds_side_b: int) -> float:
    """Two-way market vig (juice) in percentage points."""
    return (american_to_implied(odds_side_a) + american_to_implied(odds_side_b) - 1) * 100.0


if __name__ == "__main__":
    # Quick smoke test reproducing the dashboard's Play of the Day calculation.
    p = 0.640
    price = -148
    print(f"Model win prob: {p:.3f}")
    print(f"Market price : {price}")
    print(f"Implied prob : {american_to_implied(price):.3f}")
    print(f"Fair price   : {prob_to_american(p)}")
    print(f"EV per $1    : {expected_value(p, price):+.4f}")
    print(f"Edge %       : {edge_pct(p, price):+.2f}")
    print(f"¼-Kelly units: {kelly_stake_units(p, price):.2f}u")
    print(f"Confidence   : {confidence_label(edge_pct(p, price))}")
