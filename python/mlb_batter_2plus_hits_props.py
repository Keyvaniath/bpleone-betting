"""
EdgeStat -- MLB batter 2+ hits yes/no prop.

Common DK line: "Batter to record 2+ hits in game"
Typical book: YES +180 to +280 (26-36% breakeven). Top contact hitters
(~ .300+ avg) closer to +130 (43%).

Method:
  Primary: real `2_plus_hits` prob from mlb_batter_logs.props (last 14 games)
  Fallback: Poisson estimate from batter AVG * AB.

  P(2+ hits) follows Poisson at rate = batter_avg * AB.
  Hit rate per AB * 4.0 AB ≈ 1.0-1.3 expected hits for a typical bat.
  P(>= 2 hits) = 1 - P(0) - P(1).

STRONG_YES at p >= 0.42 (vs +130 book ~ 43.5% breakeven, requires 3%+ edge
                         OR longer lines like +160 = 38% breakeven, more
                         attainable). Set range [0.42, 0.55] to capture
                         realistic top-of-order picks.

Output: data/mlb_batter_2plus_hits_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_2plus_hits_props.json")


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


def _expected_ab(order: int) -> float:
    if order <= 3: return 4.1
    if order <= 6: return 3.8
    return 3.4


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))

    parks = today.get("parks") or {}
    lvr_idx = {(r.get("batter") or "").lower(): r for r in (lvr.get("all_batters") or []) if r.get("batter")}
    blog_idx = {(b.get("name") or "").lower(): b for b in (batter_logs.get("batters") or []) if b.get("name")}

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                hits_source = "ops_proxy"
                blog = blog_idx.get((name or "").lower())
                if blog:
                    props = blog.get("props") or {}
                    real_p = (props.get("2_plus_hits") or {}).get("p")
                    n_games = blog.get("n_games_logged") or 0
                    if real_p is not None and n_games >= 8:
                        # Light park adjustment
                        p_2 = float(real_p) * (park_run_factor ** 0.20)
                        p_2 = max(0.03, min(0.85, p_2))
                        hits_source = "real_last_14"
                if hits_source == "ops_proxy":
                    # Fallback Poisson from OPS-derived AVG
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    est_avg = max(0.21, min(0.35, season_ops * 0.36))
                    ab = _expected_ab(order)
                    expected_hits = est_avg * ab * (park_run_factor ** 0.30)
                    p_2 = _poisson_at_least(2, expected_hits)

                p_no = 1 - p_2

                edge_class = "NONE"
                best_market = None
                # STRONG_YES at p in [0.42, 0.55] (vs +130 book = 43.5% breakeven)
                if 0.42 <= p_2 <= 0.55:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "HITS_2PLUS_YES", "p": round(p_2, 3),
                                   "fair_odds": _american(p_2)}
                # STRONG_NO at p_no in [0.78, 0.88] (vs -250 book = 71.4% breakeven)
                elif 0.78 <= p_no <= 0.88:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "HITS_2PLUS_NO", "p": round(p_no, 3),
                                   "fair_odds": _american(p_no)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "hits_source": hits_source,
                    "p_2_plus_hits": round(p_2, 3),
                    "p_no_2_hits": round(p_no, 3),
                    "fair_yes_odds": _american(p_2),
                    "fair_no_odds": _american(p_no),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_2_plus_hits"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Primary: real 2_plus_hits prob from batter_logs (last 14 games). "
                       "Fallback: Poisson(avg*AB). STRONG_YES p in [0.42, 0.55], "
                       "STRONG_NO p_no in [0.78, 0.88].",
        "top_25_by_p_2plus": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[batter-2h] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
