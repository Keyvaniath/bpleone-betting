"""
EdgeStat - Correlation / Same-Game-Parlay pricer.

Books advertise SGP markets at "fun" prices that look attractive but hide a
heavy juice multiplier on top of the natural vig.  This module exposes how:

  • Independent parlay price = product of leg probabilities × payout multiplier
  • Correlated parlay price = joint probability (NOT the product of marginals)
  • Book's SGP price = often noticeably worse than the fair correlated price

We use a Gaussian copula to capture leg correlations.  Inputs are each leg's
marginal probability + a pairwise correlation matrix.

Result: a "Bookie's edge on your SGP" calculator that almost always shows you
the SGP is a bad bet.
"""
from __future__ import annotations

import math
import random
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Tuple


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1.0 + am / 100.0 if am > 0 else 1.0 + 100.0 / abs(am)


def decimal_to_american(d: float) -> int:
    if d <= 1.0: return 0
    return int(round((d - 1) * 100)) if d >= 2 else -int(round(100 / (d - 1)))


def prob_to_american(p: float) -> int:
    if p <= 0 or p >= 1: return 0
    return decimal_to_american(1 / p)


# --------------------------- Independent parlay ---------------------------

def parlay_fair_decimal(leg_probs: List[float]) -> float:
    """Fair decimal odds for an INDEPENDENT-legged parlay."""
    if not leg_probs: return 1.0
    p_all = 1.0
    for p in leg_probs:
        p_all *= p
    return 1 / p_all


def parlay_fair_price(leg_probs: List[float]) -> int:
    return decimal_to_american(parlay_fair_decimal(leg_probs))


# --------------------------- Gaussian copula (correlated legs) ---------------------------

def _norm_inv(p: float) -> float:
    """Approximate inverse normal CDF (Beasley-Springer-Moro)."""
    a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2,
         1.383577518672690e2, -3.066479806614716e1, 2.506628277459239e0]
    b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2,
         6.680131188771972e1, -1.328068155288572e1]
    c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838e0,
         -2.549732539343734e0, 4.374664141464968e0, 2.938163982698783e0]
    d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996e0,
         3.754408661907416e0]
    p_low = 0.02425
    p_high = 1 - p_low
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > p_high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    num = (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q
    den = ((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1
    return num / den


def _cholesky(matrix: List[List[float]]) -> List[List[float]]:
    n = len(matrix)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                v = matrix[i][i] - s
                L[i][j] = math.sqrt(max(v, 1e-9))
            else:
                L[i][j] = (matrix[i][j] - s) / L[j][j]
    return L


def correlated_parlay_prob(leg_probs: List[float],
                           correlation: List[List[float]],
                           n_sims: int = 20000, seed: int = 17) -> float:
    """Joint probability all legs hit, under Gaussian copula correlation."""
    rng = random.Random(seed)
    n = len(leg_probs)
    if n != len(correlation):
        raise ValueError("correlation matrix size mismatch")
    thresholds = [_norm_inv(p) for p in leg_probs]
    L = _cholesky(correlation)
    hits = 0
    for _ in range(n_sims):
        # Draw n iid standard normals.
        z = [rng.gauss(0, 1) for _ in range(n)]
        # Correlate them: x = L @ z
        x = [sum(L[i][j] * z[j] for j in range(n)) for i in range(n)]
        # Leg i hits if x[i] >= -thresholds[i] (rough copula trick: we want
        # P(leg) = phi(threshold_i), with our threshold = inv_phi(p_leg)).
        all_hit = True
        for i in range(n):
            if x[i] > thresholds[i]:   # x > threshold = leg misses (p=1-p_leg above threshold)
                all_hit = False
                break
        if all_hit:
            hits += 1
    return hits / n_sims


def sgp_analysis(leg_probs: List[float],
                 book_price_american: int,
                 correlation: List[List[float]]) -> Dict:
    """Compare book's SGP price to fair independent and fair correlated prices."""
    indep_dec = parlay_fair_decimal(leg_probs)
    book_dec = american_to_decimal(book_price_american)
    cor_p = correlated_parlay_prob(leg_probs, correlation, n_sims=15000)
    cor_dec = 1 / max(cor_p, 1e-6)
    book_p = 1 / book_dec
    # Edge a bettor has, assuming the correlated prob is correct.
    ev = cor_p * (book_dec - 1) - (1 - cor_p)
    return {
        "leg_probs": leg_probs,
        "book_price": book_price_american,
        "book_decimal": round(book_dec, 3),
        "book_implied_pct": round(book_p * 100, 2),
        "independent_fair_decimal": round(indep_dec, 3),
        "independent_fair_price": parlay_fair_price(leg_probs),
        "correlated_fair_decimal": round(cor_dec, 3),
        "correlated_fair_price": prob_to_american(cor_p),
        "correlated_prob_pct": round(cor_p * 100, 2),
        "edge_vs_book_pct": round(ev * 100, 2),
        "book_hold_pct": round((book_dec / cor_dec - 1) * 100, 2)
                          if cor_dec > 0 else 0,
    }


# --------------------------- Demo ---------------------------

if __name__ == "__main__":
    # Example: 3-leg SGP on Yankees game:
    #   Leg 1: NYY moneyline                       (p=0.59)
    #   Leg 2: Aaron Judge HR                       (p=0.27)
    #   Leg 3: NYY over 4.5 runs                    (p=0.53)
    # All three are POSITIVELY correlated (Yankees winning means more runs and
    # more chances for Judge to HR).
    legs = [0.59, 0.27, 0.53]
    corr = [
        [1.00, 0.30, 0.55],
        [0.30, 1.00, 0.35],
        [0.55, 0.35, 1.00],
    ]
    # Book's typical SGP price for these legs: ~+500.
    out = sgp_analysis(legs, +500, corr)
    print("=== SGP Pricing Example ===")
    for k, v in out.items():
        print(f"  {k:>30}: {v}")
    payload = {"example_yankees_sgp": out}

    # Another: NEGATIVELY correlated SGP (Both teams to score 8+ runs).
    legs2 = [0.45, 0.40]   # OVER each team total
    corr2 = [[1.0, -0.15], [-0.15, 1.0]]
    out2 = sgp_analysis(legs2, +220, corr2)
    print("\n=== SGP Pricing Example 2 (both teams to score) ===")
    for k, v in out2.items():
        print(f"  {k:>30}: {v}")
    payload["example_both_teams_score"] = out2

    os.makedirs("../data", exist_ok=True)
    with open("../data/correlations.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("\nWrote ../data/correlations.json")
ations.json")
