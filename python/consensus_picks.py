"""
EdgeStat -- CONSENSUS picks detector.

When multiple INDEPENDENT modules all flag the same batter as boost / fade
for the same market, that's stronger signal than any one module alone.
Different models converging on the same answer = lower variance / higher
confidence.

Sources scanned:
   mlb_batter_logs         -- raw last-14-game probability
   mlb_batter_sp_edges     -- xwOBA arsenal + career-vs-pitcher
   mlb_batter_situational  -- home/away + day/night splits
   mlb_batter_lvr          -- vsL / vsR season splits

For each (batter, market) pair we check how many sources boost adj_p
above their base by >=3 pp, and how many sources fade by >=3 pp.

Consensus tier:
   ELITE     >= 4 sources agree
   STRONG    >= 3 sources agree
   GOOD      >= 2 sources agree
   weak      < 2 (filtered out)

Output: data/consensus_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "consensus_picks.json")

MIN_DELTA_PP = 3.0   # require 3+ percentage-point move for a "vote"


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _key(batter, market):
    return f"{(batter or '').strip()}|{market}"


def run() -> Dict[str, Any]:
    # Each source produces (batter, market_family) records.
    # We register hit / hr boosts and fades by source.

    sp_edges = _load(os.path.join(DATA_DIR, "mlb_batter_sp_edges.json"))
    sit = _load(os.path.join(DATA_DIR, "mlb_batter_situational_splits.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))

    # For each batter, accumulate votes
    # Dict[batter_market_key, dict with hit_boost_sources, hit_fade_sources, hr_boost_sources, ...]
    votes: Dict[str, Dict[str, Any]] = {}

    def _record(batter, market, source, hit_delta, hr_delta, **extra):
        if not batter or not market: return
        k = _key(batter, market)
        v = votes.setdefault(k, {
            "batter": batter,
            "market": market,
            "hit_boost_sources": [],
            "hit_fade_sources": [],
            "hr_boost_sources": [],
            "hr_fade_sources": [],
            "details": [],
        })
        if hit_delta is not None and hit_delta >= MIN_DELTA_PP:
            v["hit_boost_sources"].append(source)
        elif hit_delta is not None and hit_delta <= -MIN_DELTA_PP:
            v["hit_fade_sources"].append(source)
        if hr_delta is not None and hr_delta >= MIN_DELTA_PP:
            v["hr_boost_sources"].append(source)
        elif hr_delta is not None and hr_delta <= -MIN_DELTA_PP:
            v["hr_fade_sources"].append(source)
        v["details"].append({"source": source, "hit_delta": hit_delta, "hr_delta": hr_delta, **extra})

    # Source 1: mlb_batter_sp_edges
    for g in (sp_edges.get("games") or []):
        for b in (g.get("batters") or []):
            _record(b.get("batter"), "1_plus_hit", "sp_edges",
                    b.get("hit_delta_pp"), b.get("hr_delta_pp"),
                    opp_pitcher=b.get("opp_pitcher"),
                    xwoba_delta=b.get("delta_vs_league_xwoba"))

    # Source 2: mlb_batter_situational_splits
    for b in (sit.get("all_batters") or []):
        _record(b.get("batter"), "1_plus_hit", "situational",
                b.get("hit_delta_pp"), b.get("hr_delta_pp"),
                home=b.get("is_home_today"), night=b.get("is_night_today"))

    # Source 3: mlb_batter_lvr_splits
    for b in (lvr.get("all_batters") or []):
        _record(b.get("batter"), "1_plus_hit", "lvr_splits",
                b.get("hit_delta_pp"), b.get("hr_delta_pp"),
                opp_hand=b.get("opp_hand"), split_ops=b.get("split_ops"),
                split_pa=b.get("split_pa"))

    # Classify consensus
    consensus_hit_boost: List[Dict[str, Any]] = []
    consensus_hit_fade: List[Dict[str, Any]] = []
    consensus_hr_boost: List[Dict[str, Any]] = []

    for k, v in votes.items():
        n_hit_boost = len(v["hit_boost_sources"])
        n_hit_fade = len(v["hit_fade_sources"])
        n_hr_boost = len(v["hr_boost_sources"])

        if n_hit_boost >= 2:
            tier = "ELITE" if n_hit_boost >= 4 else ("STRONG" if n_hit_boost >= 3 else "GOOD")
            consensus_hit_boost.append({**v, "tier": tier, "n_agreeing": n_hit_boost})
        if n_hit_fade >= 2:
            tier = "ELITE" if n_hit_fade >= 4 else ("STRONG" if n_hit_fade >= 3 else "GOOD")
            consensus_hit_fade.append({**v, "tier": tier, "n_agreeing": n_hit_fade})
        if n_hr_boost >= 2:
            tier = "ELITE" if n_hr_boost >= 4 else ("STRONG" if n_hr_boost >= 3 else "GOOD")
            consensus_hr_boost.append({**v, "tier": tier, "n_agreeing": n_hr_boost})

    # Rank by n_agreeing then by sum of deltas
    def _rank(v, key):
        deltas = [d.get(key) or 0 for d in v["details"] if d.get(key) is not None]
        return (v["n_agreeing"], sum(deltas) if deltas else 0)
    consensus_hit_boost.sort(key=lambda v: -_rank(v, "hit_delta")[0]*1000 - _rank(v, "hit_delta")[1])
    consensus_hit_fade.sort(key=lambda v: -_rank(v, "hit_delta")[0]*1000 + _rank(v, "hit_delta")[1])
    consensus_hr_boost.sort(key=lambda v: -_rank(v, "hr_delta")[0]*1000 - _rank(v, "hr_delta")[1])

    # Tier counts
    def _count_tiers(items):
        from collections import Counter
        return dict(Counter(x["tier"] for x in items))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "min_delta_pp": MIN_DELTA_PP,
        "n_unique_batters": len(votes),
        "n_hit_boost_consensus": len(consensus_hit_boost),
        "n_hit_fade_consensus": len(consensus_hit_fade),
        "n_hr_boost_consensus": len(consensus_hr_boost),
        "hit_boost_tiers": _count_tiers(consensus_hit_boost),
        "hit_fade_tiers": _count_tiers(consensus_hit_fade),
        "hr_boost_tiers": _count_tiers(consensus_hr_boost),
        "top_15_hit_boost_consensus": consensus_hit_boost[:15],
        "top_10_hit_fade_consensus": consensus_hit_fade[:10],
        "top_15_hr_boost_consensus": consensus_hr_boost[:15],
        "note": ("Consensus picks: a single module flagging a batter is "
                  "informative but variable. When 3+ INDEPENDENT modules "
                  "(different signal sources -- xwOBA arsenal, home/away, "
                  "vsL/vsR) all flag the same direction, the signal "
                  "compounds and variance drops."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Consensus picks: {p['n_unique_batters']} unique batters across sources")
    print(f"  Hit boost consensus (>=2 sources agree): {p['n_hit_boost_consensus']} ({p['hit_boost_tiers']})")
    print(f"  Hit fade consensus: {p['n_hit_fade_consensus']} ({p['hit_fade_tiers']})")
    print(f"  HR boost consensus: {p['n_hr_boost_consensus']} ({p['hr_boost_tiers']})")
    print(f"\n  Top 8 hit-boost consensus picks:")
    for x in p["top_15_hit_boost_consensus"][:8]:
        srcs = ", ".join(x["hit_boost_sources"])
        print(f"    [{x['tier']:6s}] {x['batter'][:24]:24s}  ({x['n_agreeing']}/3) -- {srcs}")
    print(f"\n  Top 5 HR-boost consensus picks:")
    for x in p["top_15_hr_boost_consensus"][:5]:
        srcs = ", ".join(x["hr_boost_sources"])
        print(f"    [{x['tier']:6s}] {x['batter'][:24]:24s}  ({x['n_agreeing']}/3) -- {srcs}")
