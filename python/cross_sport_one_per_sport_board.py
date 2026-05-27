"""
EdgeStat -- Cross-sport "best of best" one-per-sport board.

For each sport, surfaces the single highest-conviction pick by composite
score (across all roles within that sport).

Output: data/cross_sport_one_per_sport_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_one_per_sport_board.json")


# (sport, [(filename, subject_field, ...)])
SPORT_MODULES = {
    "MLB": [
        ("mlb_pitcher_confluence_score.json", "pitcher"),
        ("mlb_batter_confluence_score.json", "batter"),
        ("mlb_team_confluence_score.json", "team"),
    ],
    "NBA": [
        ("nba_player_confluence_score.json", "player"),
        ("nba_team_confluence_score.json", "team"),
    ],
    "NHL": [
        ("nhl_goalie_confluence_score.json", "goalie"),
        ("nhl_skater_confluence_score.json", "skater"),
        ("nhl_team_confluence_score.json", "team"),
    ],
    "WNBA": [
        ("wnba_player_confluence_score.json", "player"),
    ],
    "SOCCER": [
        ("soccer_match_confluence_score.json", "match"),
    ],
    "TENNIS": [
        ("tennis_player_confluence_score.json", "player"),
    ],
    "UFC": [
        ("ufc_fighter_confluence_score.json", "fighter"),
    ],
    "GOLF": [
        ("golf_player_confluence_score.json", "player"),
    ],
    "F1": [
        ("f1_driver_confluence_score.json", "driver"),
    ],
}


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
    best_per_sport: List[Dict[str, Any]] = []

    for sport, modules in SPORT_MODULES.items():
        best_entry = None
        best_score = 0
        best_source = None

        for fname, subject_field in modules:
            data = _load(os.path.join(DATA_DIR, fname))
            for r in (data.get("rows") or []):
                if not isinstance(r, dict): continue
                tier = r.get("tier") or ""
                if "LOCK" not in tier and "STRONG" not in tier: continue
                score = _safe(r.get("composite_score"))
                if score > best_score:
                    best_score = score
                    best_entry = r
                    best_source = fname.replace("_confluence_score.json", "")

        if not best_entry: continue

        subject_field = next(s for f, s in modules if f.replace("_confluence_score.json", "") == best_source)

        best_per_sport.append({
            "sport": sport,
            "source_module": best_source,
            "subject": best_entry.get(subject_field) or "?",
            "team": best_entry.get("team"),
            "matchup": best_entry.get("matchup") or best_entry.get("match") or best_entry.get("fight")
                        or best_entry.get("race") or best_entry.get("tournament"),
            "tier": best_entry.get("tier"),
            "composite_score": round(best_score, 2),
        })

    best_per_sport.sort(key=lambda p: -p["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_sports_with_pick": len(best_per_sport),
        "method_note": "Single best LOCK/STRONG pick per sport by composite "
                       "score. Cross-sport diversified.",
        "best_per_sport": best_per_sport,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[one-per-sport] {o['n_sports_with_pick']} sports with picks -> {OUT}")
