"""NFL scoreboard (60-min game, 4 x 15 quarters, +55 HFA, 7pt = late lead)."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "nfl",
    "espn_path": "football/nfl",
    "league_label": "NFL",
    "hfa_elo": 55,
    "regulation_seconds": 3600,    # 60 min
    "n_periods": 4,
    "score_logodds_divisor": 7.0,  # 7pt lead = late game
    "score_logodds_multiplier": 2.0,
}

if __name__ == "__main__":
    p = run(CFG)
    print(f"NFL: {p['n_games_today']} games ({p['season_status']})")
    for g in p.get("games", []):
        print(f"  {g['matchup']} ({g['away_record']} vs {g['home_record']}) "
              f"P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}")
