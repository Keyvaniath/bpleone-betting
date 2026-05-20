"""NCAA Softball / Women's College World Series scoreboard."""
from __future__ import annotations
from espn_generic import run

CFG = {
    "sport_key": "ncaa_softball", "espn_path": "baseball/college-softball",
    "league_label": "NCAA Softball", "hfa_elo": 30,
    "regulation_seconds": 7000,  # 7 innings standard
    "n_periods": 7,
    "score_logodds_divisor": 2.2, "score_logodds_multiplier": 2.0,
}
if __name__ == "__main__":
    p = run(CFG)
    print(f"NCAA Softball: {p['n_games_today']} games")
    for g in p.get("games", [])[:8]:
        print(f"  {g.get('matchup','?')[:50]:50s} | p_home={g.get('p_home_win', 0):.3f}")
