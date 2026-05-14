"""
EdgeStat - Portfolio bet optimizer.

Sharp bettors don't pick one play per slate.  They pick a *portfolio* of
plays and stake each one to balance expected return against variance and
correlation.  This is classic Markowitz portfolio theory, applied to bets.

Each bet has:
  - Expected return (EV per $1)
  - Variance (binary win/loss has known variance = p*(1-p)*odds^2)
  - Correlation with other bets (e.g. LAD ML and LAD -1.5 are very correlated)

The optimizer maximizes:
   E[portfolio return]  -  lambda * Var(portfolio)

subject to:
   sum of stakes <= bankroll_pct
   each stake >= 0
   each stake <= Kelly cap

We use a simple coordinate descent (no scipy dependency) so it runs in pure
Python on any box.
"""
from __future__ import annotations

import math
import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional


@dataclass
class Bet:
    label: str
    p_win: float
    american_price: int
    correlation_group: Optional[str] = None  # bets in same group have implicit correlation

    @property
    def decimal_odds(self) -> float:
        am = self.american_price
        return 1 + am / 100 if am > 0 else 1 + 100 / abs(am)

    @property
    def ev_per_dollar(self) -> float:
        return self.p_win * (self.decimal_odds - 1) - (1 - self.p_win)

    @property
    def variance_per_dollar(self) -> float:
        d = self.decimal_odds
        return self.p_win * (d - 1) ** 2 + (1 - self.p_win) * 1
              # binary outcome variance for $1 stake

    @property
    def kelly_fraction(self) -> float:
        b = self.decimal_odds - 1
        if b <= 0: return 0
        f = (b * self.p_win - (1 - self.p_win)) / b
        return max(0, f)


# --------------------------- Correlation matrix ---------------------------

def build_correlation_matrix(bets: List[Bet],
                             same_game_corr: float = 0.45,
                             same_team_corr: float = 0.18) -> List[List[float]]:
    """Heuristic correlation matrix.  In production this comes from
    simulator output; here we use group labels."""
    n = len(bets)
    M = [[0.0] * n for _ in range(n)]
    for i in range(n):
        M[i][i] = 1.0
        for j in range(i + 1, n):
            if bets[i].correlation_group and bets[i].correlation_group == bets[j].correlation_group:
                M[i][j] = M[j][i] = same_game_corr
            elif bets[i].correlation_group and bets[j].correlation_group:
                # Sub-string match for same-team correlation (e.g. "LAD_ML" and "LAD_TB")
                a = bets[i].correlation_group.split("_")[0]
                b = bets[j].correlation_group.split("_")[0]
                if a == b:
                    M[i][j] = M[j][i] = same_team_corr
    return M


# --------------------------- Portfolio metrics ---------------------------

def portfolio_metrics(stakes: List[float], bets: List[Bet],
                      corr: List[List[float]]) -> Dict[str, float]:
    """Compute expected return and variance of a stake vector."""
    n = len(bets)
    ev = sum(stakes[i] * bets[i].ev_per_dollar for i in range(n))
    # Variance: sum_i sum_j s_i s_j sigma_i sigma_j rho_ij
    sigmas = [math.sqrt(b.variance_per_dollar) for b in bets]
    var = 0.0
    for i in range(n):
        for j in range(n):
            var += stakes[i] * stakes[j] * sigmas[i] * sigmas[j] * corr[i][j]
    return {"expected_return": round(ev, 4),
            "variance":        round(var, 4),
            "std":             round(math.sqrt(max(0, var)), 4),
            "sharpe":          round(ev / max(math.sqrt(max(0, var)), 1e-6), 4)}


# --------------------------- Coordinate-descent optimizer ---------------------------

