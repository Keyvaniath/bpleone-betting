"""
EdgeStat - Injury impact model.

The single biggest "edge slippage" event in betting is an injury. A starter
gets scratched 90 minutes before first pitch and the book moves the line —
but how MUCH should it move?  Most public bettors over- or under-adjust.

This module estimates the win-probability hit from losing a player, using
two inputs:

  1. The player's WAR (or projected WAR per game)
  2. The replacement-level player's WAR (~0 by definition; AAA call-up
     typically -0.3 WAR per 162 games)

A 6-WAR player going on the IL costs the team ~6/162 = 0.037 wins per game.
A 6 WAR ace pitcher missing his start is bigger — concentrate the impact on
that one game.

For a single game, the win-probability hit is:
  - position player (lineup): ~0.5-1.5 pp (small, distributed)
  - starting pitcher:        ~3-5 pp     (BIG, concentrated)
  - closer:                  ~1-2 pp     (small but high-leverage)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict


@dataclass
class Player:
    name: str
    position: str        # "SP" / "RP" / "POS" / "CL"
    projected_war_162: float
    games_remaining_in_season: int = 100


@dataclass
class Replacement:
    name: str
    projected_war_162: float = -0.3   # AAA call-up baseline


# --------------------------- Per-game injury impact ---------------------------

POSITION_WEIGHTS = {
    # Wins per game contribution per unit WAR.
    # SP starts ~32 games/yr; missing one of those concentrates impact.
    # POS plays ~140 games/yr; impact is spread.
    "SP":  0.020,   # ~ 0.6-1.0pp per WAR-game (still ~half of full-game WAR equivalent)
    "POS": 0.0055,  # ~1/162 * fraction-of-game played
    "CL":  0.008,   # closer in save situations only
    "RP":  0.004,
}


def single_game_wp_hit(player: Player, replacement: Replacement) -> float:
    """Estimated single-game win-probability decrease in PP."""
    diff = player.projected_war_162 - replacement.projected_war_162
    weight = POSITION_WEIGHTS.get(player.position, 0.01)
    pp = diff * weight * 100   # convert to PP
    return round(pp, 2)


def season_wp_hit(player: Player, replacement: Replacement) -> float:
    """Total projected wins lost over the rest of the season."""
    diff = player.projected_war_162 - replacement.projected_war_162
    return round(diff * player.games_remaining_in_season / 162, 2)


# --------------------------- Line move implication ---------------------------

def implied_line_move(wp_hit_pp: float) -> Dict[str, float]:
    """Translate a WP hit into how much the moneyline should move.

    Rough heuristic: each 1pp of WP corresponds to ~5 cents of American
    odds at typical spreads (-150 to +130 region).  More accurate near 50/50.
    """
    # Convert from WP delta to American odds delta around -120 baseline.
    cents = wp_hit_pp * 5
    return {
        "wp_hit_pp":          round(wp_hit_pp, 2),
        "approx_cents_shift": round(cents, 1),
        "interpretation":     ("favorite is " + ("less" if wp_hit_pp > 0 else "more") +
                               " favored — line should move " +
                               ("toward pick'em" if abs(wp_hit_pp) > 0 else "very little")),
    }


# --------------------------- Demo ---------------------------

DEMO_INJURIES = [
    ("Mookie Betts (POS, 6.5 WAR) IL-10 day", Player("Mookie Betts", "POS", 6.5, 100), Replacement("AAA Util")),
    ("Yamamoto (SP, 5.0 WAR) misses start",   Player("Yamamoto", "SP", 5.0, 0),         Replacement("AAA SP")),
    ("Devin Williams (CL, 2.2 WAR) day-to-day",Player("D. Williams", "CL", 2.2, 0),     Replacement("AAA RP")),
    ("Aaron Judge (POS, 9.0 WAR) 60-day IL",  Player("Aaron Judge", "POS", 9.0, 100),   Replacement("AAA OF")),
]

if __name__ == "__main__":
    print("=== INJURY IMPACT TABLE ===")
    payload = []
    print(f"{'Scenario':<46}{'WP/game':>10}{'season-W lost':>17}")
    for label, p, r in DEMO_INJURIES:
        wp = single_game_wp_hit(p, r)
        seasonal = season_wp_hit(p, r) if p.games_remaining_in_season > 0 else 0.0
        print(f"{label:<46}{wp:>9.2f}pp{seasonal:>15.2f}w")
        payload.append({
            "scenario": label,
            "single_game_wp_hit_pp": wp,
            "season_wins_lost": seasonal,
            "line_move": implied_line_move(wp),
        })
    os.makedirs("../data", exist_ok=True)
    with open("../data/injuries.json", "w") as f:
        json.dump({"examples": payload}, f, indent=2)
    print("\nWrote ../data/injuries.json")
