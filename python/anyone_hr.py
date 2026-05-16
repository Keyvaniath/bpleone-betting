"""
EdgeStat -- "anyone hits a HR in this game" probability per game.

For each game tonight, computes P(at least one home run by anyone on
either team) using independent per-batter HR probabilities derived from
HR per PA + expected PA per batter. Some sportsbooks offer an "Anyone HR"
prop -- this gives us a fair price + edge vs market.

Output: data/anyone_hr.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
OUT_PATH = os.path.join(DATA_DIR, "anyone_hr.json")

LEAGUE_HR_PER_PA = 0.034   # ~ MLB league average HR / PA
DEFAULT_PA_PER_LINEUP_BATTER = 4.3   # average PA per starting batter per game


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _hr_per_pa(season: Dict[str, Any]) -> float:
    pa = season.get("plateAppearances") or 0
    hr = season.get("homeRuns") or 0
    if pa < 50:
        return LEAGUE_HR_PER_PA
    return hr / pa if pa else LEAGUE_HR_PER_PA


def run() -> Dict[str, Any]:
    matchups = _load(MATCHUPS_PATH)
    today = _load(TODAY_PATH)
    park_factors: Dict[str, float] = {}
    for g in today.get("games") or []:
        park_factors[g.get("matchup", "")] = (g.get("model") or {}).get("park_hr_factor") or 1.0

    out: List[Dict[str, Any]] = []
    for g in matchups.get("games") or []:
        matchup = g.get("matchup")
        park = g.get("park")
        park_factor = park_factors.get(matchup, 1.0)
        # Adjust everyone's HR/PA by park factor
        p_no_hr = 1.0
        n_batters = 0
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                # Need season HR/PA on the batter. matchups.json may not have
                # it for batters by default, so fall back to league avg.
                hr_per_pa = LEAGUE_HR_PER_PA
                season = (b.get("season") or {})
                if season:
                    hr_per_pa = _hr_per_pa(season)
                # Adjust by park
                adjusted = hr_per_pa * park_factor
                # PA estimate by lineup spot (leadoff ~ 4.7, 9 hitter ~ 3.9)
                spot = b.get("order") or 5
                pa = DEFAULT_PA_PER_LINEUP_BATTER + (5 - spot) * 0.1
                p_no_hr_this_batter = (1 - adjusted) ** pa
                p_no_hr *= p_no_hr_this_batter
                n_batters += 1
        if n_batters == 0:
            continue
        p_at_least_one = 1 - p_no_hr
        # Convert to fair odds
        if p_at_least_one >= 0.5:
            fair_american = int(round(-100 / ((1 / p_at_least_one) - 1)))
        else:
            fair_american = int(round(((1 / p_at_least_one) - 1) * 100))
        out.append({
            "matchup": matchup,
            "park": park,
            "park_factor": park_factor,
            "n_batters": n_batters,
            "p_anyone_hr": round(p_at_least_one, 4),
            "p_no_hr": round(p_no_hr, 4),
            "fair_yes_american": fair_american,
            "fair_no_american": -fair_american if abs(fair_american) >= 100 else 0,
        })
    out.sort(key=lambda x: -x["p_anyone_hr"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(out),
        "league_hr_per_pa": LEAGUE_HR_PER_PA,
        "games": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games']} games scored")
    for g in p["games"][:5]:
        print(f"  {g['matchup']:18} {g['park']:25} factor {g['park_factor']:.2f} P(anyone HR) {g['p_anyone_hr']:.3f} fair {g['fair_yes_american']:+d}")
