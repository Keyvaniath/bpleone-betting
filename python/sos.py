"""
EdgeStat - Strength of Schedule (SOS).

A 5-1 record against the Yankees, Astros, Phillies, Braves, Dodgers, Padres
is FAR more impressive than 5-1 against the White Sox, Marlins, Angels,
Rockies, Pirates, A's.  Without adjusting, a season-long futures model would
treat both records the same.

SOS quantifies this:
  - Past SOS: average opponent quality over already-played games
  - Future SOS: average opponent quality over remaining schedule
  - Strength-adjusted record: what a 0.500 team's record would look like
    against this exact schedule

These adjustments matter most for over/under win-total bets and
to-make-playoffs odds, where the back-half schedule can swing the team's
projected wins by 4-6.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ScheduleGame:
    opponent: str
    home: bool
    win: int     # 1 if our team won, 0 if lost, -1 if not yet played


def opp_strength(opp_code: str, ratings: Dict[str, float]) -> float:
    """Return opponent's true-talent (rating)."""
    return ratings.get(opp_code, 0.500)


def past_sos(schedule: List[ScheduleGame], ratings: Dict[str, float]) -> Dict[str, float]:
    """Strength of schedule already played."""
    played = [g for g in schedule if g.win != -1]
    if not played:
        return {"avg_opp_strength": 0.500, "n_games": 0, "wins": 0, "losses": 0}
    sos = sum(opp_strength(g.opponent, ratings) for g in played) / len(played)
    wins = sum(1 for g in played if g.win == 1)
    return {
        "avg_opp_strength": round(sos, 4),
        "n_games":          len(played),
        "wins":             wins,
        "losses":           len(played) - wins,
        "win_pct":          round(wins / len(played), 4),
    }


def future_sos(schedule: List[ScheduleGame], ratings: Dict[str, float]) -> Dict[str, float]:
    """SOS of remaining games."""
    remaining = [g for g in schedule if g.win == -1]
    if not remaining:
        return {"avg_opp_strength": 0.0, "n_games": 0}
    sos = sum(opp_strength(g.opponent, ratings) for g in remaining) / len(remaining)
    return {
        "avg_opp_strength": round(sos, 4),
        "n_games":          len(remaining),
        "home_games":       sum(1 for g in remaining if g.home),
        "away_games":       sum(1 for g in remaining if not g.home),
    }


def strength_adjusted_record(schedule: List[ScheduleGame],
                             team_true_p: float,
                             ratings: Dict[str, float]) -> Dict[str, float]:
    """For each played game, compute the EXPECTED win probability given the
    matchup, then sum to get strength-adjusted expected wins."""
    played = [g for g in schedule if g.win != -1]
    if not played:
        return {"expected_wins": 0, "expected_losses": 0, "actual_wins": 0,
                "actual_losses": 0, "luck": 0.0, "win_pct_actual": 0.0,
                "win_pct_expected": 0.0}
    expected = 0
    for g in played:
        opp_rating = opp_strength(g.opponent, ratings)
        # Bradley-Terry head-to-head.
        p = team_true_p / (team_true_p + (1 - opp_rating))
        # Home field
        if g.home: p = min(0.95, p + 0.025)
        else:      p = max(0.05, p - 0.025)
        expected += p
    actual_w = sum(1 for g in played if g.win == 1)
    return {
        "expected_wins":      round(expected, 2),
        "expected_losses":    round(len(played) - expected, 2),
        "actual_wins":        actual_w,
        "actual_losses":      len(played) - actual_w,
        "luck":               round(actual_w - expected, 2),   # +ve = lucky, -ve = unlucky
        "win_pct_actual":     round(actual_w / len(played), 4),
        "win_pct_expected":   round(expected / len(played), 4),
    }


def project_remaining_wins(schedule: List[ScheduleGame],
                            team_true_p: float,
                            ratings: Dict[str, float]) -> float:
    """Expected wins over remaining games, given team strength and opp strengths."""
    remaining = [g for g in schedule if g.win == -1]
    expected = 0
    for g in remaining:
        opp_rating = opp_strength(g.opponent, ratings)
        p = team_true_p / (team_true_p + (1 - opp_rating))
        if g.home: p = min(0.95, p + 0.025)
        else:      p = max(0.05, p - 0.025)
        expected += p
    return round(expected, 2)


# --------------------------- Demo ---------------------------

DEMO_RATINGS = {
    "LAD": 0.625, "NYY": 0.605, "PHI": 0.591, "ATL": 0.572, "BAL": 0.567,
    "HOU": 0.555, "TEX": 0.555, "CLE": 0.535, "CHC": 0.530, "MIN": 0.522,
    "BOS": 0.518, "DET": 0.512, "MIL": 0.512, "SEA": 0.510, "ARI": 0.510,
    "STL": 0.508, "NYM": 0.502, "SFG": 0.500, "TBR": 0.498, "TOR": 0.495,
    "SDP": 0.495, "WSH": 0.484, "CIN": 0.465, "PIT": 0.460, "OAK": 0.430,
    "COL": 0.420, "KCR": 0.470, "MIA": 0.440, "CHW": 0.395, "LAA": 0.451,
}

# Demo: Dodgers (68 games into season at this snapshot).
LAD_SCHEDULE = []
import random
rng = random.Random(7)
opps = list(DEMO_RATINGS.keys())
opps.remove("LAD")
# 68 played games
for _ in range(68):
    o = rng.choice(opps)
    home = rng.random() < 0.5
    # Bradley-Terry win prob
    p = 0.625 / (0.625 + (1 - DEMO_RATINGS[o]))
    if home: p = min(0.95, p + 0.025)
    else:    p = max(0.05, p - 0.025)
    LAD_SCHEDULE.append(ScheduleGame(opponent=o, home=home,
                                     win=1 if rng.random() < p else 0))
# 94 remaining
for _ in range(94):
    LAD_SCHEDULE.append(ScheduleGame(opponent=rng.choice(opps),
                                     home=rng.random() < 0.5, win=-1))


if __name__ == "__main__":
    print("=== Dodgers SOS analysis ===\n")
    past = past_sos(LAD_SCHEDULE, DEMO_RATINGS)
    fut = future_sos(LAD_SCHEDULE, DEMO_RATINGS)
    sar = strength_adjusted_record(LAD_SCHEDULE, 0.625, DEMO_RATINGS)
    proj = project_remaining_wins(LAD_SCHEDULE, 0.625, DEMO_RATINGS)
    print("Past schedule:")
    for k, v in past.items():
        print(f"  {k:>20}: {v}")
    print("\nRemaining schedule:")
    for k, v in fut.items():
        print(f"  {k:>20}: {v}")
    print("\nStrength-adjusted record (past):")
    for k, v in sar.items():
        print(f"  {k:>20}: {v}")
    print(f"\nProjected wins in remaining {fut['n_games']} games: {proj}")
    print(f"Season-end projection: {past['wins'] + proj:.1f} wins")

    os.makedirs("../data", exist_ok=True)
    with open("../data/sos.json", "w") as f:
        json.dump({
            "team": "LAD",
            "past_sos": past, "future_sos": fut,
            "strength_adjusted_record": sar,
            "projected_remaining_wins": proj,
            "season_end_projection_wins": round(past["wins"] + proj, 1),
        }, f, indent=2)
    print("\nWrote ../data/sos.json")
