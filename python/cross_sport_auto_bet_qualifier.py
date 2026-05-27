"""
EdgeStat -- Cross-sport auto-bet qualifier.

Picks meeting STRICT bet-it-blind criteria for autonomous wagering:
  1. LOCK tier from sport-level confluence_score
  2. No FADE conflict in opposing module (e.g. MLB pitcher LOCK but team
     FADE -- conflict)
  3. Highest tier from cross_sport_top_picks (or LOCK tier from any
     confluence_score)
  4. Listed in tonight_top_5_curated (validated curated top)
  5. NOT in daily_fade_board

When all 4 criteria align, the pick is "auto-bet" tier: high enough
conviction that a script could place it without further review.

Output: data/cross_sport_auto_bet_qualifier.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_auto_bet_qualifier.json")


CONFLUENCE_SOURCES = [
    "mlb_pitcher_confluence_score.json",
    "mlb_batter_confluence_score.json",
    "mlb_team_confluence_score.json",
    "nba_player_confluence_score.json",
    "nba_team_confluence_score.json",
    "nhl_goalie_confluence_score.json",
    "nhl_skater_confluence_score.json",
    "nhl_team_confluence_score.json",
    "wnba_player_confluence_score.json",
    "soccer_match_confluence_score.json",
    "tennis_player_confluence_score.json",
    "ufc_fighter_confluence_score.json",
    "golf_player_confluence_score.json",
    "f1_driver_confluence_score.json",
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    fade_board = _load(os.path.join(DATA_DIR, "daily_fade_board.json"))
    top_5 = _load(os.path.join(DATA_DIR, "tonight_top_5_curated.json"))

    # Build fade set
    fade_subjects: set = set()
    for f in (fade_board.get("fades") or []):
        if isinstance(f, dict):
            fade_subjects.add(_norm(f.get("subject") or ""))

    # Top 5 subjects
    top_5_subjects: set = set()
    for p in (top_5.get("top_5_picks") or []):
        if isinstance(p, dict):
            top_5_subjects.add(_norm(p.get("subject") or ""))

    auto_bets: List[Dict[str, Any]] = []
    near_misses: List[Dict[str, Any]] = []

    for fname in CONFLUENCE_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for r in (data.get("rows") or []):
            if not isinstance(r, dict): continue
            tier = r.get("tier") or ""
            if "LOCK" not in tier: continue

            # Identify subject by sport
            subject = (r.get("pitcher") or r.get("batter") or r.get("player")
                       or r.get("goalie") or r.get("skater") or r.get("fighter")
                       or r.get("driver") or r.get("team") or r.get("match")
                       or "?")
            norm_subj = _norm(subject)

            # Apply gates
            in_fade = norm_subj in fade_subjects
            in_top_5 = norm_subj in top_5_subjects

            pick = {
                "subject": subject,
                "source_module": fname.replace("_confluence_score.json", ""),
                "tier": tier,
                "composite_score": r.get("composite_score"),
                "matchup": r.get("matchup") or r.get("match") or r.get("fight")
                           or r.get("race") or r.get("tournament"),
                "in_fade_board": in_fade,
                "in_top_5_curated": in_top_5,
            }

            if not in_fade and in_top_5:
                pick["qualification"] = "AUTO_BET"
                auto_bets.append(pick)
            elif not in_fade:
                pick["qualification"] = "NEAR_MISS_NOT_TOP_5"
                near_misses.append(pick)
            else:
                pick["qualification"] = "FADE_CONFLICT"
                near_misses.append(pick)

    auto_bets.sort(key=lambda b: -(b.get("composite_score") or 0))
    near_misses.sort(key=lambda b: -(b.get("composite_score") or 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_auto_bets": len(auto_bets),
        "n_near_misses": len(near_misses),
        "method_note": "Strict auto-bet criteria: LOCK tier from confluence_score "
                       "AND in tonight_top_5_curated AND NOT in daily_fade_board. "
                       "Near misses = LOCK tier but missing one criterion.",
        "auto_bets": auto_bets,
        "near_misses": near_misses[:10],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[auto-bet] {o['n_auto_bets']} qualified auto-bets, "
          f"{o['n_near_misses']} near misses -> {OUT}")
