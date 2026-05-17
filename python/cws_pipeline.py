"""NCAA Baseball / College World Series scoreboard."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "cws", "espn_path": "baseball/college-baseball",
    "league_label": "NCAA Baseball", "hfa_elo": 25,
    "regulation_seconds": 9000,  # 9 innings, variable
    "n_periods": 9,
    "score_logodds_divisor": 2.5, "score_logodds_multiplier": 2.0,
}
if __name__ == "__main__":
    p = run(CFG)
    print(f"NCAA Baseball: {p['n_games_today']} games")
    for g in p.get("games", [])[:8]:
        print(f"  {g['matchup']} P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}")
