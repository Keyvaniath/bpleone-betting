"""
EdgeStat -- NHL per-period totals + period-by-period projections.

NHL game totals split into:
  - 1st period total (typically 1.5 over/under)
  - 2nd period total (typically 1.5)
  - 3rd period total (typically 1.5-2.0)

Empirical distribution: 1st period accounts for ~31%% of scoring, 2nd ~33%%,
3rd ~36%% (slight tilt to 3rd due to pulling goalies + late-game pressure).

Approach:
  expected_total = base game total (from market or estimated 6.0)
  per_period[i] = expected_total * weights[i]
  Poisson per period -> P(>= line+1)

Output: data/nhl_period_totals_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

from nhl_teams import abbr as _abbr   # full scoreboard name -> abbrev (fixes [:3] team drops)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_period_totals_props.json")

PERIOD_WEIGHTS = {1: 0.31, 2: 0.33, 3: 0.36}
DEFAULT_GAME_TOTAL = 6.0


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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue

        # Get game total estimate (from goalie matchup if available, else default)
        gm = _load(os.path.join(DATA_DIR, "nhl_goalie_matchup.json"))
        # Try to match game by team abbrev
        home = _abbr(g.get("home_team") or "")
        away = _abbr(g.get("away_team") or "")
        if not home or not away: continue

        game_total = DEFAULT_GAME_TOTAL
        for gm_row in (gm.get("matchups") or []):
            if _abbr(gm_row.get("home_team") or "") == home:
                game_total = _safe(gm_row.get("expected_total") or gm_row.get("fair_total"), DEFAULT_GAME_TOTAL)
                break

        # Per-period projections
        period_projections = []
        period_strong = []
        for period, weight in PERIOD_WEIGHTS.items():
            lam = game_total * weight
            # Common book lines: 1.5
            p_over_1_5 = _poisson_at_least(2, lam)
            p_over_0_5 = _poisson_at_least(1, lam)
            p_under_1_5 = 1 - p_over_1_5

            # Edge classification at 1.5 line
            edge_class = "NONE"
            best_market = None
            if 0.62 <= p_over_1_5 <= 0.72:
                edge_class = "STRONG_OVER_1_5"
                best_market = {"market": f"P{period}_OVER_1.5", "p": round(p_over_1_5, 3),
                               "fair_odds": _american(p_over_1_5)}
            elif 0.62 <= p_under_1_5 <= 0.72:
                edge_class = "STRONG_UNDER_1_5"
                best_market = {"market": f"P{period}_UNDER_1.5", "p": round(p_under_1_5, 3),
                               "fair_odds": _american(p_under_1_5)}

            period_projections.append({
                "period": period,
                "expected_goals": round(lam, 2),
                "p_over_1_5": round(p_over_1_5, 3),
                "p_under_1_5": round(p_under_1_5, 3),
                "p_over_0_5": round(p_over_0_5, 3),
                "fair_over_1_5": _american(p_over_1_5),
                "fair_under_1_5": _american(p_under_1_5),
                "edge_class": edge_class,
                "best_market": best_market,
            })
            if edge_class.startswith("STRONG") and best_market:
                period_strong.append({**best_market, "period": period})

        rows.append({
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "game_total_used": game_total,
            "periods": period_projections,
            "n_period_strong": len(period_strong),
            "strong_period_markets": period_strong,
        })

    all_strong = []
    for r in rows:
        for sm in r["strong_period_markets"]:
            all_strong.append({"matchup": r["matchup"], **sm})

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(all_strong),
        "period_weights": PERIOD_WEIGHTS,
        "method_note": "Per-period lambda = game_total × period_weight. "
                       "Poisson over/under at 1.5 line. STRONG = 10%+ edge vs -120 book.",
        "rows": rows,
        "strong_edges": all_strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-periods] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
