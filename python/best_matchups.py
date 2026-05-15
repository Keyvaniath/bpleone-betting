"""
EdgeStat -- Best matchups tonight.

For each batter in every confirmed lineup, rank them by their projected
xwOBA against tonight's opposing starting pitcher. The leverage comes from
the batter-vs-pitch-type Statcast data: a batter who crushes fastballs
facing a fastball-heavy pitcher is leverage; a great hitter facing a
slider-specialist whose slider is elite is a fade spot.

Best matchups (highest matchup_xwoba) are leverage for:
  - OVER total bases / hits / HR props
  - Hitter Fantasy Score on PrizePicks
  - OVER game totals if BOTH lineups are high-leverage

Worst matchups (lowest matchup_xwoba) are leverage for:
  - UNDER the batter's prop lines
  - Pitcher K props (these batters whiff vs this arsenal)
  - UNDER game total

Writes data/best_matchups.json sorted by leverage.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "best_matchups.json")
LEAGUE_XWOBA = 0.320


def build_all() -> Dict[str, Any]:
    matchups_path = os.path.join(DATA_DIR, "matchups.json")
    if not os.path.exists(matchups_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "matchups.json missing", "matchups": []}
    with open(matchups_path) as f:
        m = json.load(f)
    rows = []
    for g in m.get("games", []):
        L = g.get("lineups") or {}
        for side, opp_pitcher_key in (("home", "away_pitcher"), ("away", "home_pitcher")):
            opp_p = (g.get(opp_pitcher_key) or {})
            opp_name = opp_p.get("name") or "TBD"
            for b in (L.get(side) or []):
                mu = b.get("vs_pitcher_xwoba_matchup") or {}
                if not mu.get("matchup_xwoba"):
                    continue
                rows.append({
                    "matchup": g.get("matchup"),
                    "time": g.get("time"),
                    "side": side,
                    "order": b.get("order"),
                    "batter": b.get("name"),
                    "batter_id": b.get("id"),
                    "vs_pitcher": opp_name,
                    "matchup_xwoba": mu["matchup_xwoba"],
                    "delta_vs_league": mu.get("delta_vs_league"),
                    "leverage": ("leverage" if mu["matchup_xwoba"] >= 0.380
                                  else "fade" if mu["matchup_xwoba"] <= 0.270
                                  else "neutral"),
                    "h2h": b.get("vs_pitcher_career") or {},
                })
    rows.sort(key=lambda r: -r["matchup_xwoba"])
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "league_xwoba_baseline": LEAGUE_XWOBA,
        "total": len(rows),
        "leverage_count": sum(1 for r in rows if r["leverage"] == "leverage"),
        "fade_count": sum(1 for r in rows if r["leverage"] == "fade"),
        "matchups": rows,
    }


def write_best(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote best_matchups -> {path}")
    print(f"  Batter matchups scored: {payload.get('total', 0)}")
    print(f"  Leverage spots (xwOBA >= .380): {payload.get('leverage_count', 0)}")
    print(f"  Fade spots (xwOBA <= .270): {payload.get('fade_count', 0)}")
    for r in payload.get("matchups", [])[:5]:
        print(f"  {r['batter']:25} vs {r['vs_pitcher']:22} "
              f"matchup xwOBA {r['matchup_xwoba']} ({r['delta_vs_league']:+}) -- {r['leverage']}")


if __name__ == "__main__":
    write_best(build_all())
