"""
EdgeStat -- Golf per-player round score O/U prop.

DK market: 'Player to score under N.5 in current round'.

Method:
  Pulls per-player espr (expected score per round vs par) from
  golf_live_projections. Round score = par + espr (relative to course par 70-72).

  Sigma per round ~ 2.8 strokes. Normal CDF at typical lines.

  STRONG when 10%+ edge vs -120 book.

Output: data/golf_round_score_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_round_score_props.json")


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


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    projections = _load(os.path.join(DATA_DIR, "golf_live_projections.json"))
    players_src = projections.get("all_projections") or projections.get("top_10_favorites") or []
    par = int(_safe(projections.get("course_par"), 71))

    rows: List[Dict[str, Any]] = []
    for p in players_src:
        if not isinstance(p, dict): continue
        name = p.get("name") or p.get("player")
        # Derive per-round espr: (projected_final - current_to_par) / rounds_left
        proj_final = _safe(p.get("projected_final_to_par"), 0)
        current = _safe(p.get("current_to_par"), 0)
        rounds_played = int(_safe(p.get("rounds_played"), 0))
        rounds_left = max(1, 4 - rounds_played)

        if rounds_left > 0:
            espr = (proj_final - current) / rounds_left
        else:
            espr = 0

        # Expected score for upcoming round = par + espr
        proj_round_score = par + espr
        sigma = 2.8

        # Test only the most-realistic line (nearest 0.5) — typical book offering
        # ranges 1.5 strokes above/below typical performance for that player.
        # To avoid false positives, require espr to deviate meaningfully from 0
        # (otherwise every player at par-level projection triggers).
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        # Only flag when ESPR meaningfully off baseline AND projection differs
        # from round-to-half by enough to be exploitable.
        if abs(espr) >= 0.7:
            base_line = round(proj_round_score * 2) / 2
            # Test lines that put projection ~0.5-1.5 strokes from line
            # (Normal at sigma 2.8 with line 1 stroke off gives ~64% one-side)
            for offset in (-1.5, -1.0, 0.5, 1.0, 1.5):
                line = base_line + offset
                if line < 60.5 or line > 80.5: continue
                p_over = _p_over(proj_round_score, sigma, line)
                p_under = 1 - p_over
                for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                    if 0.60 <= p <= 0.68:  # tighter zone
                        edge_amt = p - 0.545
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {"market": f"ROUND_{direction}_{line}",
                                           "line": line, "direction": direction,
                                           "p": round(p, 3),
                                           "fair_odds": _american(p)}
                            edge_class = "STRONG"

        rows.append({
            "player": name,
            "current_to_par": current,
            "rounds_played": rounds_played,
            "rounds_left": rounds_left,
            "espr": round(espr, 2),
            "projected_round_score": round(proj_round_score, 2),
            "sigma": sigma,
            "best_market": best_market,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: r["projected_round_score"])
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "course_par": par,
        "n_players": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Per-player upcoming-round score = par + espr (expected score "
                       "per round vs par). Sigma = 2.8 strokes/round. Tests "
                       "offsets +/- 1.0-1.5 strokes from projection. STRONG_ALT when "
                       "10%+ edge vs hypothetical -120 book. NOTE: without real book "
                       "lines this surfaces model deviations only - validate vs DK before betting.",
        "top_15_by_score": rows[:15],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[golf-round] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
