"""
EdgeStat -- MLB run-line (spread) edge detector.

Standard MLB run-line is -1.5 / +1.5. The favorite must win by 2+ to
cover; the underdog covers if losing by 1 or winning outright.

Method:
   Decompose model fair_total into per-team Poisson lambdas (same as
   mlb_team_total_edges):
     diff = T * (P - 0.5) * 1.6
     home_lam = (T + diff) / 2
     away_lam = (T - diff) / 2

   Simulate via Poisson convolution:
     P(home_score - away_score >= 2)  -- home -1.5 covers
     P(home_score - away_score <= -2) -- away -1.5 covers
     P(|diff| <= 1)                   -- +1.5 wins for whoever's down

Output: data/mlb_run_line_edges.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_run_line_edges.json")

DIFF_SCALAR = 1.6
MAX_RUNS = 20   # truncate Poisson sum at 20 runs per team


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _spread_probs(home_lam, away_lam):
    """Return (p_home_minus_15, p_away_minus_15, p_home_plus_15, p_away_plus_15)."""
    p_home_by_2_plus = 0.0
    p_away_by_2_plus = 0.0
    p_home_win_or_tie_by_1 = 0.0
    p_away_win_or_tie_by_1 = 0.0
    for h in range(MAX_RUNS + 1):
        for a in range(MAX_RUNS + 1):
            p = _poisson_pmf(h, home_lam) * _poisson_pmf(a, away_lam)
            diff = h - a   # home minus away
            if diff >= 2: p_home_by_2_plus += p
            if diff <= -2: p_away_by_2_plus += p
            if diff >= -1: p_home_win_or_tie_by_1 += p   # home +1.5 (covers if loses by <=1 or wins)
            if diff <= 1: p_away_win_or_tie_by_1 += p   # away +1.5
    return (p_home_by_2_plus, p_away_by_2_plus,
            p_home_win_or_tie_by_1, p_away_win_or_tie_by_1)


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    games_out: List[Dict[str, Any]] = []
    all_picks: List[Dict[str, Any]] = []

    for g in (today.get("games") or []):
        model = g.get("model") or {}
        T = model.get("fair_total")
        P = model.get("p_home_win")
        if not T or not P: continue

        D = T * (P - 0.5) * DIFF_SCALAR
        home_lam = max(1.5, (T + D) / 2)
        away_lam = max(1.5, (T - D) / 2)

        p_home_15, p_away_15, p_home_plus15, p_away_plus15 = _spread_probs(home_lam, away_lam)
        mu = g.get("matchup")

        rec = {
            "matchup": mu,
            "home_lambda": round(home_lam, 2),
            "away_lambda": round(away_lam, 2),
            "p_home_minus_1_5": round(p_home_15, 4),
            "p_away_minus_1_5": round(p_away_15, 4),
            "p_home_plus_1_5": round(p_home_plus15, 4),
            "p_away_plus_1_5": round(p_away_plus15, 4),
            "fair_home_rl_american": _american(p_home_15),
            "fair_away_rl_american": _american(p_away_15),
            "fair_home_plus_rl_american": _american(p_home_plus15),
            "fair_away_plus_rl_american": _american(p_away_plus15),
        }
        games_out.append(rec)

        # Surface sweet-spot picks (50-80% probability range)
        for side, mkt, p, fair in (
            ("HOME -1.5", "HOME_runline_minus_1_5", p_home_15, _american(p_home_15)),
            ("AWAY -1.5", "AWAY_runline_minus_1_5", p_away_15, _american(p_away_15)),
            ("HOME +1.5", "HOME_runline_plus_1_5", p_home_plus15, _american(p_home_plus15)),
            ("AWAY +1.5", "AWAY_runline_plus_1_5", p_away_plus15, _american(p_away_plus15)),
        ):
            if 0.55 <= p <= 0.85:
                all_picks.append({
                    "matchup": mu, "side": side, "market": mkt,
                    "prob": p, "fair": fair,
                })

    all_picks.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "n_picks": len(all_picks),
        "method": ("Poisson convolution on per-team implied runs. P(spread "
                    "covers) computed exactly via the joint distribution of "
                    "home_runs and away_runs."),
        "top_picks": all_picks[:15],
        "games": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB run-line edges: {p['n_games']} games, {p['n_picks']} picks")
    print(f"\n  Top 8 run-line picks:")
    for x in p["top_picks"][:8]:
        print(f"    {x['matchup'][:30]:30s} {x['side']:12s} p={x['prob']*100:.0f}% (fair {x['fair']})")
