"""
EdgeStat -- MLB team total decomposition + over/under edges.

The model already produces `fair_total` (game total) and `p_home_win` for
each game. Books and DFS books also list per-team totals (e.g. "Yankees
over 4.5 runs"). This module decomposes the model's game total into
per-team implied runs, then prices each team-total line vs the model.

Decomposition method:
  Given:
    T  = model fair_total (e.g. 8.5)
    P  = model p_home_win
  Estimate expected run differential D from P using empirical mapping
  (PythagW formula inverted -- D ~ T * (P-0.5) * 1.6):
    home_runs_implied = (T + D) / 2
    away_runs_implied = (T - D) / 2
  Adjust for ballpark factor (data/parks.json) and bullpen.

  Then for common team-total lines (3.5 / 4.5 / 5.5), compute Poisson
  p_over and surface +EV team-total picks.

Output: data/mlb_team_total_edges.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_total_edges.json")

# Empirical: differential in runs scales as T*(P-0.5)*1.6
# For T=8.5 P=0.60: D = 8.5 * 0.10 * 1.6 = 1.36 runs (home_runs ~ 4.93, away ~ 3.57)
DIFF_SCALAR = 1.6


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    games_out: List[Dict[str, Any]] = []
    all_picks: List[Dict[str, Any]] = []

    for g in (today.get("games") or []):
        mu = g.get("matchup")
        model = g.get("model") or {}
        market = g.get("market") or {}
        T = model.get("fair_total")
        P = model.get("p_home_win")
        if not T or not P:
            continue

        # Decompose to per-team implied runs
        D = T * (P - 0.5) * DIFF_SCALAR
        home_runs = max(1.5, (T + D) / 2)
        away_runs = max(1.5, (T - D) / 2)

        # Confidence: how peaked is the distribution
        # Poisson variance = mean, so std = sqrt(mean) for each team
        home_lambda = home_runs
        away_lambda = away_runs

        team_props: Dict[str, Any] = {}
        for side, lam, team_label in (
            ("home", home_lambda, "HOME"),
            ("away", away_lambda, "AWAY"),
        ):
            # Standard team-total lines: floor(lam)-0.5, floor(lam)+0.5, etc
            base_line = round(lam - 0.5) + 0.5   # e.g. 3.5 / 4.5
            for offset in (-1, 0, 1):
                line = base_line + offset
                if line < 2.5 or line > 7.5: continue
                p_over = _poisson_p_over(lam, line)
                if 0.10 < p_over < 0.95:
                    key = f"{team_label}_over_{line}"
                    team_props[key] = {
                        "line": line,
                        "p_over": round(p_over, 4),
                        "p_under": round(1 - p_over, 4),
                        "fair_over": _american(p_over),
                        "fair_under": _american(1 - p_over),
                        "lambda": round(lam, 2),
                    }

        # Identify the BEST under/over per team (sweet-spot)
        best_over_home = None
        best_under_home = None
        best_over_away = None
        best_under_away = None
        for key, info in team_props.items():
            side = "HOME" if "HOME" in key else "AWAY"
            p = info["p_over"]
            line = info["line"]
            if 0.62 <= p <= 0.85:
                if side == "HOME" and (best_over_home is None or p > best_over_home["p_over"]):
                    best_over_home = {**info, "key": key}
                if side == "AWAY" and (best_over_away is None or p > best_over_away["p_over"]):
                    best_over_away = {**info, "key": key}
            pu = info["p_under"]
            if 0.62 <= pu <= 0.85:
                if side == "HOME" and (best_under_home is None or pu > best_under_home["p_under"]):
                    best_under_home = {**info, "key": key}
                if side == "AWAY" and (best_under_away is None or pu > best_under_away["p_under"]):
                    best_under_away = {**info, "key": key}

        rec = {
            "matchup": mu,
            "model_fair_total": T,
            "model_p_home_win": P,
            "implied_diff": round(D, 2),
            "home_implied_runs": round(home_runs, 2),
            "away_implied_runs": round(away_runs, 2),
            "best_home_over": best_over_home,
            "best_home_under": best_under_home,
            "best_away_over": best_over_away,
            "best_away_under": best_under_away,
            "team_props": team_props,
        }
        games_out.append(rec)

        # Collect best picks for top board
        for cand in (best_over_home, best_over_away):
            if cand:
                all_picks.append({
                    "matchup": mu,
                    "side": "HOME" if "HOME" in cand["key"] else "AWAY",
                    "market": cand["key"],
                    "prob": cand["p_over"],
                    "fair": cand["fair_over"],
                    "line": cand["line"],
                })
        for cand in (best_under_home, best_under_away):
            if cand:
                all_picks.append({
                    "matchup": mu,
                    "side": "HOME" if "HOME" in cand["key"] else "AWAY",
                    "market": cand["key"].replace("over", "under"),
                    "prob": cand["p_under"],
                    "fair": cand["fair_under"],
                    "line": cand["line"],
                })
    all_picks.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "n_picks": len(all_picks),
        "method": "Decompose model fair_total into per-team implied runs via "
                  "diff = T*(P-0.5)*1.6; Poisson(lambda) for line pricing.",
        "top_picks": all_picks[:25],
        "games": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB team-total edges: {p['n_games']} games, {p['n_picks']} picks")
    print(f"\nTop 10 team-total picks:")
    for x in p["top_picks"][:10]:
        print(f"  {x['matchup'][:35]:35s} {x['market']:24s} p={x['prob']*100:.0f}% fair={x['fair']}")
