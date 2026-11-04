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
    # (2026-11-03) Every tile here is MLB. In the offseason (today.json
    # no_games) the feeds are frozen end-of-season snapshots and team_form.json
    # holds 4 teams -- top-8 "hottest" and "coldest" were the SAME 4 teams.
    # Offseason -> suppress MLB; a top-k/bottom-k board needs > 2k teams.
    today = _load("today.json")
    offseason = bool(today.get("no_games")) or not (today.get("games") or [])
    ats = {} if offseason else _load("ats_tracker_mlb.json")
    tf = {} if offseason else (_load("team_form.json").get("teams") or {})
    teams = [v for v in tf.values() if isinstance(v, dict)]
    hot = {} if offseason else _load("hot_streaks.json")

    # pitcher form leaderboard: recent-form index (0-100) + heating/cooling status
    rfi = [] if offseason else _rows(_load("mlb_starter_recent_form_index.json"))
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

    def _top(key, k, rev):
        # a distinct top-k / bottom-k needs more than 2k teams (2026-11-03)
        if len(teams) <= 2 * k:
            return []
        return sorted(teams, key=lambda t: (-1 if rev else 1) * _num(t.get(key)))[:k]
    hottest = _top("run_diff", 8, True)
    coldest = _top("run_diff", 8, False)
    high_scoring = _top("runs_pg", 6, True)
    pitching_best = _top("runs_allowed_pg", 6, False)

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "date": (_load("today.json").get("date")),
        "method_note": "League-wide MLB trend scan: record vs the MODEL'S OWN spread (not a "
                       "sportsbook spread; n >= 20 decided games), hottest/coldest teams by run "
                       "differential (only with > 2k teams), hot/cold bats (L7 OPS), starting-"
                       "pitcher form. Context, not recommendations. Suppressed in the offseason.",
        "offseason": offseason,
        "season_note": ("MLB offseason: no games on the board, so the MLB trend tiles are "
                        "suppressed until Opening Day." if offseason else None),
        "ats_basis": ats.get("basis"),
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
        "nrfi_leans": [],   # (2026-11-03) model P vs a league baseline is not a price/lean
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
