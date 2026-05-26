"""
EdgeStat -- NHL game total saves O/U prop (combined both goalies).

DK alt: 'Total saves in game over/under N.5' (common lines 55.5, 60.5, 65.5).

Method:
  Combined expected saves across both goalies. Use individual saves
  projections from nhl_goalie_saves_props if available, else compute from
  team-level shots allowed:
    expected_total_saves = expected_shots_team_A_against +
                           expected_shots_team_B_against
                         ≈ 2 * 30 = 60 shots/game on goal league avg
                         * 0.910 league SV% = 54.6 saves total

  Normal CDF at typical 0.5-step lines. Combined sigma ~ sqrt(60) = 7.7.

  STRONG when 7%+ edge vs -110 book.

Output: data/nhl_game_total_saves.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_game_total_saves.json")

LEAGUE_SHOTS_PER_TEAM_GAME = 30.0
LEAGUE_SV_PCT = 0.910


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
    saves_props = _load(os.path.join(DATA_DIR, "nhl_goalie_saves_props.json"))
    saves_idx = {(r.get("matchup") or "") + "|" + (r.get("side") or ""): r
                 for r in (saves_props.get("rows") or [])
                 if isinstance(r, dict)}

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue
        matchup = f"{away} @ {home}"

        # Try goalie-saves projection first; fallback to league baseline
        home_g = saves_idx.get(f"{matchup}|HOME", {}) or saves_idx.get(f"{matchup}|home", {})
        away_g = saves_idx.get(f"{matchup}|AWAY", {}) or saves_idx.get(f"{matchup}|away", {})
        home_saves = _safe(home_g.get("expected_saves"),
                            LEAGUE_SHOTS_PER_TEAM_GAME * LEAGUE_SV_PCT)
        away_saves = _safe(away_g.get("expected_saves"),
                            LEAGUE_SHOTS_PER_TEAM_GAME * LEAGUE_SV_PCT)
        total_saves = home_saves + away_saves
        sigma = max(5.0, math.sqrt(total_saves) * 1.2)  # slight inflation

        # Find best edge at typical alt lines
        base_line = round(total_saves * 2) / 2
        edges: List[Dict[str, Any]] = []
        league_baseline = 54.6
        deviates = abs(total_saves - league_baseline) >= 2.0
        if deviates:
            for offset in (-1.5, -0.5, 0.5, 1.5):
                line = base_line + offset
                if line < 40 or line > 80: continue
                p_o = _p_over(total_saves, sigma, line)
                p_u = 1 - p_o
                for direction, p in (("OVER", p_o), ("UNDER", p_u)):
                    if 0.57 <= p <= 0.68:
                        edges.append({
                            "market": f"SAVES_TOTAL_{direction}_{line}",
                            "line": line, "direction": direction,
                            "p": round(p, 3),
                            "fair_odds": _american(p),
                        })

        best_edge = max(edges, key=lambda e: e["p"]) if edges else None
        edge_class = "STRONG" if best_edge else "NONE"

        rows.append({
            "matchup": matchup,
            "home_expected_saves": round(home_saves, 1),
            "away_expected_saves": round(away_saves, 1),
            "total_expected_saves": round(total_saves, 2),
            "sigma": round(sigma, 2),
            "best_market": best_edge,
            "edge_class": edge_class,
        })

    rows.sort(key=lambda r: -r["total_expected_saves"])
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Combined goalie saves = sum of expected_saves from "
                       "nhl_goalie_saves_props (or league baseline 54.6). Normal CDF, "
                       "sigma sqrt(lambda)*1.2. STRONG-gated on deviation >= 2.0 from "
                       "league baseline.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-saves] {o['n_games']} games, {o['n_strong_edges']} strong -> {OUT}")
