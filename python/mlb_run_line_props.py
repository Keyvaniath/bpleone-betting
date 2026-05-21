"""
EdgeStat -- MLB run line (-1.5 / +1.5) prop projection.

Run line is the most common alternative to moneyline:
  Favorite -1.5: needs to win by 2+ runs   (typically +130 to +180)
  Underdog +1.5: loses by <2 OR wins      (typically -160 to -200)

Method:
  expected_home_runs and expected_away_runs derived from model total + p_home_win
  (same decomposition as mlb_team_total_edges).

  Treat home_runs and away_runs as independent Poisson — the difference
  follows a Skellam distribution. We approximate via Normal with:
    mean = home_runs - away_runs
    var  = home_runs + away_runs  (variance of difference of indep Poissons)
    sd   = sqrt(var)

  P(home -1.5 covers) = P(home - away >= 2) = 1 - Normal.CDF(1.5)
  P(away +1.5 covers) = P(home - away <= 1) = Normal.CDF(1.5)

Surface STRONG_YES when our prob >= breakeven by 5%+ over typical book.
Book breakeven for -150 dog +1.5 = 60%; for +160 fav -1.5 = 38.5%.

Output: data/mlb_run_line_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_run_line_props.json")


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
    today = _load(os.path.join(DATA_DIR, "today.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    # Index matchups for team names
    m_by_key = {}
    for g in (matchups.get("games") or []):
        k = g.get("matchup")
        if k: m_by_key[k] = g

    games = today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup")
        if not matchup: continue
        model = g.get("model") or {}
        T = _safe(model.get("fair_total"), 8.5)
        p_home = _safe(model.get("p_home_win"), None) or 0.5
        if p_home == 0.5 and not model.get("p_home_win"): continue

        # Empirical decomposition: D ≈ T * (P-0.5) * 1.6
        D = T * (p_home - 0.5) * 1.6
        home_runs = max(1.5, (T + D) / 2)
        away_runs = max(1.5, (T - D) / 2)

        # Skellam approximation via Normal
        mean_diff = home_runs - away_runs
        sd_diff = math.sqrt(home_runs + away_runs)

        # P(home covers -1.5) = P(home_runs - away_runs >= 2)
        # Continuity correction: use 1.5 as threshold for discrete >=2
        z = (1.5 - mean_diff) / sd_diff
        p_home_minus_15 = 1 - _norm_cdf(z)
        # P(away covers +1.5) = P(home - away <= 1)
        z2 = (1.5 - mean_diff) / sd_diff
        p_away_plus_15 = _norm_cdf(z2)
        # Sanity: these sum to 1
        # (they do, since P(home-away>=2) + P(home-away<=1) = 1)

        # Decide favorite / underdog side
        if p_home > 0.5:
            # Home is favorite, would be -1.5
            fav_side = "HOME"
            dog_side = "AWAY"
            p_fav_minus = p_home_minus_15
            p_dog_plus = p_away_plus_15
        else:
            # Away is favorite, decompose mirror
            fav_side = "AWAY"
            dog_side = "HOME"
            p_fav_minus = 1 - p_home_minus_15  # P(away wins by 2+) = P(home_runs - away_runs <= -2)
            # which we get from P(diff <= -2): Normal(diff <= -1.5) for continuity
            z3 = (-1.5 - mean_diff) / sd_diff
            p_fav_minus = _norm_cdf(z3)
            p_dog_plus = 1 - p_fav_minus

        edge_class = "NONE"
        best_market = None
        # STRONG_YES favorite -1.5 at p >= 0.45 (typical +130 fav-line = 43.5%)
        if 0.45 <= p_fav_minus <= 0.65:
            edge_class = f"STRONG_{fav_side}_-1.5"
            best_market = {"market": f"{fav_side}_MINUS_1.5", "p": round(p_fav_minus, 3),
                           "fair_odds": _american(p_fav_minus)}
        # STRONG_YES dog +1.5 at p >= 0.65 (typical -150 dog-line = 60%)
        elif p_dog_plus >= 0.65 and p_dog_plus <= 0.85:
            edge_class = f"STRONG_{dog_side}_+1.5"
            best_market = {"market": f"{dog_side}_PLUS_1.5", "p": round(p_dog_plus, 3),
                           "fair_odds": _american(p_dog_plus)}

        rows.append({
            "matchup": matchup,
            "fav_side": fav_side,
            "dog_side": dog_side,
            "p_home_win": round(p_home, 3),
            "home_runs_implied": round(home_runs, 2),
            "away_runs_implied": round(away_runs, 2),
            "expected_diff": round(mean_diff, 2),
            "sd_diff": round(sd_diff, 2),
            "p_fav_minus_1_5": round(p_fav_minus, 3),
            "p_dog_plus_1_5": round(p_dog_plus, 3),
            "fair_fav_minus_odds": _american(p_fav_minus),
            "fair_dog_plus_odds": _american(p_dog_plus),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_dog_plus_1_5"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Skellam approx via Normal on (home_runs - away_runs). "
                       "Decompose fair_total + p_home_win -> per-team expected runs. "
                       "STRONG_FAV_-1.5 at p in [0.45, 0.65]; STRONG_DOG_+1.5 at p in [0.65, 0.85].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[run-line] {o['n_games']} games, {o['n_strong_edges']} strong edges -> {OUT}")
    for r in o['strong_edges']:
        print(f"  {r['matchup']:25s} {r['edge_class']:25s} "
              f"p_fav-1.5={r['p_fav_minus_1_5']:.3f} p_dog+1.5={r['p_dog_plus_1_5']:.3f}")
