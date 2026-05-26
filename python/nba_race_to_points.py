"""
EdgeStat -- NBA team race-to-N points alternate market.

DK alt: 'First team to reach N points' (most commonly 10, 15, 20).

Method:
  Approximated from team total projection. Higher-PPG team has higher
  P(first to N). Use ratio: p_home_first = lam_home / (lam_home + lam_away).
  This is exact under Poisson assumption.

  Then adjust for tempo lead: home team starts with ball more often + has
  marginal +2-3% boost on race-to markets.

  STRONG_HOME when p_home_first >= 0.56 (vs -130 book = 56.5%)
  STRONG_AWAY when p_away_first >= 0.56

Output: data/nba_race_to_points.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_race_to_points.json")


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
    tt_edge = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))

    # Aggregate per matchup
    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        side = r.get("side")
        proj = _safe(r.get("model_proj_pts_anchored"))
        entry = by_matchup.setdefault(m, {"matchup": m})
        if side == "HOME":
            entry["home_team"] = r.get("team")
            entry["home_proj"] = proj
        elif side == "AWAY":
            entry["away_team"] = r.get("team")
            entry["away_proj"] = proj

    rows: List[Dict[str, Any]] = []
    for m, g in by_matchup.items():
        home_proj = _safe(g.get("home_proj"))
        away_proj = _safe(g.get("away_proj"))
        if home_proj <= 0 or away_proj <= 0: continue

        total = home_proj + away_proj
        # Home tempo boost: +3% for opening-tip + home crowd
        p_home_first = home_proj / total + 0.030
        p_home_first = max(0.20, min(0.80, p_home_first))
        p_away_first = 1 - p_home_first

        # For each race-to threshold
        thresholds = [10, 15, 20]
        race_results: Dict[str, Any] = {}
        for n in thresholds:
            # Higher N favors the higher-scoring team slightly more
            n_factor = 0.005 * (n - 10)  # +0.5% per 5 pts above 10
            ph = p_home_first + (n_factor if home_proj > away_proj else -n_factor)
            ph = max(0.20, min(0.80, ph))
            race_results[f"race_to_{n}"] = {
                "p_home_first": round(ph, 3),
                "p_away_first": round(1 - ph, 3),
                "fair_home": _american(ph),
                "fair_away": _american(1 - ph),
            }

        # Use race_to_15 as the primary signal (mid-range, most predictive)
        primary = race_results["race_to_15"]
        edge_class = "NONE"
        best_market = None
        if primary["p_home_first"] >= 0.56:
            edge_class = "STRONG_HOME_FIRST"
            best_market = {"market": "RACE_TO_15_HOME",
                           "p": primary["p_home_first"],
                           "fair_odds": primary["fair_home"]}
        elif primary["p_away_first"] >= 0.56:
            edge_class = "STRONG_AWAY_FIRST"
            best_market = {"market": "RACE_TO_15_AWAY",
                           "p": primary["p_away_first"],
                           "fair_odds": primary["fair_away"]}

        rows.append({
            "matchup": m,
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_proj_pts": round(home_proj, 1),
            "away_proj_pts": round(away_proj, 1),
            "race_to": race_results,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(home first to N pts) = lam_home/lam_total + 0.030 (home "
                       "tempo boost). Adjusts upward for higher-N when home is "
                       "higher-scoring. STRONG when p >= 0.56 (vs -130 book 56.5%).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[race-to] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
