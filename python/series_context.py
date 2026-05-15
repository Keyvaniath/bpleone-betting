"""
EdgeStat -- series context tracker.

For each game tonight, find the last 7 days of head-to-head games between
the same two teams. Outputs:
  - Series number (Game 1, 2, 3, or 4)
  - Prior result(s) summary
  - Blowout flag if any prior game was 5+ run differential
  - Sweep / split context

Useful research signal: teams that just got pasted 12-3 the night before
tend to bounce back; rubber games trend lower-scoring; etc.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "series_context.json")


def _fetch_h2h(team_a_id: int, team_b_id: int, before_date: str) -> List[Dict[str, Any]]:
    """Get completed games between two teams in the last 7 days."""
    if requests is None:
        return []
    look_back = (dt.date.fromisoformat(before_date) - dt.timedelta(days=7)).isoformat()
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "teamId": team_a_id,
                    "startDate": look_back, "endDate": before_date,
                    "opponentId": team_b_id},
            timeout=10,
        )
        if not r.ok:
            return []
        sched = r.json().get("dates", [])
    except Exception:
        return []
    out = []
    for d in sched:
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") != "Final":
                continue
            if (g.get("officialDate") or "") >= before_date:
                continue
            out.append(g)
    out.sort(key=lambda x: x.get("officialDate") or "")
    return out


def project_series(home_id: int, away_id: int, today_date: str) -> Dict[str, Any]:
    """Return series context for tonight."""
    h2h = _fetch_h2h(home_id, away_id, today_date)
    if not h2h:
        return {"series_number": 1, "prior_results": [], "note": "first meeting / no recent H2H"}
    results = []
    blowouts = 0
    home_wins = 0
    away_wins = 0
    for g in h2h:
        try:
            h_runs = int(g["teams"]["home"].get("score") or 0)
            a_runs = int(g["teams"]["away"].get("score") or 0)
        except Exception:
            continue
        h_id = g["teams"]["home"]["team"]["id"]
        a_id = g["teams"]["away"]["team"]["id"]
        # Normalize to our home/away labels
        if h_id == home_id:
            tonight_home_score = h_runs
            tonight_away_score = a_runs
        else:
            tonight_home_score = a_runs
            tonight_away_score = h_runs
        margin = tonight_home_score - tonight_away_score
        winner = "home" if margin > 0 else "away"
        if winner == "home":
            home_wins += 1
        else:
            away_wins += 1
        if abs(margin) >= 5:
            blowouts += 1
        results.append({
            "date": g.get("officialDate"),
            "home_score": tonight_home_score,
            "away_score": tonight_away_score,
            "margin": margin,
            "winner": winner,
        })

    series_num = len(results) + 1
    note_parts = []
    if series_num == 2:
        last = results[-1]
        if abs(last["margin"]) >= 5:
            loser = "away" if last["winner"] == "home" else "home"
            note_parts.append(f"Game 1 blowout (margin {last['margin']:+d}); {loser} typically bounces back")
        else:
            note_parts.append("Coming off close Game 1")
    elif series_num == 3:
        if home_wins == 2 or away_wins == 2:
            leader = "home" if home_wins == 2 else "away"
            note_parts.append(f"Series finale; {leader} can sweep")
        else:
            note_parts.append("Rubber match (series tied 1-1)")
    elif series_num == 4:
        note_parts.append(f"Series record so far: home {home_wins}-{away_wins}")

    if blowouts:
        note_parts.append(f"{blowouts} blowout(s) in this set")

    return {
        "series_number": series_num,
        "prior_results": results,
        "home_wins_in_series": home_wins,
        "away_wins_in_series": away_wins,
        "blowouts_in_series": blowouts,
        "note": " - ".join(note_parts) or "no special context",
    }


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "games": []}
    with open(matchups_path) as f:
        m = json.load(f)
    today_date = dt.date.today().isoformat()
    out_games = []
    for g in m.get("games", []):
        home_id = (g.get("home") or {}).get("team_id")
        away_id = (g.get("away") or {}).get("team_id")
        if not home_id or not away_id:
            continue
        ctx = project_series(home_id, away_id, today_date)
        out_games.append({
            "matchup": g.get("matchup"),
            "time": g.get("time"),
            **ctx,
        })
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "games": out_games}


def write_series(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote series_context -> {path}")
    print(f"  Games covered: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        print(f"  {g['matchup']:14} | Game {g['series_number']} of series | {g.get('note', '')}")


if __name__ == "__main__":
    write_series(build_all())
