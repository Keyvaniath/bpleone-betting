"""
EdgeStat -- NHL team-level prop projections.

For each NHL playoff game tonight, projects team-level markets:
  - Total Goals over/under 4.5 / 5.5 / 6.5 / 7.5
  - Both Teams Score Yes/No (less common in NHL but bookable)
  - Each team to score over 1.5 / 2.5 / 3.5
  - 1st Period Total Goals over/under 0.5 / 1.5

NHL is lower-scoring than soccer (avg ~6 GPG combined including OT),
so different baselines than soccer_extended_props.

Math: convert p_home_win + league avg total goals (~6.0) into per-team
expected goals (xG), then Poisson-project totals.

Output: data/nhl_team_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_props.json")

# NHL playoff average total goals (slightly lower than regular season due to
# defensive play in playoffs). Empirical: 5.7 regular, 5.4 playoffs.
LEAGUE_AVG_TOTAL = 5.7


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_cdf(lam, k):
    return sum(_poisson_p(lam, i) for i in range(k + 1))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_game(g):
    p_home = g.get("p_home_win")
    if p_home is None: return {}

    # home_share: stronger team gets larger share of expected goals.
    # For NHL: 0.5 base + 0.25 * (p_home - 0.5) adjustment
    home_share = 0.5 + 0.25 * (p_home - 0.5)
    home_share = max(0.30, min(0.70, home_share))
    home_xg = LEAGUE_AVG_TOTAL * home_share
    away_xg = LEAGUE_AVG_TOTAL * (1 - home_share)

    def _p_total_over(line):
        thr = int(math.floor(line)) + 1
        return 1 - _poisson_cdf(home_xg + away_xg, thr - 1)

    def _p_team_over(team_xg, line):
        thr = int(math.floor(line)) + 1
        return 1 - _poisson_cdf(team_xg, thr - 1)

    # P(home scores ≥1) * P(away scores ≥1) (rough indep)
    p_home_score = 1 - _poisson_p(home_xg, 0)
    p_away_score = 1 - _poisson_p(away_xg, 0)
    btts_yes = p_home_score * p_away_score

    # First period: typical NHL splits ~25-30% of game goals to 1st (lower)
    # Use 0.27 * total goals as 1st period lambda
    p1_lam = LEAGUE_AVG_TOTAL * 0.27
    p1_over_05 = 1 - _poisson_cdf(p1_lam, 0)
    p1_over_15 = 1 - _poisson_cdf(p1_lam, 1)

    return {
        "home_xg": round(home_xg, 2), "away_xg": round(away_xg, 2),
        "totals": {
            f"over_{line}": {
                "line": line,
                "p": round(_p_total_over(line), 4),
                "fair_over": _american(_p_total_over(line)),
                "fair_under": _american(1 - _p_total_over(line)),
            } for line in (4.5, 5.5, 6.5, 7.5)
        },
        "btts": {
            "yes": round(btts_yes, 4), "no": round(1 - btts_yes, 4),
            "fair_yes": _american(btts_yes), "fair_no": _american(1 - btts_yes),
        },
        "home_team_over_2_5": {
            "p": round(_p_team_over(home_xg, 2.5), 4),
            "fair_yes": _american(_p_team_over(home_xg, 2.5))
        },
        "away_team_over_2_5": {
            "p": round(_p_team_over(away_xg, 2.5), 4),
            "fair_yes": _american(_p_team_over(away_xg, 2.5))
        },
        "first_period_over_0_5": {
            "p": round(p1_over_05, 4),
            "fair_yes": _american(p1_over_05),
            "fair_no": _american(1 - p1_over_05),
        },
        "first_period_over_1_5": {
            "p": round(p1_over_15, 4),
            "fair_yes": _american(p1_over_15),
            "fair_no": _american(1 - p1_over_15),
        },
    }


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games_out: List[Dict[str, Any]] = []
    for g in (state.get("games") or []):
        if g.get("state") == "post": continue
        proj = _project_game(g)
        if not proj: continue
        games_out.append({
            "matchup": g.get("matchup"),
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "p_home_win": g.get("p_home_win"),
            **proj,
        })

    # Sweet-spot picks (55-90%)
    sweet = []
    for g in games_out:
        for line, info in (g.get("totals") or {}).items():
            p = info.get("p")
            if p and 0.55 <= p <= 0.90:
                sweet.append({"matchup": g["matchup"], "market": f"total_{line}",
                                "prob": p, "fair": info.get("fair_over")})
        for side in ("home", "away"):
            info = g.get(f"{side}_team_over_2_5") or {}
            p = info.get("p")
            team = g["home_team"] if side == "home" else g["away_team"]
            if p and 0.55 <= p <= 0.90:
                sweet.append({"matchup": g["matchup"],
                                "market": f"{team}_over_2.5_goals",
                                "prob": p, "fair": info.get("fair_yes")})
        for key in ("first_period_over_0_5", "first_period_over_1_5", "btts"):
            info = g.get(key) or {}
            p = info.get("p") or info.get("yes")
            if p and 0.55 <= p <= 0.90:
                sweet.append({"matchup": g["matchup"], "market": key,
                                "prob": p, "fair": info.get("fair_yes")})
    sweet.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "league_avg_total_used": LEAGUE_AVG_TOTAL,
        "n_sweet_spot": len(sweet),
        "games": games_out,
        "top_picks": sweet[:30],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NHL team props: {p['n_games']} games, {p['n_sweet_spot']} sweet-spot picks")
    for g in p["games"]:
        print(f"  {g['matchup']} | xG home={g['home_xg']} away={g['away_xg']} | "
              f"O5.5={g['totals']['over_5.5']['p']*100:.0f}% (fair {g['totals']['over_5.5']['fair_over']:+d}) | "
              f"BTTS={g['btts']['yes']*100:.0f}% | 1P>0.5={g['first_period_over_0_5']['p']*100:.0f}%")
    print("Top sweet-spot picks:")
    for s in p["top_picks"][:10]:
        print(f"  {s['matchup']:45s} {s['market'][:35]:35s} p={s['prob']*100:.0f}% fair={s['fair']:+d}")
