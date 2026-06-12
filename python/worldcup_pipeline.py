"""2026 FIFA World Cup scoreboard (June 11 - July 19, USA/Canada/Mexico).

Same generic ESPN engine as the club leagues. Two World Cup-specific notes:
  - hfa_elo is small (20): venues are administratively "home/away" except for
    the three actual hosts, so a club-sized home edge would be fabricated.
  - Team strength derives from in-tournament records, so the group stage opens
    with flat priors that sharpen as results accrue -- honest, not pre-seeded.
"""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "worldcup",
    "espn_path": "soccer/fifa.world",
    "league_label": "WORLDCUP",
    "hfa_elo": 20,
    "regulation_seconds": 5400,
    "n_periods": 2,
    "score_logodds_divisor": 1.2,
    "score_logodds_multiplier": 2.0,
}

if __name__ == "__main__":
    p = run(CFG)
    print(f"WORLD CUP: {p['n_games_today']} matches ({p['season_status']})")
    for g in p.get("games", []):
        print(f"  {g['matchup']} P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}")
