"""
EdgeStat -- NBA first half total O/U prop.

DK alt: '1H total points over/under N.5'. League avg 1H total ~112 (48% of
full game total ~225). Sigma ~7.5.

Method:
  half_total = full_game_total * 0.48 (1H share)
  STRONG-gated on deviation from book half-line (book_total/2).

Output: data/nba_half_total_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_half_total_props.json")

HALF_SHARE = 0.48


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
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    # Pull team total edges to get model totals
    tt_edge = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))
    home_lams: Dict[str, float] = {}
    away_lams: Dict[str, float] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        proj = _safe(r.get("model_proj_pts_anchored"))
        if r.get("side") == "HOME":
            home_lams[m] = proj
        elif r.get("side") == "AWAY":
            away_lams[m] = proj

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "")
        away = (g.get("away_team") or g.get("away") or "")
        if not home or not away: continue

        # Try to match matchup format
        matchup_candidates = [f"{away} @ {home}", f"{away[:3].upper()} @ {home[:3].upper()}"]
        matchup_used = None
        for cand in matchup_candidates:
            if cand in home_lams and cand in away_lams:
                matchup_used = cand; break
        if not matchup_used:
            # Fallback: use first available
            for cand in home_lams:
                if home[:3].upper() in cand.upper() or home.lower() in cand.lower():
                    matchup_used = cand; break

        if not matchup_used: continue
        home_proj = home_lams[matchup_used]
        away_proj = away_lams[matchup_used]
        full_total = home_proj + away_proj
        half_total = full_total * HALF_SHARE
        sigma = max(6.0, math.sqrt(half_total) * 1.0)

        book_total = _safe((g.get("market") or {}).get("total"), 224.0)
        book_half = book_total * HALF_SHARE

        # Test lines near book_half
        edges: List[Dict[str, Any]] = []
        base_line = round(book_half * 2) / 2
        for offset in (-2.0, -1.0, 0, 1.0, 2.0):
            line = base_line + offset
            p_o = _p_over(half_total, sigma, line)
            p_u = 1 - p_o
            for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                if 0.58 <= p <= 0.68:
                    edges.append({"market": f"1H_TOTAL_{direction}_{line}",
                                   "line": line, "direction": direction,
                                   "p": round(p, 3),
                                   "fair_odds": _american(p)})

        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG_HALF" if best_edge else "NONE"

        rows.append({
            "matchup": matchup_used,
            "home_team": home,
            "away_team": away,
            "full_game_model_total": round(full_total, 1),
            "model_1H_total": round(half_total, 1),
            "book_full_total": book_total,
            "book_1H_total": round(book_half, 1),
            "delta_vs_book": round(half_total - book_half, 1),
            "sigma": round(sigma, 2),
            "best_market": best_edge,
            "edge_class": edge_class,
        })

    strong = [r for r in rows if r["edge_class"] == "STRONG_HALF"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "1H total = full_game_model * 0.48 (1H share). Tests offset "
                       "lines around book_total*0.48. STRONG when p in [0.58, 0.68].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-1h] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
