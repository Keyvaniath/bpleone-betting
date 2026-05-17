"""NCAA Football scoreboard (60-min game, big HFA, late upsets common)."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "ncaaf", "espn_path": "football/college-football",
    "league_label": "NCAA Football", "hfa_elo": 60,
    "regulation_seconds": 3600, "n_periods": 4,
    "score_logodds_divisor": 7.0, "score_logodds_multiplier": 2.0,
}
if __name__ == "__main__":
    p = run(CFG)
    print(f"NCAA Football: {p['n_games_today']} games ({p['season_status']})")
    for g in p.get("games", [])[:10]:
        print(f"  {g['matchup']} P(home) = {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}")
