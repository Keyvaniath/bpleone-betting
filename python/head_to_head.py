"""
EdgeStat -- head-to-head matchup history per sport.

For every team pair that has played in our historical_<sport>.json,
computes their head-to-head record + per-game scoring history.
Used to overlay context onto today's matchups ("Lakers are 0-3 vs Thunder
in the last 14 days, averaging 8 fewer points").

Output: data/h2h_<sport>.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "cws", "mlb"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def compute_h2h(sport: str) -> Dict[str, Any]:
    h = _load(os.path.join(DATA_DIR, f"historical_{sport}.json"))
    games = h.get("games") or []
    matchups: Dict[str, Any] = {}
    for g in games:
        a, b = sorted([g.get("home_team"), g.get("away_team")])
        if not (a and b): continue
        key = f"{a}|||{b}"
        m = matchups.setdefault(key, {
            "team_a": a, "team_b": b,
            "n_games": 0,
            "a_wins": 0, "b_wins": 0, "draws": 0,
            "avg_total": 0,
            "games": [],
        })
        m["n_games"] += 1
        if g["winner"] == a: m["a_wins"] += 1
        elif g["winner"] == b: m["b_wins"] += 1
        else: m["draws"] += 1
        m["avg_total"] += g["total"]
        m["games"].append({
            "date": g["date"],
            "home": g["home_team"],
            "away": g["away_team"],
            "score": f"{g['home_score']}-{g['away_score']}",
            "winner": g["winner"],
            "total": g["total"],
        })

    # Normalize + sort each matchup's games by date desc
    h2h_list = []
    for key, m in matchups.items():
        if m["n_games"] == 0: continue
        m["avg_total"] = round(m["avg_total"] / m["n_games"], 1)
        m["games"].sort(key=lambda g: g["date"], reverse=True)
        h2h_list.append(m)
    # Sort matchups by n_games desc (most-played first)
    h2h_list.sort(key=lambda m: -m["n_games"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport,
        "n_matchups": len(h2h_list),
        "matchups": h2h_list,
    }
    out_path = os.path.join(DATA_DIR, f"h2h_{sport}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, int]:
    results = {}
    for sport in SPORTS:
        try:
            p = compute_h2h(sport)
            results[sport] = p["n_matchups"]
        except Exception as e:
            results[sport] = f"ERROR: {e}"
    return results


if __name__ == "__main__":
    r = run()
    print("H2H matchups per sport:")
    for sport, n in r.items():
        print(f"  {sport:6}: {n} matchups")
