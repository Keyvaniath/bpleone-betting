"""
EdgeStat -- Tennis total games (O/U) prop projections.

Common DK lines: O/U 21.5, 22.5, 23.5 games (best-of-3 matches).
Best-of-5 has different distribution but rare outside Grand Slams men's.

Method:
  ELO difference -> game-by-game competitiveness factor
  Close match (|elo_diff| < 50): ~24 games avg (set scores like 7-5, 6-4)
  Lopsided (|elo_diff| > 200): ~17-19 games avg (6-2, 6-3 sets)
  Surface factor: clay = +1.5 (longer rallies), grass = -1.0 (faster), hard = 0

Total games for best-of-3:
  Mean = 22.0 - 0.025 * |elo_diff| + surface_adj
  Sigma = 3.5

Output: data/tennis_total_games_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_total_games_props.json")

SIGMA_GAMES_BO3 = 3.5
SIGMA_GAMES_BO5 = 7.0

SURFACE_ADJ = {"clay": 1.5, "grass": -1.0, "hard": 0.0}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    matches = state.get("rows") or []  # use match-win module's already-built ELO calcs

    rows: List[Dict[str, Any]] = []

    for m in matches:
        elo1 = m.get("p1_elo")
        elo2 = m.get("p2_elo")
        if not elo1 or not elo2: continue
        elo_diff = abs(elo1 - elo2)
        surface = m.get("surface", "hard")
        surface_adj = SURFACE_ADJ.get(surface, 0.0)
        format_bo = m.get("format") or "bo3"  # best of 3 default

        # Expected total games
        if format_bo == "bo5":
            expected_games = 35.0 - 0.05 * elo_diff + surface_adj * 2
            sigma = SIGMA_GAMES_BO5
        else:
            expected_games = 22.0 - 0.025 * elo_diff + surface_adj
            sigma = SIGMA_GAMES_BO3

        # Evaluate nearest 1.0 line within 4.0 of projection
        edge_class = "NONE"
        best_market = None
        base_line = round(expected_games) + 0.5
        for line_int in (base_line - 3, base_line - 2, base_line - 1, base_line, base_line + 1, base_line + 2, base_line + 3):
            line = line_int
            if line < 14.5 or line > 50.5: continue
            if abs(expected_games - line) > 4.0: continue
            p_over = _p_over(expected_games, sigma, line)
            p_under = 1 - p_over
            if 0.62 <= p_over <= 0.72:
                if not best_market or p_over > best_market["p"]:
                    edge_class = "STRONG_OVER"
                    best_market = {"market": f"TOTAL_GAMES_OVER_{line}", "p": round(p_over, 3),
                                   "fair_odds": _american(p_over), "line": line}
            elif 0.62 <= p_under <= 0.72:
                if not best_market or p_under > best_market["p"]:
                    edge_class = "STRONG_UNDER"
                    best_market = {"market": f"TOTAL_GAMES_UNDER_{line}", "p": round(p_under, 3),
                                   "fair_odds": _american(p_under), "line": line}

        rows.append({
            "matchup": m.get("matchup"),
            "surface": surface,
            "format": format_bo,
            "elo_diff": elo_diff,
            "expected_total_games": round(expected_games, 1),
            "sigma": sigma,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Tennis total games (bo3) = 22 - 0.025*|elo_diff| + surface_adj. "
                       "Normal CDF, sigma 3.5 (bo3) / 7.0 (bo5). STRONG = 10%+ edge.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-games] {o['n_matches']} matches, {o['n_strong_edges']} strong edges -> {OUT}")
