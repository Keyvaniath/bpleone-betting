"""WNBA scoreboard pipeline (40-min game, 4 x 10min quarters, +30 HFA)."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "wnba",
    "espn_path": "basketball/wnba",
    "league_label": "WNBA",
    "hfa_elo": 30,
    "regulation_seconds": 2400,  # 40 min
    "n_periods": 4,
    "score_logodds_divisor": 3.0,
    "score_logodds_multiplier": 2.5,
}

if __name__ == "__main__":
    p = run(CFG)
    print(f"WNBA: {p.get('n_games_today', 0)} games ({p.get('season_status', '?')})")
    for g in p.get("games", []):
        try:   # display only: one unpriced row must not fail the module
            print(f"  {g['matchup']} ({g['away_record']} vs {g['home_record']}) "
                  f"P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}")
        except (TypeError, KeyError, ValueError):
            print(f"  {g.get('matchup') or g.get('name')} (incomplete row)")
