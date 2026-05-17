"""
EdgeStat -- KBO Poisson win-prob + total-runs model.

Same Poisson framework used for MLB, calibrated to KBO scoring environment
(slightly lower average runs/game ~9 vs MLB's ~9.2 in recent years).

For each game:
  - Compute expected runs per team (league avg adjusted by ELO + home factor)
  - Skellam-style P(home win) via Monte Carlo (50K runs simulation)
  - Total OVER/UNDER fair line via Poisson PMF

Self-learning: incorporates settled game results into rolling ELO via kbo_elo.json.

Output: data/kbo_props.json + data/kbo_elo.json
"""
from __future__ import annotations

import os
import json
import math
import random
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "kbo_state.json")
ELO_PATH = os.path.join(DATA_DIR, "kbo_elo.json")
OUT_PATH = os.path.join(DATA_DIR, "kbo_props.json")

KBO_AVG_RUNS_PER_TEAM = 4.7     # ~4.7 R/G/team (2023 KBO actual)
HOME_RUN_BONUS = 0.20           # +0.20 runs from home-field
K_FACTOR = 20
N_SIMS = 50000


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f:
        json.dump(payload, f, indent=2)


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _elo_winprob(elo_a: float, elo_b: float, hfa: float = 24) -> float:
    return 1 / (1 + 10 ** ((elo_b - (elo_a + hfa)) / 400))


def _expected_runs(elo_team: float, elo_opp: float, is_home: bool) -> float:
    """Convert ELO diff to expected runs above/below league average."""
    elo_diff = elo_team - elo_opp
    # 100 ELO diff = +0.4 runs lift (rough calibration from MLB analogy)
    delta = elo_diff / 250
    base = KBO_AVG_RUNS_PER_TEAM + delta
    if is_home:
        base += HOME_RUN_BONUS
    return max(1.5, base)


def _poisson_sample(mean: float) -> int:
    """Knuth Poisson sampler."""
    if mean <= 0:
        return 0
    L = math.exp(-mean)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def _simulate_game(home_lambda: float, away_lambda: float, n_sims: int) -> Dict[str, float]:
    home_wins = 0
    home_runs_total = 0
    away_runs_total = 0
    total_dist: Dict[int, int] = {}
    for _ in range(n_sims):
        h = _poisson_sample(home_lambda)
        a = _poisson_sample(away_lambda)
        # KBO games can tie (no extra innings beyond 12); treat as 0.5 each
        if h > a:
            home_wins += 1
        elif a > h:
            pass
        else:
            home_wins += 0.5
        home_runs_total += h
        away_runs_total += a
        total = h + a
        total_dist[total] = total_dist.get(total, 0) + 1
    p_home_win = home_wins / n_sims
    # Compute fair total via median of total_dist
    sorted_totals = sorted(total_dist.items())
    cdf = 0
    median_total = 0
    for total, count in sorted_totals:
        cdf += count
        if cdf >= n_sims / 2:
            median_total = total
            break
    return {
        "p_home_win": p_home_win,
        "expected_home_runs": home_runs_total / n_sims,
        "expected_away_runs": away_runs_total / n_sims,
        "median_total_runs": median_total,
    }


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    matches = state.get("matches") or []
    seed_elo = {s["team"]: s["elo_baseline"]
                for s in (state.get("standings_seed") or [])}
    elo_store = _load(ELO_PATH)
    elo: Dict[str, float] = dict(seed_elo)
    elo.update(elo_store.get("teams") or {})

    seen_ids = set(elo_store.get("processed_match_ids") or [])

    # Update ELO from any completed games
    today = dt.date.today().isoformat()
    for m in matches:
        if m.get("state") != "post":
            continue
        mid = f"{m.get('home_team')}|{m.get('away_team')}|{today}"
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        h, a = m["home_team"], m["away_team"]
        elo_h = elo.get(h, 1500)
        elo_a = elo.get(a, 1500)
        sh = m.get("home_score") or 0
        sa = m.get("away_score") or 0
        if sh + sa == 0:
            continue
        actual_h = 1.0 if sh > sa else 0.0 if sa > sh else 0.5
        expected_h = _elo_winprob(elo_h, elo_a)
        margin = abs(sh - sa)
        margin_mult = 1.0 + math.log1p(margin) * 0.25
        delta = K_FACTOR * margin_mult * (actual_h - expected_h)
        elo[h] = elo_h + delta
        elo[a] = elo_a - delta

    _save(ELO_PATH, {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(elo),
        "teams": elo,
        "processed_match_ids": list(seen_ids)[-2000:],
    })

    # Pitcher matchup adjustments
    pitcher_adj = _load(os.path.join(DATA_DIR, "kbo_pitcher_adj.json"))
    adj_by_matchup = {a["matchup"]: a for a in (pitcher_adj.get("adjustments") or [])}

    random.seed(7)
    preds: List[Dict[str, Any]] = []
    for m in matches:
        h, a = m["home_team"], m["away_team"]
        elo_h = elo.get(h, 1500)
        elo_a = elo.get(a, 1500)
        home_lambda = _expected_runs(elo_h, elo_a, is_home=True)
        away_lambda = _expected_runs(elo_a, elo_h, is_home=False)

        # Apply starting-pitcher adjustment: home SP quality suppresses away_lambda
        adj_key = f"{a} @ {h}"
        adj = adj_by_matchup.get(adj_key) or {}
        sp_adjustment = None
        if adj:
            # home SP "runs against" adjustment applies to away_lambda
            away_lambda += adj.get("home_runs_against_adjustment", 0)
            home_lambda += adj.get("away_runs_against_adjustment", 0)
            away_lambda = max(1.5, away_lambda)
            home_lambda = max(1.5, home_lambda)
            sp_adjustment = adj.get("note")

        sim = _simulate_game(home_lambda, away_lambda, N_SIMS)
        p_home = sim["p_home_win"]
        median_total = sim["median_total_runs"]
        preds.append({
            **m,
            "elo_home": round(elo_h, 1),
            "elo_away": round(elo_a, 1),
            "expected_home_runs": round(sim["expected_home_runs"], 2),
            "expected_away_runs": round(sim["expected_away_runs"], 2),
            "model_total": median_total,
            "p_home_win": round(p_home, 4),
            "p_away_win": round(1 - p_home, 4),
            "fair_home_american": _american(p_home),
            "fair_away_american": _american(1 - p_home),
            "pitcher_matchup": sp_adjustment,
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(preds),
        "n_teams_rated": len(elo),
        "n_sims_per_game": N_SIMS,
        "predictions": preds,
    }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games']} KBO games ({p['n_sims_per_game']} sims/game)")
    for m in p["predictions"]:
        print(f"  {m['away_team']:18} @ {m['home_team']:18} "
              f"P(home)={m['p_home_win']*100:5.1f}% fair {m['fair_home_american']:+5d}/{m['fair_away_american']:+5d} "
              f"Total={m['model_total']:.1f}")
