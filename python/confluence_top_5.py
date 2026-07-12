"""
EdgeStat -- Top 5 confluence picks across all modules.

THIS is the daily action list. Surfaces picks where multiple independent
modules agree on the same player + market direction.

How it works:
  1. Read all_picks_ledger.json (current cycle picks)
  2. Group by (player_or_matchup, market_family) -- different sources
     should agree on the underlying play
  3. Score each cluster by:
     - Number of agreeing sources (each adds confidence)
     - Avg probability
     - Source A-grade weighting (from learning_integrity)
  4. Return the top 5 by confluence score

Output: data/confluence_top_5.json

This complements whale_picks.py (which is per-pick confluence). This one is
the OVERALL DAILY ACTION LIST.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional
from collections import defaultdict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "confluence_top_5.json")

# Grade multipliers (B and A grades get boosted weight)
GRADE_MULT = {"A": 1.5, "B": 1.2, "C": 1.0, "D": 0.6, "F": 0.3, None: 1.0}


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


def _market_family(market: str) -> str:
    """Normalize markets so similar picks cluster together.
    e.g. '1_plus_hit', '1_plus_HR', '2_plus_hits' -> different families.
    But 'PP_batter_hits_over_1.5' and '1_plus_hit' = same family."""
    if not market: return "unknown"
    m = str(market).lower()
    if "hit" in m and "no" not in m: return "hits"
    if "hr" in m or "home_run" in m: return "homer"
    if "rbi" in m: return "rbi"
    if "tb" in m or "total_base" in m: return "total_bases"
    if "hrr" in m: return "hrr"
    if "k" in m and ("over" in m or "strike" in m): return "strikeouts"
    if "walk" in m or "bb" in m: return "walks"
    if "er" in m or "earned_run" in m: return "er"
    if "under" in m and ("game" in m.lower() or len(m) <= 12): return "game_under"
    if "over" in m and ("game" in m.lower() or len(m) <= 12): return "game_over"
    if "ml" in m: return "moneyline"
    if "pts" in m or "points" in m: return "points"
    if "ast" in m or "assist" in m: return "assists"
    if "reb" in m or "rebound" in m: return "rebounds"
    if "3pm" in m or "three" in m: return "threes"
    if "block" in m: return "blocks"
    if "steal" in m: return "steals"
    if "sog" in m or "shot" in m: return "shots"
    if "goal" in m: return "goal"
    return m[:20]


def _load_grades() -> Dict[str, str]:
    """Map source -> grade from learning_integrity.json."""
    li = _load(os.path.join(DATA_DIR, "learning_integrity.json"))
    return {r.get("source"): r.get("grade") for r in (li.get("rows") or [])}


def run() -> Dict[str, Any]:
    ledger = _load(os.path.join(DATA_DIR, "all_picks_ledger.json"))
    picks = ledger.get("picks") or []
    if not picks and isinstance(ledger.get("by_pick_id"), dict):
        picks = list(ledger["by_pick_id"].values())

    grades = _load_grades()

    # Group by (player, market_family) — only consider PENDING picks (current day)
    today_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
    clusters = defaultdict(list)
    for p in picks:
        if p.get("voided") or (p.get("result") or "pending").lower() not in ("pending", ""): continue
        if p.get("date") and p["date"] != today_str: continue
        key = (
            (p.get("player_or_matchup") or "").lower().strip(),
            _market_family(p.get("market") or ""),
        )
        if not key[0]: continue
        clusters[key].append(p)

    # Score clusters
    scored = []
    for (player, family), members in clusters.items():
        if len(members) < 2: continue   # confluence needs >= 2 sources
        sources = [m.get("source") for m in members if m.get("source")]
        unique_sources = set(sources)
        probs = [_safe(m.get("prob"), 0) for m in members if m.get("prob")]
        avg_prob = sum(probs) / len(probs) if probs else 0
        # Grade-weighted confluence score
        grade_weight_sum = sum(GRADE_MULT.get(grades.get(s), 1.0) for s in unique_sources)
        confluence_score = len(unique_sources) * grade_weight_sum * (0.5 + avg_prob)

        sample = members[0]
        scored.append({
            "player_or_matchup": sample.get("player_or_matchup"),
            "market_family": family,
            "sport": sample.get("sport"),
            "n_sources": len(unique_sources),
            "sources": sorted(unique_sources),
            "source_grades": [grades.get(s) or "F" for s in sorted(unique_sources)],
            "avg_prob": round(avg_prob, 3) if avg_prob else None,
            "confluence_score": round(confluence_score, 2),
            "tier": ("WHALE" if confluence_score >= 6
                     else "STRONG" if confluence_score >= 4
                     else "STANDARD"),
            "sample_pick": {
                "market": sample.get("market"),
                "fair_american": sample.get("fair_american"),
                "matchup": sample.get("matchup") or sample.get("player_or_matchup"),
            },
        })

    scored.sort(key=lambda r: -r["confluence_score"])
    top_5 = scored[:5]
    top_15 = scored[:15]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_clusters": len(scored),
        "n_top_5_whales": sum(1 for r in top_5 if r["tier"] == "WHALE"),
        "n_top_5_strong": sum(1 for r in top_5 if r["tier"] == "STRONG"),
        "grade_mult": GRADE_MULT,
        "method_note": "Confluence = unique_sources × grade_weight_sum × (0.5 + avg_prob). "
                       "WHALE>=6, STRONG>=4, STANDARD>=2. Only pending picks for today.",
        "top_5": top_5,
        "top_15": top_15,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[confluence-5] {o['n_clusters']} clusters | top-5 WHALES: {o['n_top_5_whales']} -> {OUT}")
