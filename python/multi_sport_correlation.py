"""
EdgeStat -- multi-sport correlation engine.

Identifies multi-sport "regime days" where multiple sports are showing the
same trend (e.g. lots of home favorites covering today across NBA+NHL+MLB
suggests a public-side-light day). Surfaces:

  - Home-favorite vs Road-dog days (avg P(home) across all today's games)
  - Over-heavy vs Under-heavy slates (avg game total vs season norm)
  - Concentration of top edges in 1 sport (multi-leg parlay candidate)

Output: data/multi_sport_correlation.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "multi_sport_correlation.json")

SPORTS = ["nba", "nhl", "wnba", "mls", "epl", "nfl", "ncaaf", "ncaab", "cws", "mlb"]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    today: List[Dict[str, Any]] = []
    sport_summary: Dict[str, Any] = {}

    for sport in SPORTS:
        state = _load(os.path.join(DATA_DIR, f"{sport}_state.json"))
        games = [g for g in (state.get("games") or []) if g.get("state") != "post"]
        if not games:
            continue
        avg_phome = sum(g.get("p_home_win", 0.5) for g in games) / len(games)
        home_fav = sum(1 for g in games if (g.get("p_home_win") or 0.5) >= 0.55)
        home_dog = sum(1 for g in games if (g.get("p_home_win") or 0.5) <= 0.45)
        sport_summary[sport] = {
            "n_games": len(games),
            "avg_phome": round(avg_phome, 3),
            "n_home_favs": home_fav,
            "n_home_dogs": home_dog,
        }
        today.extend([{**g, "sport": sport} for g in games])

    # Cross-sport regime
    if today:
        regime_phome = sum(g.get("p_home_win", 0.5) for g in today) / len(today)
        n_strong_home = sum(1 for g in today if (g.get("p_home_win") or 0.5) >= 0.60)
        n_strong_away = sum(1 for g in today if (g.get("p_home_win") or 0.5) <= 0.40)
    else:
        regime_phome = 0.5
        n_strong_home = 0
        n_strong_away = 0

    # Sport concentration (where are the most strong-favorite picks?)
    sport_concentration = sorted(
        sport_summary.items(),
        key=lambda kv: -(kv[1]["n_home_favs"] + kv[1]["n_home_dogs"])
    )[:3]

    regime = ("HOME_FAVORITE_DAY" if regime_phome >= 0.55 else
              "ROAD_DOG_DAY" if regime_phome <= 0.45 else "BALANCED")

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games_today_total": len(today),
        "regime_avg_phome": round(regime_phome, 3),
        "regime_label": regime,
        "n_strong_home_favs": n_strong_home,
        "n_strong_road_dogs": n_strong_away,
        "by_sport": sport_summary,
        "top_3_concentrated_sports": [{
            "sport": s,
            "n_games": d["n_games"],
            "actionable_picks": d["n_home_favs"] + d["n_home_dogs"],
        } for s, d in sport_concentration],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Multi-sport correlation: regime={p['regime_label']} "
          f"(avg P(home)={p['regime_avg_phome']})")
    print(f"  Strong home favs: {p['n_strong_home_favs']} | strong road dogs: {p['n_strong_road_dogs']}")
    print(f"  Top concentrated sports: {[s['sport'] for s in p['top_3_concentrated_sports']]}")
