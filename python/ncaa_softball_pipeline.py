"""NCAA Softball / Women's College World Series scoreboard."""
from __future__ import annotations
from espn_generic import run


def _fmtv(v, spec, dflt="?"):
    """Display-safe format (2026-10-26): `{x.get(k, d):spec}` crashes when the
    key exists with None -- .get's default only applies to a MISSING key --
    and a display print must never fail the module (the 30-day cascade
    started exactly this way)."""
    if v is None:
        return str(dflt)
    try:
        return format(v, spec)
    except (TypeError, ValueError):
        return str(v)

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
        print(f"  {g.get('matchup','?')[:50]:50s} | p_home={_fmtv(g.get('p_home_win'), '.3f', 0)}")
