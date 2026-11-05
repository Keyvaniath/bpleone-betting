"""
EdgeStat -- unified Top Calibrated Edges report.

Combines TWO sources of edge into ONE daily action list:

  1. Real book-vs-model edges (book_vs_model_team.json)
     - Uses ACTUAL book decimal odds (live DraftKings game lines via ESPN's
       free feed since 2026-06; the frozen Bovada snapshot is the fallback --
       the old "Bovada" attribution here was stale)
     - calibrated_prob already Bayesian-shrunk toward book
     - calibrated_edge_pct is the honest number

  2. (REMOVED 2026-11-03) player-prop "edges" priced at the model's own fair
     odds -- "Book %" was 1/model fair and EV was vs the model's own price.

Output: data/top_calibrated_edges.json
  {
    "top_10": [...10 highest calibrated edges across all sources...],
    "by_source_type": {...breakdown counts...}
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "top_calibrated_edges.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(a):
    if a is None: return None
    try: a = int(a)
    except Exception: return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _shrink(model_p: float, baseline_p: float) -> float:
    """Bayesian shrinkage toward baseline. Same shape as book_vs_model_team."""
    if model_p is None or baseline_p is None: return model_p
    gap = abs(model_p - baseline_p)
    weight_baseline = min(0.40, gap * 2.0)
    return model_p * (1 - weight_baseline) + baseline_p * weight_baseline


def run() -> Dict[str, Any]:
    bvm = _load(os.path.join(DATA_DIR, "book_vs_model_team.json"))
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))

    all_edges: List[Dict[str, Any]] = []

    # ---- Real book edges (already calibrated) ----
    for e in (bvm.get("ml_edges") or []) + (bvm.get("total_edges") or []):
        cal_edge = e.get("calibrated_edge_pct")
        if cal_edge is None or cal_edge < 1.0: continue
        all_edges.append({
            "source_type": "REAL_BOOK",
            "sport": "MLB",
            "matchup": e.get("matchup"),
            "side": e.get("side"),
            "team": e.get("team"),
            "market": "TEAM_ML" if e.get("side") in ("HOME", "AWAY") else f"TOTAL_{e.get('side')}_{e.get('total_line')}",
            "model_prob": e.get("model_prob"),
            "calibrated_prob": e.get("calibrated_prob"),
            "book_implied": e.get("book_implied_devig"),
            "book_american": e.get("book_american"),
            "book_decimal": e.get("book_decimal"),
            "calibrated_edge_pct": cal_edge,
            "raw_edge_pct": e.get("edge_pct"),
            "kelly": e.get("kelly_calibrated"),
            "is_underdog": e.get("is_underdog"),
        })

    # ---- (2026-11-03) MODEL_PROP branch DELETED. It listed props with "Book %" =
    # 1/model fair price and "EV" computed against the model's OWN price -- no
    # sportsbook quote existed. Only REAL_BOOK edges (a DraftKings price) remain.

    # Sort by calibrated edge descending
    all_edges.sort(key=lambda e: -e["calibrated_edge_pct"])

    # Count by source_type for diagnostics
    by_type: Dict[str, int] = {}
    for e in all_edges:
        st = e["source_type"]
        by_type[st] = (by_type.get(st) or 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total_edges": len(all_edges),
        "by_source_type": by_type,
        "top_10": all_edges[:10],
        "top_25": all_edges[:25],
        "method_note": "Unified calibrated-edges report. REAL_BOOK = priced against the "
                       "live book line (DraftKings game lines via ESPN's free feed, "
                       "post-shrinkage). Surface 1%+ edges only. (2026-11-03) Model-priced "
                       "props are no longer listed: no sportsbook prop price exists.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[top-calibrated] {o['n_total_edges']} total edges -> {OUT}")
    print(f"  By source: {o['by_source_type']}")
    for i, e in enumerate(o['top_10'][:10], 1):
        print(f"  {i:2d}. [{e['source_type'][:10]:10s}] {e['sport']:5s} {e['matchup'][:30]:30s} "
              f"{(e.get('side') or e.get('market') or '')[:20]:20s} "
              f"cal_p={e['calibrated_prob']:.3f} edge={e['calibrated_edge_pct']:+5.1f}%")
