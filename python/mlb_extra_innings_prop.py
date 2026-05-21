"""
EdgeStat -- MLB extra-innings yes/no prop projection.

Common DK line: "Game to go to extra innings - Yes/No"
Typical book: Yes +600 to +800, No -1000 to -1500.

Method:
  Historical MLB rate of extra-inning games: ~9-10%.
  Adjust based on:
    - Game total line (low totals favor extras — tighter scoring)
    - Run differential expected (large favorite reduces extras chance)
    - Both bullpens strong (reduces extras... actually increases since less
      late scoring; we use this as small positive factor)
  Final: base_rate * total_adj * differential_adj

  STRONG_YES when P(extras) >= 0.115 (vs +700 book = 12.5% breakeven)
  STRONG_NO when P(no_extras) >= 0.93 (vs -1300 book = 92.9% breakeven)

Output: data/mlb_extra_innings_prop.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_extra_innings_prop.json")

# League-average extra-innings rate (10 yrs MLB data)
BASE_EXTRA_RATE = 0.095


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


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        # Game total line — lower totals = tighter games = more extras
        game_total = _safe(g.get("total") or g.get("fair_total"), 8.5)
        # Run differential expected — if one team heavily favored, less likely extras
        p_home_win = _safe(g.get("p_home_win") or g.get("model_home_win"), 0.5)
        run_diff = abs(p_home_win - 0.5) * 2  # 0.0 (even) to 1.0 (one-sided)

        # Adjustments
        # Lower total (e.g. 7.0) -> more extras (+15% rel); Higher total (10) -> fewer (-15%)
        total_adj = max(0.75, min(1.25, 1 + (8.5 - game_total) * 0.05))
        # Heavy favorite -> fewer extras (rated game is decided early)
        diff_adj = max(0.70, min(1.10, 1 - run_diff * 0.30))

        p_extras = BASE_EXTRA_RATE * total_adj * diff_adj
        p_extras = max(0.04, min(0.20, p_extras))  # clamp to reasonable range
        p_no_extras = 1 - p_extras

        edge_class = "NONE"
        best_market = None
        # STRONG_YES when P(extras) >= 0.115 (vs +700 book = 12.5%)
        if p_extras >= 0.115:
            edge_class = "STRONG_YES"
            best_market = {"market": "EXTRA_INNINGS_YES", "p": round(p_extras, 3),
                           "fair_odds": _american(p_extras)}
        # STRONG_NO when P(no_extras) >= 0.93 (vs -1300 = 92.9%)
        elif p_no_extras >= 0.93:
            edge_class = "STRONG_NO"
            best_market = {"market": "EXTRA_INNINGS_NO", "p": round(p_no_extras, 3),
                           "fair_odds": _american(p_no_extras)}

        rows.append({
            "matchup": matchup_str,
            "game_total": game_total,
            "p_home_win": p_home_win,
            "run_diff_signal": round(run_diff, 3),
            "total_adj": round(total_adj, 3),
            "diff_adj": round(diff_adj, 3),
            "p_extras": round(p_extras, 3),
            "p_no_extras": round(p_no_extras, 3),
            "fair_yes_odds": _american(p_extras),
            "fair_no_odds": _american(p_no_extras),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_extras"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(extras) = 0.095 baseline x total_adj (lower total = more extras) "
                       "x diff_adj (heavy favorite = fewer extras). "
                       "STRONG_YES p>=11.5% (vs +700), STRONG_NO p_no>=93% (vs -1300).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-extras] {o['n_games']} games, {o['n_strong_edges']} strong edges -> {OUT}")
