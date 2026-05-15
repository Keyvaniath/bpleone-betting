"""
EdgeStat -- Pythagorean expected wins per team.

Bill James' Pythagorean expectation: expected_win_pct = R^2 / (R^2 + RA^2)
(using exponent 1.83 for MLB).

Teams with actual W-L significantly diverging from Pythagorean expectation
tend to regress -- "lucky" teams give back wins, "unlucky" teams gain them.

Outputs per team:
  - season runs scored / allowed
  - actual W-L
  - pythag expected W-L
  - luck (actual_wins - pythag_wins): positive = lucky, negative = unlucky

Writes data/pythagorean.json.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pythagorean.json")
EXP = 1.83


def fetch_team_record(team_id: int) -> Dict[str, Any]:
    """Get current season W-L + runs for/against."""
    season = dt.date.today().year
    if requests is None:
        return {}
    try:
        # Pull from team standings record
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/standings",
            params={"leagueId": "103,104", "season": season,
                    "standingsTypes": "regularSeason"},
            timeout=10,
        )
        if not r.ok:
            return {}
        data = r.json()
    except Exception:
        return {}
    for rec in data.get("records", []):
        for tr in rec.get("teamRecords", []):
            if tr.get("team", {}).get("id") == team_id:
                rs = int(tr.get("runsScored") or 0)
                ra = int(tr.get("runsAllowed") or 0)
                w = int(tr.get("wins") or 0)
                l = int(tr.get("losses") or 0)
                gp = w + l
                pythag_pct = (rs ** EXP) / ((rs ** EXP) + (ra ** EXP)) if (rs + ra) else 0.5
                pythag_w = round(pythag_pct * gp, 1) if gp else None
                luck = round(w - (pythag_w or 0), 1) if pythag_w else 0
                return {
                    "wins": w, "losses": l, "games": gp,
                    "runs_scored": rs, "runs_allowed": ra,
                    "run_diff": rs - ra,
                    "pythag_pct": round(pythag_pct, 4),
                    "pythag_wins": pythag_w,
                    "luck_wins": luck,   # positive = lucky, negative = unlucky
                }
    return {}


def build_all() -> Dict[str, Any]:
    teams = sr._teams()
    out: Dict[str, Any] = {}
    # The standings endpoint returns ALL teams in one call, but for simplicity:
    # call once per team via filter (this also caches per-team via _get).
    for name, info in teams.items():
        rec = fetch_team_record(info["id"])
        if rec:
            out[name] = {"abbr": info.get("abbr"), **rec}
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "exponent": EXP,
        "teams": out,
    }


def write_pythag(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote pythagorean -> {path}")
    teams = payload.get("teams") or {}
    print(f"  Teams covered: {len(teams)}")
    # Print 3 luckiest + 3 unluckiest
    sorted_by_luck = sorted(teams.items(), key=lambda kv: -kv[1].get("luck_wins", 0))
    print("  Luckiest 3 (over-performing pythag):")
    for n, t in sorted_by_luck[:3]:
        print(f"    {n:25} actual {t['wins']}-{t['losses']} vs pythag {t['pythag_wins']} (+{t['luck_wins']:.1f} luck)")
    print("  Unluckiest 3 (due to regress positively):")
    for n, t in sorted_by_luck[-3:]:
        print(f"    {n:25} actual {t['wins']}-{t['losses']} vs pythag {t['pythag_wins']} ({t['luck_wins']:+.1f} luck)")


if __name__ == "__main__":
    write_pythag(build_all())
