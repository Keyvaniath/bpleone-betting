"""
EdgeStat -- pitcher days of rest tracker.

For each starting pitcher in today's slate, compute days since their last
start. Standard rest is 4-5 days. Less = short rest (often less effective).
More = extra rest (can be either way -- some pitchers thrive on more rest,
some get rusty).

Writes data/pitcher_rest.json keyed by gamePk + starter side.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pitcher_rest.json")


def days_of_rest(pid: int, today_iso: Optional[str] = None) -> Dict[str, Any]:
    """Return {last_start_date, days_rest, label}."""
    if not pid:
        return {}
    today = dt.date.fromisoformat(today_iso) if today_iso else dt.date.today()
    log = sr.pitcher_gamelog(pid)
    starts = [g for g in log if (g["stat"].get("inningsPitched") or 0) >= 3]
    if not starts:
        return {}
    last = starts[0]
    last_date_str = last.get("date") or ""
    try:
        last_date = dt.date.fromisoformat(last_date_str)
    except Exception:
        return {}
    rest = (today - last_date).days
    if rest <= 3:
        label = "short rest"
    elif rest == 4:
        label = "4 days (normal)"
    elif rest == 5:
        label = "5 days (slight extra)"
    elif rest <= 7:
        label = "extra rest"
    else:
        label = "extended layoff"
    return {
        "last_start_date": last_date_str,
        "days_rest": rest,
        "label": label,
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(os.path.dirname(__file__), "..", "data", "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    today_iso = dt.date.today().isoformat()
    out_games = []
    for g in m.get("games", []):
        home_p = (g.get("home_pitcher") or {})
        away_p = (g.get("away_pitcher") or {})
        out_games.append({
            "matchup": g.get("matchup"),
            "home_pitcher": home_p.get("name"),
            "home_rest": days_of_rest(home_p.get("id"), today_iso),
            "away_pitcher": away_p.get("name"),
            "away_rest": days_of_rest(away_p.get("id"), today_iso),
        })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
    }


def write_rest(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote pitcher_rest -> {path}")
    print(f"  Games covered: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:6]:
        hr = g.get("home_rest") or {}
        ar = g.get("away_rest") or {}
        print(f"  {g['matchup']:14} | home {g['home_pitcher']}: {hr.get('label', '?')} ({hr.get('days_rest', '?')}d) | "
              f"away {g['away_pitcher']}: {ar.get('label', '?')} ({ar.get('days_rest', '?')}d)")


if __name__ == "__main__":
    write_rest(build_all())
