"""NCAA Men's Basketball scoreboard."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "ncaab", "espn_path": "basketball/mens-college-basketball",
    "league_label": "NCAA MBB", "hfa_elo": 40,
    "regulation_seconds": 2400, "n_periods": 2,    # 2 x 20 halves
    "score_logodds_divisor": 4.0, "score_logodds_multiplier": 2.0,
}
if __name__ == "__main__":
    p = run(CFG)
    print(f"NCAA MBB: {p['n_games_today']} games")
    for g in p.get("games", [])[:5]:
        print(f"  {g['matchup']} P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}")
