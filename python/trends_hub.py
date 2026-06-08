"""
EdgeStat -- league-wide Trends hub aggregator (powers trends.html).

One JSON to "scan the whole slate for trends": biggest model under/over-rates
(ATS), hottest & coldest teams and bats, a starting-pitcher form leaderboard, and
NRFI / run-environment leans. Pure join over feeds that already exist
(ats_tracker, team_form, hot_streaks, pitcher form trackers, nrfi) -- no new model.

Output: data/trends_hub.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "trends_hub.json")


def _load(name: str) -> Any:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _rows(j: Any, *keys) -> List[Dict[str, Any]]:
    if isinstance(j, list):
        return [r for r in j if isinstance(r, dict)]
    if not isinstance(j, dict):
        return []
    for k in keys + ("rows",):
        v = j.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def _num(x, d=0.0):
    try:
        return float(x) if x is not None else d
    except Exception:
        return d


def run() -> Dict[str, Any]:
    ats = _load("ats_tracker_mlb.json")
    tf = (_load("team_form.json").get("teams") or {})
    teams = [v for v in tf.values() if isinstance(v, dict)]
    hot = _load("hot_streaks.json")

    # pitcher form leaderboard: recent-form index (0-100) + heating/cooling status
    rfi = _rows(_load("mlb_starter_recent_form_index.json"))
    status_by_pitcher = {r.get("pitcher"): r.get("status")
                         for r in _rows(_load("mlb_pitcher_form_tracker.json"))}
    pform = []
    for r in rfi:
        pform.append({
            "pitcher": r.get("pitcher"), "team": r.get("team"), "matchup": r.get("matchup"),
            "form_index": r.get("form_index"), "tier": r.get("tier"), "trend": r.get("trend"),
            "recent_k9": r.get("recent_k9"), "season_k9": r.get("season_k9"),
            "recent_era": r.get("recent_era"), "season_era": r.get("season_era"),
            "status": status_by_pitcher.get(r.get("pitcher")),
        })
    pform.sort(key=lambda p: -_num(p.get("form_index")))

    def _slim_team(t):
        return {k: t.get(k) for k in ("abbr", "wins", "losses", "run_diff", "runs_pg",
                                      "runs_allowed_pg", "streak", "games_in_sample")}

    hottest = sorted(teams, key=lambda t: -_num(t.get("run_diff")))[:8]
    coldest = sorted(teams, key=lambda t: _num(t.get("run_diff")))[:8]
    high_scoring = sorted(teams, key=lambda t: -_num(t.get("runs_pg")))[:6]
    pitching_best = sorted(teams, key=lambda t: _num(t.get("runs_allowed_pg")))[:6]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "date": (_load("today.json").get("date")),
        "method_note": "League-wide trend scan: ATS model under/over-rates, hottest/coldest "
                       "teams by run differential, hot/cold bats (L7 OPS), starting-pitcher "
                       "form leaderboard, run-environment + NRFI leans. Joined from existing feeds.",
        "model_underrates": (ats.get("model_underrates_top5") or [])[:8],
        "model_overrates": (ats.get("model_overrates_top5") or [])[:8],
        "hottest_teams": [_slim_team(t) for t in hottest],
        "coldest_teams": [_slim_team(t) for t in coldest],
        "high_scoring_teams": [_slim_team(t) for t in high_scoring],
        "best_run_prevention": [_slim_team(t) for t in pitching_best],
        "hot_bats": (hot.get("hot_batters") or [])[:15],
        "cold_bats": (hot.get("cold_batters") or [])[:10],
        "pitcher_form_leaderboard": pform[:20],
        "hot_pitchers": (hot.get("hot_pitchers") or [])[:10],
        "cold_pitchers": (hot.get("cold_pitchers") or [])[:10],
        "nrfi_leans": _rows(_load("nrfi.json"))[:16],
        "counts": {
            "teams_ranked": len(teams),
            "hot_bats": len(hot.get("hot_batters") or []),
            "pitchers_ranked": len(pform),
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[trends-hub] {o['counts']['teams_ranked']} teams, {o['counts']['hot_bats']} hot bats, "
          f"{o['counts']['pitchers_ranked']} pitchers ranked -> {OUT}")
