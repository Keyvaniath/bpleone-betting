"""
EdgeStat -- Run-Line (-1.5 / +1.5) projections.

For each game, derives fair run-line probabilities from the existing model
output (p_home_win + fair_total). Math:

  Run differential = HomeRuns - AwayRuns
  Treated as Normal(mean_margin, sqrt(total)) with continuity correction.
  Given p_home_win = P(margin > 0), back out mean_margin via inverse normal.
  Then compute P(margin >= 2) for home -1.5 and P(margin <= -2) for home +1.5.

Output: data/run_line.json with fair prices for both sides per game.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "run_line.json")


def _phi(z: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _phi_inv(p: float) -> float:
    """Inverse standard normal CDF (Acklam approximation)."""
    if p <= 0:
        return -10.0
    if p >= 1:
        return 10.0
    # Rational approximation -- accuracy to ~1e-7
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
          1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
          6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


def _fair_american(prob: float) -> int:
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return -int(round(prob / (1 - prob) * 100))
    return int(round((1 - prob) / prob * 100))


def project_run_line(p_home_win: float, fair_total: float) -> Dict[str, Any]:
    """Return run-line probabilities + fair prices.

    Uses Normal approximation to the Skellam margin distribution. Continuity
    correction (0.5) since we're modeling discrete integer margins.
    """
    if fair_total <= 0 or p_home_win is None:
        return {}
    sd = math.sqrt(fair_total)
    # z such that Phi(z) = p_home_win  ->  z = phi_inv(p_home_win)
    # Continuity-corrected: P(margin > 0) = P(margin >= 1) ~ 1 - Phi((0.5 - mean) / sd)
    # so mean = 0.5 - phi_inv(1 - p_home_win) * sd
    z_win = _phi_inv(1 - p_home_win)
    mean_margin = 0.5 - z_win * sd
    # P(home wins by 2+) = P(margin >= 2) ~ 1 - Phi((1.5 - mean) / sd)
    p_home_cover = 1 - _phi((1.5 - mean_margin) / sd)
    # P(home wins by 1 or 0 or loses) = P(margin <= 1) ~ Phi((1.5 - mean) / sd)
    # P(home +1.5 covers) = P(margin >= -1) ~ 1 - Phi((-0.5 - mean) / sd)
    p_home_plus_15 = 1 - _phi((-0.5 - mean_margin) / sd)
    # Mirror for away
    p_away_cover = 1 - p_home_plus_15
    p_away_plus_15 = 1 - p_home_cover
    return {
        "mean_margin": round(mean_margin, 2),
        "total_used": round(fair_total, 2),
        "p_home_minus_15": round(p_home_cover, 4),
        "p_home_plus_15": round(p_home_plus_15, 4),
        "p_away_minus_15": round(p_away_cover, 4),
        "p_away_plus_15": round(p_away_plus_15, 4),
        "fair_home_minus_15": _fair_american(p_home_cover),
        "fair_home_plus_15": _fair_american(p_home_plus_15),
        "fair_away_minus_15": _fair_american(p_away_cover),
        "fair_away_plus_15": _fair_american(p_away_plus_15),
    }


def build_all() -> Dict[str, Any]:
    today_path = os.path.join(DATA_DIR, "today.json")
    if not os.path.exists(today_path):
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "warning": "today.json missing", "games": []}
    with open(today_path) as f:
        today = json.load(f)
    out_games = []
    for g in today.get("games", []):
        mod = g.get("model") or {}
        rl = project_run_line(mod.get("p_home_win"), mod.get("fair_total"))
        if rl:
            out_games.append({
                "matchup": g.get("matchup"),
                "time": g.get("time"),
                **rl,
            })
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
    }


def write_run_line(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote run_line -> {path}")
    print(f"  Games projected: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        print(f"  {g['matchup']:14} | margin {g['mean_margin']:+5.2f} | "
              f"home -1.5: {g['p_home_minus_15']:.3f} (fair {g['fair_home_minus_15']:+d}) | "
              f"away +1.5: {g['p_away_plus_15']:.3f} (fair {g['fair_away_plus_15']:+d})")


if __name__ == "__main__":
    write_run_line(build_all())
