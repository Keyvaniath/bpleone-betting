"""
EdgeStat -- NHL game total shots on goal O/U prop (combined both teams).

DK alt: 'Total SOG in game over/under N.5' (common lines 60.5, 63.5, 66.5).
League avg: ~60 combined SOG per NHL game.

Method:
  combined_SOG = both teams' team_SOG_per_game (~30 each).
  Adjust for:
    - Game pace (lookup from team_pace if available)
    - Opp goalie sv% (no impact on SOG, just on saves)
    - Playoff intensity (-2 SOG, defensive style)

  STRONG-gated on deviation >= 3 SOG from league baseline (60).

Output: data/nhl_game_total_sog.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_game_total_sog.json")

LEAGUE_SOG_PER_TEAM = 30.0
LEAGUE_TOTAL_SOG = 60.0


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


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue
        matchup = f"{away} @ {home}"

        # Pace adjustment from team_pace if available
        home_sog = _safe(g.get("home_sog_per_game"), LEAGUE_SOG_PER_TEAM)
        away_sog = _safe(g.get("away_sog_per_game"), LEAGUE_SOG_PER_TEAM)
        is_playoff = "playoff" in (g.get("series_name") or "").lower() or bool(g.get("playoffs"))
        playoff_adj = -2 if is_playoff else 0

        total_sog = home_sog + away_sog + playoff_adj
        sigma = max(5.5, math.sqrt(total_sog) * 1.1)

        deviates = abs(total_sog - LEAGUE_TOTAL_SOG) >= 3.0
        best_edge = 0.0
        best_market = None
        edge_class = "NONE"
        if deviates:
            base_line = round(total_sog * 2) / 2
            for offset in (-0.5, 0.5):
                line = base_line + offset
                if line < 40 or line > 90: continue
                p_o = _p_over(total_sog, sigma, line)
                p_u = 1 - p_o
                for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                    if 0.58 <= p <= 0.68:
                        edge_amt = p - 0.524
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {"market": f"SOG_TOTAL_{direction}_{line}",
                                           "line": line, "direction": direction,
                                           "p": round(p, 3),
                                           "fair_odds": _american(p)}
                            edge_class = "STRONG"

        rows.append({
            "matchup": matchup,
            "home_sog_per_game": round(home_sog, 1),
            "away_sog_per_game": round(away_sog, 1),
            "is_playoff": is_playoff,
            "playoff_adj": playoff_adj,
            "total_expected_sog": round(total_sog, 2),
            "sigma": round(sigma, 2),
            "best_market": best_market,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: -r["total_expected_sog"])
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Combined SOG = home + away team SOG/game + playoff_adj. "
                       "Normal CDF, sigma sqrt(lambda)*1.1. STRONG-gated on deviation "
                       ">= 3 from league baseline (60 SOG).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-sog-total] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
