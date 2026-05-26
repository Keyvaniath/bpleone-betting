"""
EdgeStat -- MLB which team reaches 3 runs first prop.

DK alt: 'First team to score 3 runs'. Companion to NBA race-to-N.

Method:
  P(home first to 3) approximated by Poisson share:
    p_home_first_3 = lam_home / (lam_home + lam_away)
  with mild home tempo boost (+2%).

  Also includes 'neither' outcome (game ends with both teams under 3).

  STRONG_HOME when p_home_first_3 >= 0.56 (vs -130 book = 56.5%)

Output: data/mlb_race_to_3_runs.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_race_to_3_runs.json")


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

    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        side = r.get("side")
        proj = _safe(r.get("model_expected_runs_anchored"))
        team = r.get("team")
        entry = by_matchup.setdefault(m, {"matchup": m})
        if side == "HOME":
            entry["home_team"] = team
            entry["home_lam"] = proj
        elif side == "AWAY":
            entry["away_team"] = team
            entry["away_lam"] = proj

    rows: List[Dict[str, Any]] = []
    for m, g in by_matchup.items():
        lam_h = _safe(g.get("home_lam"))
        lam_a = _safe(g.get("away_lam"))
        if lam_h <= 0 or lam_a <= 0: continue

        # P(team scores >= 3)
        p_home_3plus = _poisson_at_least(3, lam_h)
        p_away_3plus = _poisson_at_least(3, lam_a)

        # P(neither reaches 3)
        p_neither = (1 - p_home_3plus) * (1 - p_away_3plus)
        p_some_3 = 1 - p_neither

        # Given someone reaches 3, share by Poisson rate (with home tempo boost)
        share_home = lam_h / (lam_h + lam_a) + 0.020  # mild home tempo boost
        share_home = max(0.20, min(0.80, share_home))

        p_home_first = p_some_3 * share_home
        p_away_first = p_some_3 * (1 - share_home)

        edge_class = "NONE"
        best_market = None
        # League baseline = ~0.50 with home tempo boost; STRONG needs deviation
        if 0.54 <= p_home_first <= 0.62:
            edge_class = "STRONG_HOME_FIRST_3"
            best_market = {"market": "HOME_FIRST_TO_3", "p": round(p_home_first, 3),
                           "fair_odds": _american(p_home_first)}
        elif 0.50 <= p_away_first <= 0.58:
            edge_class = "STRONG_AWAY_FIRST_3"
            best_market = {"market": "AWAY_FIRST_TO_3", "p": round(p_away_first, 3),
                           "fair_odds": _american(p_away_first)}
        elif p_neither >= 0.15:
            edge_class = "STRONG_NEITHER_3"
            best_market = {"market": "NEITHER_REACHES_3", "p": round(p_neither, 3),
                           "fair_odds": _american(p_neither)}

        rows.append({
            "matchup": m,
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_lam": round(lam_h, 2),
            "away_lam": round(lam_a, 2),
            "p_home_3plus": round(p_home_3plus, 3),
            "p_away_3plus": round(p_away_3plus, 3),
            "p_home_first_to_3": round(p_home_first, 3),
            "p_away_first_to_3": round(p_away_first, 3),
            "p_neither_to_3": round(p_neither, 3),
            "fair_home": _american(p_home_first),
            "fair_away": _american(p_away_first),
            "fair_neither": _american(p_neither),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -max(r["p_home_first_to_3"], r["p_away_first_to_3"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "p_home_first_to_3 = P(>=3 by anyone) * (lam_h / lam_total + "
                       "0.020 home boost). P(neither) = (1-P_h_3plus)*(1-P_a_3plus). "
                       "STRONG zones tuned for +130/+150 book markets.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[race-3] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
