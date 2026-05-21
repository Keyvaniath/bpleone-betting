"""
EdgeStat -- NHL puck line (-1.5 / +1.5) prop projection.

NHL puck line is similar to MLB run line: favorite -1.5 vs underdog +1.5.
Typical book: Favorite -1.5 +160 to +220 (more juice than baseball because
hockey is lower-scoring — 2-goal margins are rarer).

Method (Skellam approximation via Normal):
  Goals modeled as Poisson per team. expected_home_goals + expected_away_goals
  derived from model.p_home_win and LEAGUE_GAME_GOALS (6.0 default).

  Decompose:
    p_home_win -> expected goal differential D (NHL: D ~ 3 * (P-0.5))
    home_goals = (T + D) / 2
    away_goals = (T - D) / 2

  Difference distribution mean = D, variance = home_goals + away_goals.

  P(home -1.5) = P(diff >= 2) ~ 1 - Norm.CDF(1.5)
  P(away +1.5) = P(diff <= 1) ~ Norm.CDF(1.5)

STRONG_FAV_-1.5 at p in [0.40, 0.55]  (vs +150 book = 40% breakeven)
STRONG_DOG_+1.5 at p in [0.65, 0.80]  (vs -160 book = 61.5% breakeven)

Output: data/nhl_puck_line_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_puck_line_props.json")
LEAGUE_GAME_GOALS = 6.0


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


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


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
        matchup = g.get("matchup") or f"{g.get('away_team','')} @ {g.get('home_team','')}"
        p_home = _safe(g.get("p_home_win"), None)
        if p_home is None or p_home == 0.5: continue

        # NHL goal differential decomposition (lower-scoring than MLB, smaller scale)
        D = (p_home - 0.5) * 3.0  # NHL: about 3 goal range from 50/50 to dominant fav
        home_goals = max(1.5, (LEAGUE_GAME_GOALS + D) / 2)
        away_goals = max(1.5, (LEAGUE_GAME_GOALS - D) / 2)

        mean_diff = home_goals - away_goals
        sd_diff = math.sqrt(home_goals + away_goals)

        # P(home -1.5 covers) = P(home_goals - away_goals >= 2)
        # continuity-corrected to 1.5 threshold
        if p_home > 0.5:
            fav_side = "HOME"; dog_side = "AWAY"
            z_fav = (1.5 - mean_diff) / sd_diff
            p_fav_minus = 1 - _norm_cdf(z_fav)
            p_dog_plus = _norm_cdf(z_fav)
        else:
            fav_side = "AWAY"; dog_side = "HOME"
            z_fav = (-1.5 - mean_diff) / sd_diff
            p_fav_minus = _norm_cdf(z_fav)
            p_dog_plus = 1 - p_fav_minus

        edge_class = "NONE"
        best_market = None
        if 0.40 <= p_fav_minus <= 0.55:
            edge_class = f"STRONG_{fav_side}_-1.5"
            best_market = {"market": f"{fav_side}_MINUS_1.5", "p": round(p_fav_minus, 3),
                           "fair_odds": _american(p_fav_minus)}
        elif 0.65 <= p_dog_plus <= 0.80:
            edge_class = f"STRONG_{dog_side}_+1.5"
            best_market = {"market": f"{dog_side}_PLUS_1.5", "p": round(p_dog_plus, 3),
                           "fair_odds": _american(p_dog_plus)}

        rows.append({
            "matchup": matchup,
            "fav_side": fav_side,
            "dog_side": dog_side,
            "p_home_win": round(p_home, 3),
            "home_goals_expected": round(home_goals, 2),
            "away_goals_expected": round(away_goals, 2),
            "expected_diff": round(mean_diff, 2),
            "p_fav_minus_1_5": round(p_fav_minus, 3),
            "p_dog_plus_1_5": round(p_dog_plus, 3),
            "fair_fav_minus_odds": _american(p_fav_minus),
            "fair_dog_plus_odds": _american(p_dog_plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]
    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "NHL Skellam approximation. D = (p_home_win - 0.5) * 3.0 (NHL "
                       "goal range narrower than MLB). STRONG_FAV_-1.5 p in [0.40, 0.55] "
                       "(vs +150 book), STRONG_DOG_+1.5 p in [0.65, 0.80] (vs -160).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[puck-line] {o['n_games']} games, {o['n_strong_edges']} strong edges -> {OUT}")
    for r in o['rows']:
        print(f"  {r['matchup']} p_fav-1.5={r['p_fav_minus_1_5']:.3f} p_dog+1.5={r['p_dog_plus_1_5']:.3f} edge={r['edge_class']}")
