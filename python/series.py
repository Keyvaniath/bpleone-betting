"""
EdgeStat - Multi-game series probability model.

Single-game models only get you so far.  Three-game weekend series are the
real unit of MLB scheduling, and pricing the SERIES is a sharper play than
betting any single game.  Books usually have softer lines on series totals
("Series Bettor: -1.5", "Series win 2-1") because handle is thin.

This module computes:
  - P(team A wins series 2-0 / 2-1 / loses 1-2 / loses 0-2 / etc.)
  - Expected series win percentage
  - Fair series moneyline
  - Series alternative markets (>= 1 win, sweep, etc.)

Inputs are the per-game win probabilities for the series rotation.
Output is the full multinomial distribution over series outcomes.
"""
from __future__ import annotations

import math
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


# --------------------------- Outcome enumeration ---------------------------

def series_outcomes(per_game_probs: List[float]) -> Dict[str, float]:
    """Given P(team A wins) for each game, return probability of every
    possible W/L sequence.

    Length of per_game_probs = number of games in the series (2, 3, or 4).
    Output keys are strings like "WLW", "WWL", etc.
    """
    n = len(per_game_probs)
    out: Dict[str, float] = {}
    for mask in range(2 ** n):
        # Each bit = whether team A won that game.
        seq = ""
        p = 1.0
        for i in range(n):
            won_i = (mask >> (n - 1 - i)) & 1
            seq += "W" if won_i else "L"
            p *= per_game_probs[i] if won_i else (1 - per_game_probs[i])
        out[seq] = p
    return out


def series_win_distribution(per_game_probs: List[float]) -> Dict[str, float]:
    """Sum outcomes by total W count.
    Returns e.g. {"3-0": .12, "2-1": .35, "1-2": .35, "0-3": .18}.
    """
    n = len(per_game_probs)
    outcomes = series_outcomes(per_game_probs)
    dist: Dict[str, float] = {}
    for seq, p in outcomes.items():
        wins = seq.count("W")
        losses = n - wins
        key = f"{wins}-{losses}"
        dist[key] = dist.get(key, 0) + p
    return dist


def expected_wins(per_game_probs: List[float]) -> float:
    """Expected number of wins in the series."""
    return sum(per_game_probs)


def p_team_a_wins_series(per_game_probs: List[float]) -> float:
    """Probability team A wins MORE games than team B over the series."""
    n = len(per_game_probs)
    p = 0.0
    half = 0.0
    for seq, prob in series_outcomes(per_game_probs).items():
        wins = seq.count("W")
        if wins > n - wins:
            p += prob
        elif wins == n - wins:
            half += prob
    # On split series, "series winner" is undefined; convention = tie (no bet).
    return p


def p_sweep(per_game_probs: List[float]) -> Tuple[float, float]:
    """(P(team A sweeps), P(team B sweeps))."""
    p_all_w = 1.0
    p_all_l = 1.0
    for p in per_game_probs:
        p_all_w *= p
        p_all_l *= (1 - p)
    return p_all_w, p_all_l


# --------------------------- Pricing ---------------------------

def prob_to_american(p: float) -> int:
    if p <= 0.01 or p >= 0.99:
        return 0
    dec = 1 / p
    return int(round((dec - 1) * 100)) if dec >= 2 else -int(round(100 / (dec - 1)))


def fair_series_market(per_game_probs: List[float], vig_pct: float = 4.5) -> Dict[str, dict]:
    """Build a full series betting market with fair prices."""
    dist = series_win_distribution(per_game_probs)
    pA = p_team_a_wins_series(per_game_probs)
    swA, swB = p_sweep(per_game_probs)
    n = len(per_game_probs)

    def add_vig(p):
        # 2-way market vig split: scale each side up half the vig.
        return p / (1 - vig_pct / 200)

    return {
        "team_a_wins_series": {
            "prob": round(pA, 4),
            "fair": prob_to_american(pA),
            "with_vig": prob_to_american(min(0.98, add_vig(pA))),
        },
        "team_b_wins_series": {
            "prob": round(1 - pA, 4),
            "fair": prob_to_american(1 - pA),
            "with_vig": prob_to_american(min(0.98, add_vig(1 - pA))),
        },
        "team_a_sweep": {
            "prob": round(swA, 4),
            "fair": prob_to_american(swA),
        },
        "team_b_sweep": {
            "prob": round(swB, 4),
            "fair": prob_to_american(swB),
        },
        "expected_wins_team_a": round(expected_wins(per_game_probs), 3),
        "distribution":  {k: round(v, 4) for k, v in dist.items()},
        "all_outcomes":  {k: round(v, 4) for k, v in series_outcomes(per_game_probs).items()},
        "series_length": n,
    }


# --------------------------- Pitching rotation matching ---------------------------
#
# If you know each team's projected starter ERA-FIP per game, you can
# adjust per-game probabilities accordingly.  This is the "rotation
# matching" step that books often miss for short-handed series.

def rotation_adjusted(base_per_game: List[float],
                      starter_xfip_team_a: List[float],
                      starter_xfip_team_b: List[float],
                      sensitivity: float = 0.05) -> List[float]:
    """Adjust each per-game win prob by the relative xFIP of starters.

    `sensitivity` = how much a 1.0 xFIP gap moves win probability.
    Empirically ~0.04-0.06 for MLB.
    """
    out = []
    for i, p in enumerate(base_per_game):
        gap = starter_xfip_team_b[i] - starter_xfip_team_a[i]  # + = A has better starter
        adjusted = max(0.05, min(0.95, p + gap * sensitivity))
        out.append(adjusted)
    return out


# --------------------------- Demo ---------------------------

if __name__ == "__main__":
    # Example: LAD hosts SDP for a 3-game series.  LAD has the rotation
    # advantage in Games 1 and 2 (Yamamoto, Snell vs Darvish, Cease) but
    # SDP throws their #1 in Game 3.
    base_prob = [0.62, 0.61, 0.55]    # base LAD win prob per game
    print("=== Base series (no rotation adjustment) ===")
    market = fair_series_market(base_prob, vig_pct=4.5)
    for k, v in market.items():
        if k == "all_outcomes": continue
        print(f"  {k:>22}: {v}")

    # Now adjust for actual starter quality.
    lad_starters_xfip = [2.89, 3.20, 4.10]  # Yamamoto, Snell, Glasnow
    sdp_starters_xfip = [4.12, 3.85, 2.95]  # Darvish, Cease, King
    adjusted_prob = rotation_adjusted(base_prob, lad_starters_xfip, sdp_starters_xfip)
    print(f"\nRotation-adjusted per-game probs: {[round(p, 3) for p in adjusted_prob]}")
    market2 = fair_series_market(adjusted_prob, vig_pct=4.5)
    print("\n=== Rotation-adjusted series market ===")
    for k, v in market2.items():
        if k == "all_outcomes": continue
        print(f"  {k:>22}: {v}")

    os.makedirs("../data", exist_ok=True)
    with open("../data/series.json", "w") as f:
        json.dump({
            "matchup": "LAD vs SDP (3-game home series)",
            "base":     market,
            "adjusted": market2,
            "rotation_starters_a": ["Yamamoto", "Snell", "Glasnow"],
            "rotation_starters_b": ["Darvish", "Cease", "King"],
        }, f, indent=2)
    print("\nWrote ../data/series.json")
