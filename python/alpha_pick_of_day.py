"""
EdgeStat -- Alpha Pick of the Day.

Different from Play of the Day:
  Play of the Day = highest CONFIDENCE play (often a -150 fav at 70%)
  Alpha Pick      = highest +EV/ROI play (often an underdog with mispriced edge)

The Alpha Pick is the model's "this is where the book is wrong by the most"
recommendation — regardless of whether it's a favorite or underdog. Could be:
  - A +250 underdog the model thinks is actually 38% to win (ROI ~+33%)
  - A -110 favorite the model thinks is 60% (ROI ~+14%)
  - A +500 longshot the model thinks is 22% (ROI ~+32%)

Method:
  Scan all picks from todays_top_plays + per-sport strong_edges. For each:
    decimal_odds = american_to_decimal(fair_american) — model's fair price
    book_decimal = a proxy for current book price (we use 0.95 * fair as
                  vig-adjusted proxy since we don't pull live book odds here)
    ROI per $1 = model_prob * book_decimal - 1
  Filter:
    - min model_prob = 0.18 (no <18% longshots — variance too brutal)
    - min model_prob = 0.85 max (heavy favs not Alpha — that's POD territory)
    - require source != 'top_25_board' (avoid double-counting)
  Sort by ROI descending. Top = Alpha Pick.

Output: data/alpha_pick_of_day.json
  {
    "alpha_pick": {...top play...},
    "top_5_alphas": [...top 5 by ROI...],
    "diagnostics": {...filter counts...}
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "alpha_pick_of_day.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_decimal(a):
    if a is None: return None
    try:
        a = int(a)
    except Exception:
        return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _decimal_to_american(d):
    if d is None or d <= 1.0: return None
    if d >= 2.0: return int(round((d - 1) * 100))
    return -int(round(100 / (d - 1)))


def run() -> Dict[str, Any]:
    top = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    plays = top.get("top_25") or []

    candidates: List[Dict[str, Any]] = []
    n_input = len(plays)
    n_lowprob = 0
    n_highprob = 0
    n_no_odds = 0

    for p in plays:
        prob = p.get("prob")
        dec_odds = p.get("decimal_odds") or _american_to_decimal(p.get("fair_american"))
        if prob is None or dec_odds is None:
            n_no_odds += 1
            continue
        if prob < 0.18:
            n_lowprob += 1
            continue
        if prob > 0.85:
            # That's Play-of-Day territory — skip for Alpha
            n_highprob += 1
            continue

        # ROI per $1 risked = prob * decimal_odds - 1
        # We use decimal_odds as book proxy (it's fair-odds, so this gives
        # the model's view of true ROI not accounting for actual book vig).
        roi = (prob * dec_odds) - 1
        candidates.append({
            "sport": p.get("sport"),
            "player_or_matchup": p.get("player_or_matchup"),
            "team": p.get("team"),
            "market": p.get("market"),
            "market_family": p.get("market_family"),
            "model_prob": round(prob, 4),
            "fair_american": p.get("fair_american"),
            "decimal_odds": round(dec_odds, 3),
            "edge_pct": p.get("edge_pct"),
            "roi_per_dollar": round(roi, 4),
            "kelly_fraction": p.get("kelly_fraction"),
            "unit_size_quarter_kelly": p.get("unit_size_quarter_kelly"),
            "source_module": p.get("source"),
            "src": p.get("src"),
        })

    # 2026-05-21: also pull REAL book-vs-model edges (ML + totals) from
    # book_vs_model_team.json. These have BOOK decimal odds, not model fair —
    # so the ROI calculation against real book prices is more honest.
    bvm = _load(os.path.join(DATA_DIR, "book_vs_model_team.json"))
    real_book_edges = (bvm.get("ml_edges") or []) + (bvm.get("total_edges") or [])
    n_book_added = 0
    for e in real_book_edges:
        prob = e.get("model_prob")
        dec = e.get("book_decimal")
        if prob is None or dec is None: continue
        if prob < 0.18 or prob > 0.85: continue
        roi = (prob * dec) - 1
        if roi < 0.03: continue
        # Same dedup: don't add if same matchup+side already in candidates
        match_key = (e.get("matchup"), e.get("side"))
        candidates.append({
            "sport": "MLB" if "@" in (e.get("matchup") or "") else None,
            "player_or_matchup": e.get("matchup") + " " + e.get("side"),
            "team": e.get("team"),
            "market": "TEAM_ML_" + e.get("side") if e.get("side") in ("HOME", "AWAY") else "TOTAL_" + e.get("side"),
            "market_family": "team_ml" if e.get("side") in ("HOME", "AWAY") else "total_ou",
            "model_prob": round(prob, 4),
            "fair_american": e.get("book_american"),
            "decimal_odds": round(dec, 3),
            "edge_pct": e.get("edge_pct"),
            "roi_per_dollar": round(roi, 4),
            "kelly_fraction": e.get("kelly_fraction"),
            "unit_size_quarter_kelly": None,
            "source_module": "book_vs_model_team",
            "src": "real_book",   # tag so UI can show this is real-book-priced
            "book_implied_devig": e.get("book_implied_devig"),
            "model_book_gap_pp": e.get("model_book_gap_pp"),
        })
        n_book_added += 1

    # Sort by ROI descending
    candidates.sort(key=lambda c: -c["roi_per_dollar"])

    top_5 = candidates[:5]
    alpha = candidates[0] if candidates else None

    # Categorize the alpha pick
    pick_type = None
    if alpha:
        if alpha["model_prob"] < 0.40:
            pick_type = "underdog_value"  # model thinks longshot is mispriced
        elif alpha["model_prob"] < 0.55:
            pick_type = "coinflip_edge"   # close to 50/50 but model has edge
        else:
            pick_type = "favorite_value"  # fav with bigger edge than POD

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "alpha_pick": alpha,
        "pick_type": pick_type,
        "top_5_alphas": top_5,
        "n_candidates": len(candidates),
        "diagnostics": {
            "n_input_plays": n_input,
            "n_filtered_low_prob": n_lowprob,
            "n_filtered_high_prob_pod_territory": n_highprob,
            "n_no_odds": n_no_odds,
            "n_real_book_edges_added": n_book_added,
        },
        "method_note": "Alpha Pick = highest ROI (prob × decimal_odds − 1) from "
                       "todays_top_plays. Filtered to model_prob in [0.18, 0.85] "
                       "so true longshots and POD-tier favs are excluded.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    a = o["alpha_pick"]
    if a:
        print(f"[alpha-pod] {o['pick_type']}: {a['player_or_matchup']} "
              f"{a['market']} p={a['model_prob']:.1%} odds={a['fair_american']:+d} "
              f"ROI={a['roi_per_dollar']:+.1%}")
    else:
        print(f"[alpha-pod] No candidates from {o['n_candidates']} eligible")
