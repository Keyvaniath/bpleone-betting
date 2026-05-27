"""
EdgeStat -- Cross-sport top picks board.

Unified ranked list across all sport-level confluence-score modules.
Pulls LOCK + STRONG picks from each module and normalizes scores so
they're comparable.

Sources:
  - mlb_pitcher_confluence_score (LOCK/STRONG)
  - mlb_batter_confluence_score
  - mlb_team_confluence_score
  - nba_player_confluence_score
  - nhl_goalie_confluence_score
  - nhl_skater_confluence_score

Output: top 30 picks unified across sports + sport-balance breakdown.

Output: data/cross_sport_top_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_top_picks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    sources = [
        ("MLB_PITCHER", "mlb_pitcher_confluence_score.json",
         "rows", "pitcher", "composite_score", 60.0),
        ("MLB_BATTER", "mlb_batter_confluence_score.json",
         "rows", "batter", "composite_score", 8.0),
        ("MLB_TEAM", "mlb_team_confluence_score.json",
         "rows", "team", "composite_score", 12.0),
        ("NBA_PLAYER", "nba_player_confluence_score.json",
         "rows", "player", "composite_score", 5.0),
        ("NHL_GOALIE", "nhl_goalie_confluence_score.json",
         "rows", "goalie", "composite_score", 8.0),
        ("NHL_SKATER", "nhl_skater_confluence_score.json",
         "rows", "skater", "composite_score", 8.0),
    ]

    all_picks: List[Dict[str, Any]] = []

    for source_id, fname, list_key, name_field, score_field, norm in sources:
        data = _load(os.path.join(DATA_DIR, fname))
        for r in (data.get(list_key) or []):
            if not isinstance(r, dict): continue
            tier = r.get("tier") or ""
            if "LOCK" not in tier and "STRONG" not in tier: continue
            raw_score = r.get(score_field, 0) or 0
            # Normalize to 0-100 range per source
            norm_score = (raw_score / norm) * 50 if norm else raw_score
            all_picks.append({
                "source": source_id,
                "subject": r.get(name_field) or "?",
                "team": r.get("team"),
                "matchup": r.get("matchup"),
                "tier": tier,
                "raw_score": raw_score,
                "normalized_score": round(norm_score, 2),
                "lock_or_strong_bonus": 10 if "LOCK" in tier else 5,
                "final_score": round(norm_score + (10 if "LOCK" in tier else 5), 2),
            })

    all_picks.sort(key=lambda p: -p["final_score"])
    top_30 = all_picks[:30]

    by_source: Dict[str, int] = {}
    for p in all_picks:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total_picks": len(all_picks),
        "n_lock_total": sum(1 for p in all_picks if "LOCK" in (p["tier"] or "")),
        "n_strong_total": sum(1 for p in all_picks if "STRONG" in (p["tier"] or "")),
        "by_source": by_source,
        "method_note": "Cross-sport unified top picks. Pulls LOCK+STRONG from each "
                       "sport-level confluence-score module, normalizes raw scores "
                       "per source (different scales), adds tier bonus (LOCK=+10, "
                       "STRONG=+5). Sorted by final_score descending.",
        "top_30": top_30,
        "all_picks": all_picks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[cross-sport-top] {o['n_total_picks']} picks "
          f"({o['n_lock_total']} LOCK, {o['n_strong_total']} STRONG) "
          f"by source: {o['by_source']} -> {OUT}")
