"""
EdgeStat -- Daily fade board.

Aggregates all FADE picks across the 14 confluence-score modules into a
single board for UNDER / fade opportunities. Cross-sport view of where
to bet AGAINST tonight.

Output: data/daily_fade_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "daily_fade_board.json")


FADE_SOURCES = [
    ("MLB_PITCHER", "mlb_pitcher_confluence_score.json",
     "fades", "pitcher", "MLB", "K UNDER + outs UNDER + 4+ER YES"),
    ("MLB_BATTER", "mlb_batter_confluence_score.json",
     "fades", "batter", "MLB", "K OVER YES + 0 hits"),
    ("MLB_TEAM", "mlb_team_confluence_score.json",
     "fades", "team", "MLB", "team total UNDER"),
    ("NBA_PLAYER", "nba_player_confluence_score.json",
     "fades", "player", "NBA", "PTS UNDER + PRA UNDER (multi-prop)"),
    ("NBA_TEAM", "nba_team_confluence_score.json",
     "fades", "team", "NBA", "team total UNDER"),
    ("NHL_GOALIE", "nhl_goalie_confluence_score.json",
     "fades", "goalie", "NHL", "saves UNDER + win NO"),
    ("NHL_SKATER", "nhl_skater_confluence_score.json",
     "fades", "skater", "NHL", "SOG UNDER + no goal"),
    ("NHL_TEAM", "nhl_team_confluence_score.json",
     "fades", "team", "NHL", "team total UNDER"),
    ("WNBA_PLAYER", "wnba_player_confluence_score.json",
     "fades", "player", "WNBA", "PTS UNDER"),
    ("SOCCER_MATCH", "soccer_match_confluence_score.json",
     "fades", "match", "SOCCER", "total goals UNDER + BTTS NO"),
    ("TENNIS_PLAYER", "tennis_player_confluence_score.json",
     "fades", "player", "TENNIS", "underdog ML + +set spread"),
    ("UFC_FIGHTER", "ufc_fighter_confluence_score.json",
     "fades", "fighter", "UFC", "opponent ML"),
    ("GOLF_PLAYER", "golf_player_confluence_score.json",
     "fades", "player", "GOLF", "miss cut YES + high round score"),
    ("F1_DRIVER", "f1_driver_confluence_score.json",
     "fades", "driver", "F1", "non-podium / outside top 10"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    fades: List[Dict[str, Any]] = []

    for source_id, fname, list_key, name_field, sport, fade_market in FADE_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for r in (data.get(list_key) or []):
            if not isinstance(r, dict): continue
            fades.append({
                "source": source_id,
                "sport": sport,
                "subject": r.get(name_field) or "?",
                "team": r.get("team"),
                "matchup": r.get("matchup") or r.get("match") or r.get("fight")
                           or r.get("race") or r.get("tournament") or "",
                "tier": r.get("tier"),
                "composite_score": r.get("composite_score"),
                "recommended_fade_market": fade_market,
            })

    # Sort by lowest score first (deepest fades)
    fades.sort(key=lambda f: (f["composite_score"] or 0))

    by_sport: Dict[str, int] = {}
    for f in fades:
        by_sport[f["sport"]] = by_sport.get(f["sport"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fades": len(fades),
        "by_sport": by_sport,
        "method_note": "Cross-sport daily fade board. Aggregates FADE-tier "
                       "picks from all 14 confluence-score modules into single "
                       "UNDER/fade opportunity board. Sorted by lowest composite "
                       "score first (deepest fade).",
        "fades": fades,
        "top_15": fades[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[fade-board] {o['n_fades']} fades by sport: {o['by_sport']} -> {OUT}")
