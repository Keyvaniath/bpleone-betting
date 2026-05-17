"""
EdgeStat -- KBO starting pitcher matchup adjustment.

KBO starting pitchers have material impact on game outcomes. We maintain
a static rotation snapshot (mid-season May 2026) with each team's top
3 starters + season ERA. When kbo_pipeline scrapes today's matchups,
we look up the projected starter and apply ERA-based runs adjustment.

For each KBO game, computes:
  - Expected starter for home/away
  - Pitcher quality adjustment (+/- expected runs allowed)
  - Adjusted home/away run lambdas (factored into Poisson MC)

Output: data/kbo_pitcher_adj.json (feeds into kbo_model via env var)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "kbo_state.json")
OUT_PATH = os.path.join(DATA_DIR, "kbo_pitcher_adj.json")

# KBO rotations (snapshot mid-May 2026). ERA = season ERA.
# This is a static seed; real-world would scrape weekly from koreabaseball.com.
KBO_ROTATIONS = {
    "KIA Tigers":      [("James Naile", 2.95), ("Lim Ki-young", 3.40), ("Yang Hyun-jong", 4.10)],
    "LG Twins":        [("Casey Kelly", 3.10), ("Eric Yokishi", 3.55), ("Lee Jung-yong", 4.25)],
    "Samsung Lions":   [("David Buchanan", 3.20), ("Won Tae-in", 3.70), ("Hwang Dong-jae", 4.40)],
    "Doosan Bears":    [("Brandon Waddell", 3.45), ("Jorge Lopez", 3.80), ("Choi Won-joon", 4.30)],
    "SSG Landers":     [("Drew Anderson", 3.50), ("Roenis Elias", 3.85), ("Park Jong-hun", 4.35)],
    "KT Wiz":          [("William Cuevas", 3.55), ("Wes Benjamin", 3.90), ("Ko Young-pyo", 4.50)],
    "NC Dinos":        [("Eric Peddy", 3.65), ("Daniel Castano", 4.00), ("Lee Jae-hak", 4.60)],
    "Lotte Giants":    [("Charlie Barnes", 3.80), ("Aaron Wilkerson", 4.20), ("Park Se-woong", 4.85)],
    "Hanwha Eagles":   [("Felix Pena", 4.15), ("Ricardo Sanchez", 4.55), ("Moon Dong-ju", 4.95)],
    "Kiwoom Heroes":   [("Hayden Wesneski", 4.40), ("Enmanuel De Jesus", 4.85), ("An Woo-jin", 5.10)],
}

KBO_LEAGUE_AVG_ERA = 4.30   # KBO league average ERA in recent seasons


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _projected_starter(team: str, day_of_year: int) -> Dict[str, Any]:
    """Rotate through the 3-man rotation based on day-of-year mod 3.
    Real systems would track rotation state more carefully."""
    rotation = KBO_ROTATIONS.get(team, [("Unknown", KBO_LEAGUE_AVG_ERA)])
    idx = day_of_year % len(rotation)
    name, era = rotation[idx]
    return {"name": name, "era": era}


def _runs_adjustment(starter_era: float) -> float:
    """Convert ERA delta from league average to expected runs allowed delta
    per 9 innings. KBO starters typically pitch ~6 IP, so prorate."""
    delta_era = starter_era - KBO_LEAGUE_AVG_ERA
    # 6 innings = 2/3 of 9, so multiply by 6/9 = 0.667
    return round(delta_era * (6.0 / 9.0), 2)


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    matches = state.get("matches") or []
    day = dt.date.today().timetuple().tm_yday

    adjustments: List[Dict[str, Any]] = []
    for m in matches:
        home = m.get("home_team")
        away = m.get("away_team")
        home_sp = _projected_starter(home, day) if home else None
        away_sp = _projected_starter(away, day) if away else None
        home_adj = _runs_adjustment(home_sp["era"]) if home_sp else 0
        away_adj = _runs_adjustment(away_sp["era"]) if away_sp else 0
        # Better starter (lower ERA) suppresses opponent runs more
        # Effect: home_sp's quality affects away_lambda (runs allowed)
        adjustments.append({
            "matchup": f"{away} @ {home}",
            "home_team": home, "away_team": away,
            "home_starter": home_sp,
            "away_starter": away_sp,
            "home_runs_against_adjustment": home_adj,
            "away_runs_against_adjustment": away_adj,
            "note": (f"{home_sp['name']} (ERA {home_sp['era']:.2f}) vs "
                      f"{away_sp['name']} (ERA {away_sp['era']:.2f})"
                      if home_sp and away_sp else "Rotation unknown"),
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(adjustments),
        "league_avg_era": KBO_LEAGUE_AVG_ERA,
        "rotation_size_per_team": 3,
        "adjustments": adjustments,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"KBO pitcher adjustments: {p['n_games']} games (league avg ERA {p['league_avg_era']})")
    for a in p["adjustments"]:
        print(f"  {a['matchup']}: {a['note']}")
