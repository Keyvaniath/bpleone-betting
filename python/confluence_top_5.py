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
import sys
import json
import datetime as dt
from typing import Any, Dict, List, Optional
from collections import defaultdict


def _nz(v, d):
    """None-safe default (2026-10-26): `.get(k, d)` only covers a MISSING key;
    a key stored as None still reaches the arithmetic and crashes."""
    return d if v is None else v


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


_DIRS = ("over", "under", "yes", "no", "home", "away", "plus", "minus")


def _market_family(market: str) -> str:
    """(2026-11-03) Parse the STAT token + DIRECTION, so agreement is counted
    only within one market and one direction. The old substring ladder had
    `"er" in m` -> 'er' for every OVER/UNDER (and 'hit' for 'pitcher'), so six
    different props on one player (3PM under, PA under, RA over, REB under ...)
    counted as six "agreeing sources" for one play.
      'PA_UNDER_35.5' -> 'pa|under'   'ML_HOME' -> 'ml|home'
      'HOME_TOTAL_OVER_109.7' -> 'home_total|over'   'BTTS_YES' -> 'btts|yes'"""
    if not market: return "unknown"
    toks = [t for t in str(market).lower().replace("-", "_").split("_") if t]
    for i, t in enumerate(toks):
        if t in ("over", "under", "yes", "no"):
            stat = "_".join(x for x in toks[:i] if not _is_num(x)) or "game"
            return f"{stat}|{t}"
    if len(toks) == 2 and toks[1] == "ml":          # '{TEAM}_ML' -> the team is the side
        return f"ml|{toks[0]}"
    # moneyline / spread style: direction is the side token
    for i, t in enumerate(toks):
        if t in ("home", "away"):
            rest = "_".join(x for x in toks[:i] + toks[i + 1:] if not _is_num(x)) or "ml"
            return f"{rest}|{t}"
    return "_".join(x for x in toks if not _is_num(x)) + "|?"


def _is_num(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date().isoformat()


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
    try:
        import quotes as Q
    except Exception:
        sys.path.insert(0, os.path.dirname(__file__))
        import quotes as Q

    # (2026-11-03) Group only PENDING picks on TODAY'S ET slate that are still
    # PRE-GAME and carry an ACTIONABLE sportsbook quote right now (quotes.py:
    # DK snapshot, fresh, not started, exact line). The old filter compared the
    # pick date to the UTC run date, so after 7 PM ET it listed games that had
    # already ended; props (no sportsbook price in the free feeds) are excluded.
    today_str = _today_et()
    clusters = defaultdict(list)
    excluded = defaultdict(int)
    for p in picks:
        if p.get("voided") or (p.get("result") or "pending").lower() not in ("pending", ""): continue
        if (p.get("game_date") or p.get("date")) != today_str:
            excluded["not_today_et"] += 1
            continue
        matchup = p.get("matchup") or p.get("player_or_matchup") or ""
        pc = Q.price_candidate(p.get("sport") or "", matchup, p.get("market") or "", p.get("prob"))
        if not pc["actionable"]:
            excluded[pc["reason"] or "not_actionable"] += 1
            continue
        p = dict(p, _quote=pc["quote"], _ev=pc["ev"])
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
        grade_weight_sum = sum(_nz(GRADE_MULT.get(grades.get(s)), 1.0) for s in unique_sources)
        confluence_score = len(unique_sources) * grade_weight_sum * (0.5 + avg_prob)

        sample = members[0]
        q = sample.get("_quote") or {}
        scored.append({
            "player_or_matchup": sample.get("player_or_matchup"),
            "market_family": family,
            "sport": sample.get("sport"),
            "n_sources": len(unique_sources),
            "sources": sorted(unique_sources),
            "source_grades": [grades.get(s) or "F" for s in sorted(unique_sources)],
            "avg_prob": round(avg_prob, 3) if avg_prob else None,
            "confluence_score": round(confluence_score, 2),
            # (2026-11-03) no WHALE/STRONG tiers: agreement count is not a verdict
            "desk_verdict": sample.get("desk_verdict"),
            "sample_pick": {
                "market": sample.get("market"),
                "matchup": sample.get("matchup") or sample.get("player_or_matchup"),
                "game_date": sample.get("game_date") or sample.get("date"),
                "book": q.get("book"), "book_american": q.get("american"),
                "observed_at": q.get("observed_at"), "scheduled_start": q.get("scheduled_start"),
                "ev_at_book": sample.get("_ev"),
            },
        })

    scored.sort(key=lambda r: -r["confluence_score"])
    top_5 = scored[:5]
    top_15 = scored[:15]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_clusters": len(scored),
        "date_et": today_str,
        "excluded": dict(excluded),
        "grade_mult": GRADE_MULT,
        "method_note": "Confluence = unique_sources × grade_weight_sum × (0.5 + avg_prob), counted only "
                       "within one market + direction. Only pending picks on today's ET slate, pre-game, "
                       "with an actionable DraftKings quote (props have no sportsbook price -> excluded).",
        "top_5": top_5,
        "top_15": top_15,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[confluence-5] {o['n_clusters']} clusters ({o['date_et']} ET) | excluded {o['excluded']} -> {OUT}")
