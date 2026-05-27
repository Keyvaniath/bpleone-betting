"""
EdgeStat -- Sport-by-sport breakdown.

Per-sport summary stats from confluence scores. For each sport:
  - Total LOCKs / STRONGs / FADEs
  - Top entity by composite score
  - Number of LOCK + STRONG picks
  - Sport slate strength tier

Output: data/sport_by_sport_breakdown.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "sport_by_sport_breakdown.json")


SPORT_SOURCES = [
    ("MLB", "mlb_pitcher_confluence_score.json", "pitcher"),
    ("MLB", "mlb_batter_confluence_score.json", "batter"),
    ("MLB", "mlb_team_confluence_score.json", "team"),
    ("NBA", "nba_player_confluence_score.json", "player"),
    ("NBA", "nba_team_confluence_score.json", "team"),
    ("NHL", "nhl_goalie_confluence_score.json", "goalie"),
    ("NHL", "nhl_skater_confluence_score.json", "skater"),
    ("NHL", "nhl_team_confluence_score.json", "team"),
    ("WNBA", "wnba_player_confluence_score.json", "player"),
    ("SOCCER", "soccer_match_confluence_score.json", "match"),
    ("TENNIS", "tennis_player_confluence_score.json", "player"),
    ("UFC", "ufc_fighter_confluence_score.json", "fighter"),
    ("GOLF", "golf_player_confluence_score.json", "player"),
    ("F1", "f1_driver_confluence_score.json", "driver"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    by_sport: Dict[str, Dict[str, Any]] = {}

    for sport, fname, subject_field in SPORT_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        n_lock = int(data.get("n_lock", 0) or 0)
        n_strong = int(data.get("n_strong", 0) or 0)
        n_fade = int(data.get("n_fade", 0) or 0)

        top_entity = None
        top_score = 0
        for r in (data.get("rows") or []):
            if not isinstance(r, dict): continue
            s = _safe(r.get("composite_score"))
            if s > top_score:
                top_score = s
                top_entity = r.get(subject_field)

        bucket = by_sport.setdefault(sport, {
            "n_lock": 0, "n_strong": 0, "n_fade": 0,
            "n_modules": 0, "top_entity": None, "top_score": 0,
        })
        bucket["n_lock"] += n_lock
        bucket["n_strong"] += n_strong
        bucket["n_fade"] += n_fade
        bucket["n_modules"] += 1
        if top_score > bucket["top_score"]:
            bucket["top_score"] = top_score
            bucket["top_entity"] = top_entity

    # Compute slate strength tier per sport
    for sport, b in by_sport.items():
        score = b["n_lock"] * 10 + b["n_strong"] * 4 - b["n_fade"]
        b["slate_score"] = score
        if score >= 30:
            b["tier"] = "ELITE"
        elif score >= 15:
            b["tier"] = "STRONG"
        elif score >= 5:
            b["tier"] = "MODEST"
        else:
            b["tier"] = "LIGHT"
        b["top_score"] = round(b["top_score"], 2)

    sports_sorted = sorted(by_sport.items(), key=lambda x: -x[1]["slate_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_sports": len(by_sport),
        "sports_ranked_by_slate_strength": [
            {"sport": s, **b} for s, b in sports_sorted
        ],
        "method_note": "Per-sport breakdown. slate_score = n_lock*10 + n_strong*4 "
                       "- n_fade. ELITE >=30, STRONG >=15, MODEST >=5, LIGHT <5. "
                       "Surfaces top entity per sport for quick reference.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[sport-breakdown] {o['n_sports']} sports breakdown -> {OUT}")
