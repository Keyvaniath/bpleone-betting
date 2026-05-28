"""
EdgeStat -- NBA player points distribution bands.

Pure-model (no book line). Takes each player's projected points mean and
sigma (from nba_player_points_props) and builds the alt-line probability
ladder via a Normal scoring model:

  P(pts >= line) for a spread of half-point lines around the projection
  floor / median / ceiling = 15th / 50th / 85th percentile
  coin_flip_line  = highest .5 line with P(over) >= 0.50
  confident_line  = highest .5 line with P(over) >= 0.65

NBA analog of the pitcher K-distribution module. Fires even when the
book feed is down, anchoring points alt-line leans to the model.

Output: data/nba_player_points_distribution_bands.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_points_distribution_bands.json")


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


def _p_over(line: float, mu: float, sigma: float) -> float:
    """P(X >= line) for Normal(mu, sigma)."""
    if sigma <= 0: return 1.0 if mu >= line else 0.0
    z = (line - mu) / (sigma * math.sqrt(2.0))
    return max(0.0, min(1.0, 0.5 * (1.0 - math.erf(z))))


def _quantile(q: float, mu: float, sigma: float) -> float:
    """Inverse-normal quantile via rational approximation (Acklam)."""
    if sigma <= 0: return mu
    # Acklam's inverse normal CDF
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if q < plow:
        t = math.sqrt(-2 * math.log(q))
        z = (((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / \
            ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
    elif q <= phigh:
        t = q - 0.5; r = t*t
        z = (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*t / \
            (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    else:
        t = math.sqrt(-2 * math.log(1 - q))
        z = -(((((c[0]*t+c[1])*t+c[2])*t+c[3])*t+c[4])*t+c[5]) / \
            ((((d[0]*t+d[1])*t+d[2])*t+d[3])*t+1)
    return mu + sigma * z


def run() -> Dict[str, Any]:
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))

    rows: List[Dict[str, Any]] = []
    for r in (pts.get("rows") or []):
        if not isinstance(r, dict): continue
        mu = _safe(r.get("projected_pts"))
        sigma = _safe(r.get("sigma"))
        if mu <= 0 or sigma <= 0: continue

        base = round(mu)
        # Half-point alt lines spanning roughly +/- 1.3 sigma around the mean
        lines = [base - 6.5, base - 4.5, base - 2.5, base - 0.5,
                 base + 1.5, base + 3.5, base + 5.5]
        ladder = {f"over_{ln}": round(_p_over(ln, mu, sigma), 3)
                  for ln in lines if ln > 0}

        coin_flip = 0.0
        confident = 0.0
        ln = base - 8.5
        while ln <= base + 8.5:
            if ln > 0:
                p = _p_over(ln, mu, sigma)
                if p >= 0.50: coin_flip = ln
                if p >= 0.65: confident = ln
            ln += 1.0

        rows.append({
            "player": r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "projected_pts": round(mu, 1),
            "sigma": round(sigma, 2),
            "floor_pts": round(_quantile(0.15, mu, sigma), 1),
            "median_pts": round(_quantile(0.50, mu, sigma), 1),
            "ceiling_pts": round(_quantile(0.85, mu, sigma), 1),
            "alt_ladder": ladder,
            "coin_flip_line": coin_flip,
            "confident_over_line": confident,
            "lean": f"PTS OVER {confident}" if confident else "no confident points edge",
        })

    rows.sort(key=lambda r: -r["projected_pts"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "method_note": "Normal(projected_pts, sigma) points model from "
                       "nba_player_points_props. Emits P(pts>=line) ladder over a "
                       "spread of half-point lines, floor/median/ceiling (15/50/85 "
                       "pctile), coin_flip_line (P>=.50) and confident_over_line "
                       "(P>=.65). Odds-independent NBA analog of the pitcher "
                       "K-distribution bands.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pts-distro] {o['n_players']} players laddered -> {OUT}")