def optimize_portfolio(bets: List[Bet],
                       bankroll_pct: float = 0.10,
                       lambda_risk: float = 0.5,
                       n_iter: int = 200,
                       step: float = 0.001) -> Tuple[List[float], Dict]:
    """Maximize EV - lambda * Variance via coordinate-descent gradient ascent.

    bankroll_pct = max total fraction of bankroll across all bets (e.g. 0.10 = 10%)
    lambda_risk  = risk aversion (higher = more conservative)
    """
    n = len(bets)
    corr = build_correlation_matrix(bets)
    sigmas = [math.sqrt(b.variance_per_dollar) for b in bets]
    # Initialize at Kelly stakes scaled by 0.25.
    stakes = [b.kelly_fraction * 0.25 for b in bets]
    # Clamp to bankroll.
    s_tot = sum(stakes)
    if s_tot > bankroll_pct:
        stakes = [s * bankroll_pct / s_tot for s in stakes]
    # Cap each individual at 0.03 (3% of bankroll).
    stakes = [min(s, 0.03) for s in stakes]

    for _ in range(n_iter):
        # Compute gradient for each stake.
        grads = []
        for i in range(n):
            # dEV/ds_i = ev_per_$
            dev = bets[i].ev_per_dollar
            # dVar/ds_i = 2 * sigma_i * sum_j(s_j * sigma_j * rho_ij)
            dvar = 2 * sigmas[i] * sum(stakes[j] * sigmas[j] * corr[i][j] for j in range(n))
            g = dev - lambda_risk * dvar
            grads.append(g)
        # Apply step.
        new_stakes = []
        for i in range(n):
            v = stakes[i] + step * grads[i]
            v = max(0.0, min(0.03, v))
            new_stakes.append(v)
        # Re-normalize if total too high.
        tot = sum(new_stakes)
        if tot > bankroll_pct:
            new_stakes = [s * bankroll_pct / tot for s in new_stakes]
        # Check convergence.
        delta = sum(abs(new_stakes[i] - stakes[i]) for i in range(n))
        stakes = new_stakes
        if delta < 1e-7:
            break
    metrics = portfolio_metrics(stakes, bets, corr)
    return stakes, metrics


# --------------------------- Demo ---------------------------

DEMO_BETS = [
    Bet("LAD ML",                p_win=0.640, american_price=-148, correlation_group="LAD_GAME"),
    Bet("LAD -1.5",              p_win=0.485, american_price=+118, correlation_group="LAD_GAME"),
    Bet("LAD/SDP UNDER 8.0",     p_win=0.555, american_price=-110, correlation_group="LAD_GAME"),
    Bet("Yamamoto O6.5 K",       p_win=0.580, american_price=-115, correlation_group="LAD_GAME"),
    Bet("Ohtani O0.5 HR",        p_win=0.295, american_price=+260, correlation_group="LAD_GAME"),
    Bet("NYY ML",                p_win=0.585, american_price=-128, correlation_group="NYY_GAME"),
    Bet("BOS/NYY UNDER 9.0",     p_win=0.560, american_price=-105, correlation_group="NYY_GAME"),
    Bet("ATL ML",                p_win=0.620, american_price=-148, correlation_group="ATL_GAME"),
    Bet("CIN/COL OVER 10.5",     p_win=0.610, american_price=+108, correlation_group="COL_GAME"),
    Bet("PHI ML",                p_win=0.578, american_price=-138, correlation_group="PHI_GAME"),
]


if __name__ == "__main__":
    bets = DEMO_BETS
    print(f"=== {len(bets)} candidate bets ===")
    print(f"{'Label':<26}{'p_win':>7}{'price':>8}{'EV/$':>9}{'Kelly':>8}{'σ':>7}")
    for b in bets:
        print(f"{b.label:<26}{b.p_win:>7.3f}{b.american_price:>+8d}"
              f"{b.ev_per_dollar:>+9.3f}{b.kelly_fraction*100:>7.2f}%"
              f"{math.sqrt(b.variance_per_dollar):>7.3f}")
    print("\nOptimizing portfolio (10% bankroll cap, lambda=0.5)…")
    stakes, metrics = optimize_portfolio(bets, bankroll_pct=0.10, lambda_risk=0.5)
    print("\nOptimal stakes:")
    print(f"{'Label':<26}{'stake':>10}{'units':>9}{'expected $':>13}")
    for i, b in enumerate(bets):
        ret = stakes[i] * b.ev_per_dollar * 100
        units = stakes[i] * 100
        print(f"{b.label:<26}{stakes[i]*100:>9.3f}%{units:>8.2f}u{ret:>+12.3f}u")
    print(f"\nTotal: {sum(stakes)*100:.2f}% of bankroll")
    print(f"Portfolio E[return]: {metrics['expected_return']*100:+.3f}%")
    print(f"Portfolio std:       {metrics['std']*100:.3f}%")
    print(f"Sharpe (per-play):   {metrics['sharpe']:.3f}")

    os.makedirs("../data", exist_ok=True)
    with open("../data/portfolio.json", "w") as f:
        json.dump({
            "bets": [{
                "label":  b.label, "p_win": b.p_win, "price": b.american_price,
                "ev":     round(b.ev_per_dollar, 4),
                "kelly":  round(b.kelly_fraction, 4),
                "stake_pct_bankroll": round(stakes[i] * 100, 4),
                "stake_units":        round(stakes[i] * 100, 2),
            } for i, b in enumerate(bets)],
            "metrics": metrics,
            "total_bankroll_pct": round(sum(stakes) * 100, 4),
        }, f, indent=2)
    print("\nWrote ../data/portfolio.json")
