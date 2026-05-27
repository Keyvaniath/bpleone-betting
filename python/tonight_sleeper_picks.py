"""
EdgeStat -- Tonight's sleeper picks.

Surfaces high-confluence picks that are NOT in tonight_top_5_curated
(low public visibility = sharper edges). Pulls from cross_sport_top_picks
and excludes anything already in top_5 or top_3_fades.

Output: data/tonight_sleeper_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_sleeper_picks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    top_picks = _load(os.path.join(DATA_DIR, "cross_sport_top_picks.json"))
    top_5 = _load(os.path.join(DATA_DIR, "tonight_top_5_curated.json"))
    fade_board = _load(os.path.join(DATA_DIR, "daily_fade_board.json"))

    # Already-curated subjects
    top_5_subjects: set = set()
    for p in (top_5.get("top_5_picks") or []):
        if isinstance(p, dict):
            top_5_subjects.add(_norm(p.get("subject") or ""))

    fade_subjects: set = set()
    for f in (fade_board.get("fades") or []):
        if isinstance(f, dict):
            fade_subjects.add(_norm(f.get("subject") or ""))

    sleepers: List[Dict[str, Any]] = []
    for p in (top_picks.get("all_picks") or top_picks.get("top_30") or []):
        if not isinstance(p, dict): continue
        subj_norm = _norm(p.get("subject") or "")

        # Skip if already curated or in fade board
        if subj_norm in top_5_subjects: continue
        if subj_norm in fade_subjects: continue

        # Only STRONG tier (LOCKs would already be in top_5)
        tier = p.get("tier") or ""
        if "STRONG" not in tier: continue

        source = p.get("source") or ""
        sport = source.split("_")[0] if source else "?"
        sleepers.append({
            "source": source,
            "sport": sport,
            "subject": p.get("subject"),
            "team": p.get("team"),
            "matchup": p.get("matchup"),
            "tier": tier,
            "raw_score": p.get("raw_score"),
            "normalized_score": p.get("normalized_score"),
            "final_score": p.get("final_score"),
        })

    # Sort by final_score descending
    sleepers.sort(key=lambda s: -(s.get("final_score") or 0))

    by_sport: Dict[str, int] = {}
    for s in sleepers:
        by_sport[s["sport"]] = by_sport.get(s["sport"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_sleepers": len(sleepers),
        "by_sport": by_sport,
        "method_note": "Sleeper picks: STRONG tier from cross_sport_top_picks NOT "
                       "already in tonight_top_5_curated or daily_fade_board. "
                       "Lower public visibility -> sharper edges expected.",
        "sleepers": sleepers,
        "top_15": sleepers[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[sleepers] {o['n_sleepers']} sleeper picks by_sport={o['by_sport']} -> {OUT}")
