"""
EdgeStat -- cross-sport CLV (Closing Line Value) tracker.

Compares our model's morning fair-american odds to its updated fair-american
odds closer to game time. Positive CLV = our model has moved TOWARD the
final consensus (we predicted line drift correctly). Used as a sharpness
proxy in the absence of real book closing lines.

State: .clv_open_<sport>.json captures morning open. Compared each cron.

Output: data/clv_multi.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "clv_multi.json")

SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "ncaaf", "ncaab", "cws", "mlb"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f: json.dump(payload, f, indent=2)


def _is_morning() -> bool:
    """If current run is the 10:00 UTC cron, snapshot opens.
    Otherwise compare against existing open."""
    return dt.datetime.now().hour == 10


def _amer_to_implied(amer):
    if amer is None or amer == 0: return 0.5
    if amer > 0: return 100 / (amer + 100)
    return abs(amer) / (abs(amer) + 100)


def run() -> Dict[str, Any]:
    is_morning = _is_morning()
    by_sport: Dict[str, Any] = {}
    today_str = dt.date.today().isoformat()

    for sport in SPORTS:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        games = state.get("games") or []
        opens_path = os.path.join(DATA_DIR, f".clv_open_{sport}.json")
        opens = _load(opens_path) or {}

        if is_morning:
            # Refresh opens
            new_opens = {today_str: {}}
            for g in games:
                if g.get("state") not in ("pre", None): continue
                key = g.get("id") or f"{g.get('away_team')}@{g.get('home_team')}"
                new_opens[today_str][key] = {
                    "matchup": g.get("matchup"),
                    "p_home_open": g.get("p_home_win"),
                    "fair_home_open": g.get("fair_home_american"),
                    "fair_away_open": g.get("fair_away_american"),
                }
            _save(opens_path, new_opens)
            opens = new_opens

        today_opens = opens.get(today_str, {})
        # Compute current CLV per game
        clv_rows = []
        for g in games:
            if g.get("state") == "post": continue
            key = g.get("id") or f"{g.get('away_team')}@{g.get('home_team')}"
            o = today_opens.get(key)
            if not o: continue
            curr_imp = _amer_to_implied(g.get("fair_home_american"))
            open_imp = _amer_to_implied(o.get("fair_home_open"))
            clv = curr_imp - open_imp
            clv_rows.append({
                "matchup": g.get("matchup"),
                "p_home_open": o.get("p_home_open"),
                "p_home_curr": g.get("p_home_win"),
                "fair_home_open": o.get("fair_home_open"),
                "fair_home_curr": g.get("fair_home_american"),
                "clv_pp": round(clv * 100, 2),
                "state": g.get("state"),
            })
        # Average CLV across sport (when our morning open had value, did current shift toward it?)
        avg_clv = round(sum(r["clv_pp"] for r in clv_rows) / max(1, len(clv_rows)), 2)
        by_sport[sport] = {
            "n_games": len(clv_rows),
            "avg_clv_pp": avg_clv,
            "rows": clv_rows[:20],
        }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "is_morning_snapshot": is_morning,
        "by_sport": by_sport,
    }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"CLV multi (morning_snapshot={p['is_morning_snapshot']}):")
    for sport, info in p["by_sport"].items():
        print(f"  {sport:7}: {info['n_games']} games, avg CLV {info['avg_clv_pp']:+.2f}pp")
