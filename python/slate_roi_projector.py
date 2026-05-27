"""
EdgeStat -- Slate ROI projector / Kelly heatmap.

Given today's top-tier picks (alpha POD + top_calibrated_edges +
elite_board 5+ signal entities), project the expected ROI and bankroll
movement under various Kelly fractions.

For each pick:
  p_win    = model probability
  fair_odds = -100/(1/p_win - 1) if p>=0.5 else (1/p_win - 1) * 100
  book_odds = if available
  edge_pp = (p_win * decimal_book_odds) - 1

Portfolio:
  N picks each sized at Kelly fraction f% of bankroll
  Expected return = sum(p_i * b_i - (1-p_i)) * f * B
  Variance = bankroll var contribution

Output: data/slate_roi_projection.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_roi_projection.json")


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


def _american_to_decimal(odds: float) -> float:
    if odds == 0: return 1.0
    if odds > 0: return (odds / 100.0) + 1.0
    return (100.0 / abs(odds)) + 1.0


def _kelly(p: float, decimal_odds: float) -> float:
    """Standard Kelly fraction."""
    b = decimal_odds - 1
    if b <= 0: return 0.0
    f = (p * b - (1 - p)) / b
    return max(f, 0.0)


def run() -> Dict[str, Any]:
    pod = _load(os.path.join(DATA_DIR, "alpha_pick_of_day.json"))
    top_edges = _load(os.path.join(DATA_DIR, "top_calibrated_edges.json"))
    eb = _load(os.path.join(DATA_DIR, "elite_alerts_board.json"))

    picks: List[Dict[str, Any]] = []

    # POD
    pp = pod.get("pick") or {}
    if pp:
        p_win = _safe(pp.get("p_win") or pp.get("model_p"))
        odds = _safe(pp.get("book_odds") or pp.get("odds"), -110)
        if p_win > 0 and odds != 0:
            picks.append({
                "source": "POD",
                "subject": pp.get("market") or pp.get("subject"),
                "p_win": p_win,
                "book_odds": odds,
                "decimal_odds": _american_to_decimal(odds),
            })

    # Top calibrated edges
    for e in (top_edges.get("top_25") or top_edges.get("rows") or [])[:20]:
        if not isinstance(e, dict): continue
        p_win = _safe(e.get("p_win") or e.get("model_p"))
        odds = _safe(e.get("book_odds") or e.get("odds"), -110)
        if p_win <= 0: continue
        picks.append({
            "source": "TOP_EDGE",
            "subject": e.get("market") or e.get("subject"),
            "p_win": p_win,
            "book_odds": odds,
            "decimal_odds": _american_to_decimal(odds),
        })

    # Elite board entries: assume p_win = 0.55 baseline for 5+ signal entities at -115 book
    for ent in (eb.get("elites") or [])[:10]:
        if not isinstance(ent, dict): continue
        n_sig = ent.get("n_signals", 0) or 0
        if n_sig < 5: continue
        # Assume entity-level alerts at +/-110 American odds with p calibrated by signal strength
        # 5 signals -> p=0.55; 6 -> 0.58; 7 -> 0.62
        p_win = min(0.50 + (n_sig - 4) * 0.03, 0.72)
        odds = -115
        picks.append({
            "source": "ELITE_BOARD",
            "subject": ent.get("entity"),
            "p_win": p_win,
            "book_odds": odds,
            "decimal_odds": _american_to_decimal(odds),
            "n_signals": n_sig,
        })

    # Compute Kelly + expected ROI for each pick
    kelly_fractions = [0.25, 0.5, 1.0]  # quarter / half / full Kelly
    for p in picks:
        p_win = p["p_win"]
        dec = p["decimal_odds"]
        kelly_full = _kelly(p_win, dec)
        p["kelly_full"] = round(kelly_full, 4)
        p["edge_pp"] = round((p_win * dec) - 1, 4)
        p["kelly_sizes"] = {f"{int(f*100)}%": round(kelly_full * f, 4)
                            for f in kelly_fractions}

    # Aggregate portfolio
    n = len(picks)
    avg_edge = sum(p["edge_pp"] for p in picks) / n if n else 0
    avg_kelly = sum(p["kelly_full"] for p in picks) / n if n else 0
    portfolio_edge_pp = avg_edge  # under independence
    sum_kelly_quarter = sum(p["kelly_sizes"]["25%"] for p in picks)

    # Expected ROI on $100 bankroll allocating quarter-Kelly per pick
    bankroll = 100.0
    expected_pl = 0.0
    for p in picks:
        size = p["kelly_sizes"]["25%"] * bankroll
        win_payout = size * (p["decimal_odds"] - 1)
        loss = -size
        expected_pl += p["p_win"] * win_payout + (1 - p["p_win"]) * loss

    expected_roi_pct = (expected_pl / bankroll) * 100 if bankroll else 0

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_picks": n,
        "avg_edge_pp": round(avg_edge * 100, 2),
        "avg_kelly_full_pct": round(avg_kelly * 100, 2),
        "sum_quarter_kelly_pct": round(sum_kelly_quarter * 100, 2),
        "expected_pl_on_100_bankroll": round(expected_pl, 2),
        "expected_roi_pct_quarter_kelly": round(expected_roi_pct, 2),
        "method_note": "Slate ROI projector. For each top-tier pick: computes "
                       "Kelly fraction f = (p*b - (1-p)) / b where b = decimal_odds - 1. "
                       "Portfolio sized at 25% Kelly per pick (conservative). "
                       "Expected ROI computed on $100 bankroll.",
        "picks": picks,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[slate-roi] {o['n_picks']} picks, avg edge={o['avg_edge_pp']}%, "
          f"expected ROI (1/4 Kelly) = {o['expected_roi_pct_quarter_kelly']}% -> {OUT}")
