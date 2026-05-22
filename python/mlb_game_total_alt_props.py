"""
EdgeStat -- MLB game total alternate market (over/under 7/8/9/10/11/12+ runs).

Most-bet MLB market. Common DK lines:
  - Main line 8.5 or 9.0: standard -110/-110
  - Alt lines: 7.5 (-150 over / +130 under), 10.5 (+150 over / -180 under)

Method:
  Inherits expected_total_runs from mlb_team_total_edge (sum of both sides).
  Skellam approximation via two Poisson team totals.
  P(game total >= N) = 1 - poisson_cdf(N-1, lam_total)

  STRONG_OVER when 5%+ edge vs typical -110 book.

Output: data/mlb_game_total_alt_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_total_alt_props.json")


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    # Aggregate per matchup: sum both sides' expected_runs
    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        agg = by_matchup.setdefault(m, {"home_runs": 0.0, "away_runs": 0.0,
                                        "matchup": m})
        side = r.get("side")
        runs = _safe(r.get("model_expected_runs_anchored"))
        if side == "HOME": agg["home_runs"] = runs
        elif side == "AWAY": agg["away_runs"] = runs

    # Get book game total from matchups
    game_total_book: Dict[str, float] = {}
    for g in (matchups.get("games") or []):
        m = g.get("matchup") or ""
        if not m: continue
        total = _safe((g.get("market") or {}).get("total"), 8.5)
        game_total_book[m] = total

    rows: List[Dict[str, Any]] = []
    for matchup, agg in by_matchup.items():
        lam_total = agg["home_runs"] + agg["away_runs"]
        if lam_total <= 0: continue

        book_total = game_total_book.get(matchup, 8.5)

        # Compute P(over) at multiple lines
        results: Dict[str, float] = {}
        for line in (6.5, 7.5, 8.5, 9.5, 10.5, 11.5):
            target_int = int(line + 0.5)
            p_over = _poisson_at_least(target_int, lam_total)
            results[f"p_over_{line}"] = round(p_over, 3)

        # Best edge identification
        edges: List[Dict[str, Any]] = []
        for line, p_key in [(6.5, "p_over_6.5"), (7.5, "p_over_7.5"),
                            (8.5, "p_over_8.5"), (9.5, "p_over_9.5"),
                            (10.5, "p_over_10.5"), (11.5, "p_over_11.5")]:
            p_over = results[p_key]
            p_under = 1 - p_over
            for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                # Only flag lines near the book line (within +/- 2.0 runs)
                if abs(line - book_total) <= 2.0 and 0.58 <= p <= 0.70:
                    edges.append({
                        "market": f"GAME_TOTAL_{direction}_{line}",
                        "line": line,
                        "direction": direction,
                        "p": round(p, 3),
                        "fair_odds": _american(p),
                    })

        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG_TOTAL" if best_edge else "NONE"

        rows.append({
            "matchup": matchup,
            "book_total": book_total,
            "model_total_lam": round(lam_total, 2),
            "home_expected_runs": round(agg["home_runs"], 2),
            "away_expected_runs": round(agg["away_runs"], 2),
            **results,
            "best_market": best_edge,
            "edge_class": edge_class,
            "edges_found": edges,
        })

    rows.sort(key=lambda r: -r["model_total_lam"])
    strong = [r for r in rows if r["edge_class"] == "STRONG_TOTAL"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(game total >= N) at Poisson(lam_total) where lam_total = "
                       "home_expected_runs + away_expected_runs (from team_total_edge). "
                       "Tests 6.5-11.5 lines, flags STRONG within +/- 2 runs of book and "
                       "p in [0.58, 0.70] (5%+ edge vs -110 book).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[game-total] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
