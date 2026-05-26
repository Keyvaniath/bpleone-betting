"""
EdgeStat -- MLB Top 3 Picks of the Day synthesizer.

Aggregates the HIGHEST-conviction signals from every synthesis module into
a single ranked top-3 daily picks list:

  - Today's Whales (4+ signal players)
  - Confluence Triples (3+ signal players)
  - Pitcher Play of the Day (composite >= 0.5)
  - Batter Play of the Day (composite >= 0.5)
  - Lean Consensus STRONG signals (4+ agreeing leans)

Each candidate scored by:
  - Number of supporting signals
  - Average confidence (probability or composite score)
  - Source weights (whales=1.5, confluence=1.2, PoD=1.0, lean_consensus=0.9)

Outputs the day's top 3 across all categories as the FINAL "what to bet"
shortlist.

Output: data/mlb_top_3_picks.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_top_3_picks.json")


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
    whales = _load(os.path.join(DATA_DIR, "mlb_today_whales.json"))
    scanner = _load(os.path.join(DATA_DIR, "cross_sport_alpha_scanner.json"))
    pitcher_top = _load(os.path.join(DATA_DIR, "mlb_today_top_pitcher_props.json"))
    batter_top = _load(os.path.join(DATA_DIR, "mlb_today_top_batter_props.json"))
    lean = _load(os.path.join(DATA_DIR, "mlb_today_lean_consensus.json"))

    candidates: List[Dict[str, Any]] = []

    # 1) Whales (highest priority)
    for w in (whales.get("whales") or [])[:5]:
        n_sigs = w.get("n_signals", 0)
        avg_p = _safe(w.get("avg_probability"))
        score = (n_sigs * 1.5) * (1 + avg_p)  # weight signals * confidence
        candidates.append({
            "player": w.get("player"),
            "matchup": w.get("matchup"),
            "category": "WHALE",
            "direction": w.get("primary_direction"),
            "n_signals": n_sigs,
            "avg_probability": avg_p,
            "composite_score": round(score, 3),
            "source_weight": 1.5,
        })

    # 2) Confluence triples (3+ signals, not already in whales)
    whale_players = {w["player"] for w in candidates}
    for c in (scanner.get("confluence_triples") or [])[:8]:
        if c.get("player") in whale_players: continue
        n_sigs = c.get("n_signals", 0)
        if n_sigs < 3: continue
        signals = c.get("signals") or []
        avg_p = sum(_safe(s.get("p")) for s in signals) / max(len(signals), 1)
        score = (n_sigs * 1.2) * (1 + avg_p)
        candidates.append({
            "player": c.get("player"),
            "matchup": c.get("matchup"),
            "category": "CONFLUENCE",
            "direction": None,
            "n_signals": n_sigs,
            "avg_probability": round(avg_p, 3),
            "composite_score": round(score, 3),
            "source_weight": 1.2,
        })

    # 3) PoDs
    bpod = batter_top.get("BATTER_PLAY_OF_THE_DAY") or {}
    if bpod.get("batter") and _safe(bpod.get("composite_score")) >= 0.5:
        candidates.append({
            "player": bpod["batter"],
            "matchup": (bpod.get("edges") or [{}])[0].get("matchup", ""),
            "category": "BATTER_POD",
            "direction": bpod.get("net_direction"),
            "n_signals": bpod.get("n_strong_edges", 0),
            "avg_probability": None,
            "composite_score": _safe(bpod.get("composite_score")),
            "source_weight": 1.0,
        })

    ppod = pitcher_top.get("PITCHER_PLAY_OF_THE_DAY") or {}
    if ppod.get("pitcher") and _safe(ppod.get("composite_score")) >= 0.5:
        candidates.append({
            "player": ppod["pitcher"],
            "matchup": "",
            "category": "PITCHER_POD",
            "direction": ppod.get("net_direction"),
            "n_signals": ppod.get("n_strong_edges", 0),
            "avg_probability": None,
            "composite_score": _safe(ppod.get("composite_score")),
            "source_weight": 1.0,
        })

    # Rank by composite_score desc
    candidates.sort(key=lambda c: -c["composite_score"])
    top_3 = candidates[:3]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_candidates_considered": len(candidates),
        "top_3_picks": top_3,
        "all_candidates": candidates[:10],
        "method_note": "Top-3 daily synthesis combining WHALES (4+ signals * 1.5), "
                       "CONFLUENCE (3+ * 1.2), BATTER_POD + PITCHER_POD (composite >= "
                       "0.5 * 1.0). Composite = (n_signals * weight) * (1 + avg_p).",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[top-3] {o['n_candidates_considered']} candidates -> top-3:")
    for i, p in enumerate(o['top_3_picks'], 1):
        print(f"  {i}. {p['player']:25s} [{p['category']:12s}] "
              f"score={p['composite_score']:.2f} ({p['n_signals']} signals)")
