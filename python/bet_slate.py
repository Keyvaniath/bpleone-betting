"""
EdgeStat -- consolidated daily bet slate.

Synthesizes the four hero pick types (POD / Alpha / Book Edge / Parlay)
into a single normalized JSON the dashboard reads.

For each pick:
  type            POD | ALPHA | BOOK | PARLAY
  title           display name
  market          market description
  prob            calibrated probability
  fair_american   odds
  decimal_odds    decimal price
  edge_pct        calibrated edge (%)
  kelly_fraction  full Kelly (not yet quartered — UI computes ¼-Kelly stake)

Output: data/bet_slate.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "bet_slate.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    slate: List[Dict[str, Any]] = []

    # --- POD: top pick from todays_top_plays_board ---
    top = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    top_25 = top.get("top_25") or []
    if top_25:
        p = top_25[0]
        if (p.get("prob") or 0) >= 0.62:
            slate.append({
                "type": "POD",
                "type_label": "★ PLAY OF DAY",
                "title": p.get("player_or_matchup") or "—",
                "market": p.get("market") or p.get("market_family") or "",
                "sport": p.get("sport") or "",
                "prob": p.get("prob"),
                "fair_american": p.get("fair_american"),
                "decimal_odds": p.get("decimal_odds"),
                "edge_pct": p.get("edge_pct"),
                "kelly_fraction": p.get("kelly_fraction") or 0,
            })

    # --- ALPHA: alpha_pick_of_day's top ROI play ---
    alpha = _load(os.path.join(DATA_DIR, "alpha_pick_of_day.json"))
    a = alpha.get("alpha_pick")
    if a:
        slate.append({
            "type": "ALPHA",
            "type_label": "★ ALPHA PICK",
            "title": a.get("player_or_matchup") or "—",
            "market": a.get("market") or "",
            "sport": a.get("sport") or "",
            "prob": a.get("model_prob"),
            "fair_american": a.get("fair_american"),
            "decimal_odds": a.get("decimal_odds"),
            "edge_pct": (a.get("roi_per_dollar") or 0) * 100,
            "kelly_fraction": a.get("kelly_fraction") or 0,
            "pick_type": alpha.get("pick_type"),
        })

    # --- BOOK: top 3 real-book edges (post-calibration) ---
    bvm = _load(os.path.join(DATA_DIR, "book_vs_model_team.json"))
    real_book = (bvm.get("ml_edges") or []) + (bvm.get("total_edges") or [])
    real_book.sort(key=lambda e: -(e.get("calibrated_edge_pct") or 0))
    for e in real_book[:3]:
        if (e.get("calibrated_edge_pct") or 0) < 2.0: continue
        side = e.get("side") or ""
        team = e.get("team") or ""
        title = f"{e.get('matchup')} · {side}"
        if team and side in ("HOME", "AWAY"):
            title += f" ({team})"
        if e.get("total_line"):
            title += f" · O/U {e.get('total_line')}"
        slate.append({
            "type": "BOOK",
            "type_label": "📊 BOOK EDGE",
            "title": title,
            "market": "TEAM_ML" if side in ("HOME", "AWAY") else f"TOTAL_{side}",
            "sport": "MLB",
            "prob": e.get("calibrated_prob"),
            "fair_american": e.get("book_american"),
            "decimal_odds": e.get("book_decimal"),
            "edge_pct": e.get("calibrated_edge_pct"),
            "kelly_fraction": e.get("kelly_calibrated") or e.get("kelly_fraction") or 0,
            "raw_edge_pct": e.get("edge_pct"),
            "book_implied_devig": e.get("book_implied_devig"),
        })

    # --- PARLAY: top balanced 2-leg ---
    parlays = _load(os.path.join(DATA_DIR, "cross_sport_parlays.json"))
    par = (parlays.get("balanced_2_leg_picks") or parlays.get("top_2_leg_parlays") or [None])[0]
    if par and par.get("edge_pct", 0) >= 5.0:
        names = " + ".join((L.get("player_or_matchup") or "")[:20] for L in par.get("legs", []))
        slate.append({
            "type": "PARLAY",
            "type_label": "🎲 PARLAY OF DAY",
            "title": names,
            "market": f"{par.get('n_legs')}-leg",
            "sport": "MULTI",
            "prob": par.get("joint_prob"),
            "fair_american": par.get("fair_parlay_american"),
            "decimal_odds": par.get("fair_parlay_decimal"),
            "edge_pct": par.get("edge_pct"),
            "kelly_fraction": 0.05,  # conservative cap for parlays
            "correlation_factor": par.get("correlation_factor"),
        })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_picks": len(slate),
        "slate": slate,
        "kelly_fraction_used": "quarter_kelly",  # UI applies the ¼ multiplier
        "method_note": "Consolidated bet slate: POD + ALPHA + top-3 BOOK + PARLAY. "
                       "All probabilities are calibrated where possible. "
                       "Kelly fractions are FULL Kelly; UI multiplies by 0.25.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bet-slate] {o['n_picks']} picks -> {OUT}")
    for s in o['slate']:
        print(f"  [{s['type']:6s}] {s['title'][:35]:35s} edge={s.get('edge_pct') or 0:+5.1f}% "
              f"kelly={s.get('kelly_fraction') or 0:.3f}")
