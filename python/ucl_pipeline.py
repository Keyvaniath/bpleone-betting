"""UEFA Champions League soccer scoreboard."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "ucl",
    "espn_path": "soccer/uefa.champions",
    "league_label": "Champions League",
    "hfa_elo": 50,
    "regulation_seconds": 5400,
    "n_periods": 2,
    "score_logodds_divisor": 1.2,
    "score_logodds_multiplier": 2.0,
}

if __name__ == "__main__":
    p = run(CFG)
    print(f"UCL: {p.get('n_games_today', 0)} matches ({p.get('season_status', '?')})")
    for g in p.get("games", []):
        try:   # display only: one unpriced row must not fail the module
            print(f"  {g['matchup']} P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}")
        except (TypeError, KeyError, ValueError):
            print(f"  {g.get('matchup') or g.get('name')} (incomplete row)")
