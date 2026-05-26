"""
EdgeStat -- MLB game run difference props (team to win by N+ runs).

DK alt: 'Team to win by 2+ runs' / 'win by 3+ runs'.

Method:
  Skellam approximation: D = home_runs - away_runs.
  D has mean μ = lam_home - lam_away
        variance σ² = lam_home + lam_away
  Normal CDF on D (continuity correction).
  P(home wins by N+) = P(D >= N) = 1 - Phi((N - 0.5 - μ) / σ)

  Common book markets: -1.5 / +1.5 (covered by run_line module),
  and 2+, 3+ alt margins.

Output: data/mlb_game_run_diff_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_run_diff_props.json")


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


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _p_diff_at_least(N: int, mu: float, sigma: float) -> float:
    """P(home_diff >= N) via Normal CDF with continuity correction."""
    if sigma <= 0: return 1.0 if mu >= N else 0.0
    z = (N - 0.5 - mu) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))

    by_matchup: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        m = r.get("matchup")
        if not m: continue
        proj = _safe(r.get("model_expected_runs_anchored"))
        entry = by_matchup.setdefault(m, {"matchup": m})
        if r.get("side") == "HOME":
            entry["home_team"] = r.get("team")
            entry["home_lam"] = proj
        elif r.get("side") == "AWAY":
            entry["away_team"] = r.get("team")
            entry["away_lam"] = proj

    rows: List[Dict[str, Any]] = []
    for m, g in by_matchup.items():
        lam_h = _safe(g.get("home_lam"))
        lam_a = _safe(g.get("away_lam"))
        if lam_h <= 0 or lam_a <= 0: continue

        mu = lam_h - lam_a  # expected home margin
        sigma = math.sqrt(lam_h + lam_a)

        # Compute home win-by-N+ probabilities
        p_home_win_by_2plus = _p_diff_at_least(2, mu, sigma)
        p_home_win_by_3plus = _p_diff_at_least(3, mu, sigma)
        p_home_win_by_4plus = _p_diff_at_least(4, mu, sigma)
        p_home_win = _p_diff_at_least(1, mu, sigma)
        # Away wins by N+: flip mu
        p_away_win_by_2plus = _p_diff_at_least(2, -mu, sigma)
        p_away_win_by_3plus = _p_diff_at_least(3, -mu, sigma)

        # STRONG only when meaningful asymmetry: |mu| >= 0.3 runs
        edge_class = "NONE"
        best_market = None
        if abs(mu) >= 0.3:
            # Home win by 2+
            if 0.32 <= p_home_win_by_2plus <= 0.48:
                edge_class = "STRONG_HOME_WIN_BY_2"
                best_market = {"market": "HOME_WIN_BY_2PLUS",
                               "p": round(p_home_win_by_2plus, 3),
                               "fair_odds": _american(p_home_win_by_2plus)}
            elif 0.32 <= p_away_win_by_2plus <= 0.48:
                edge_class = "STRONG_AWAY_WIN_BY_2"
                best_market = {"market": "AWAY_WIN_BY_2PLUS",
                               "p": round(p_away_win_by_2plus, 3),
                               "fair_odds": _american(p_away_win_by_2plus)}

        rows.append({
            "matchup": m,
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_lam": round(lam_h, 2),
            "away_lam": round(lam_a, 2),
            "expected_margin": round(mu, 2),
            "sigma": round(sigma, 2),
            "p_home_wins": round(p_home_win, 3),
            "p_home_win_by_2plus": round(p_home_win_by_2plus, 3),
            "p_home_win_by_3plus": round(p_home_win_by_3plus, 3),
            "p_home_win_by_4plus": round(p_home_win_by_4plus, 3),
            "p_away_win_by_2plus": round(p_away_win_by_2plus, 3),
            "p_away_win_by_3plus": round(p_away_win_by_3plus, 3),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -abs(r["expected_margin"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Skellam→Normal: margin D ~ N(lam_h - lam_a, sqrt(lam_h+lam_a)). "
                       "Surfaces win-by-2+/3+/4+ alt markets. STRONG when margin "
                       "asymmetry >= 0.3 runs AND p in [0.32, 0.48].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[run-diff] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
