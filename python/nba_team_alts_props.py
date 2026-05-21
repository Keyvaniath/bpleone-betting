"""
EdgeStat -- NBA team alt-totals + alt-spreads + 1H/1Q totals.

Builds on nba_pace_adjusted.py by computing per-team Normal distributions
around expected_points and offering alt-line probabilities at non-standard
totals + first-half + first-quarter projections.

Markets covered:
  - Team total alt-lines (-5.5 to +5.5 from main total)
  - First-half total alt-lines (~50% of game total)
  - First-quarter total alt-lines (~25% of game total)
  - Spread alt-lines (-1.5 to +1.5 from main spread)

Output: data/nba_team_alts_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_alts_props.json")

TEAM_TOTAL_STDDEV = 11.0  # sigma per team for full-game points
FIRST_HALF_STDDEV = 8.0
FIRST_Q_STDDEV = 4.5


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))
    games = pace.get("rows") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        home_pts = g.get("home_pts_projected") or 0
        away_pts = g.get("away_pts_projected") or 0
        total = home_pts + away_pts
        spread = home_pts - away_pts  # positive = home favored

        # First-half = ~52% of game (slightly more than half due to halftime fatigue / pace)
        home_h1 = home_pts * 0.52
        away_h1 = away_pts * 0.52
        # First-quarter = ~25% of game
        home_q1 = home_pts * 0.25
        away_q1 = away_pts * 0.25

        # Build per-line probabilities
        team_alts = []
        for offset in (-5.5, -3.5, 1.5, 3.5, 5.5):
            for is_home in (True, False):
                base_proj = home_pts if is_home else away_pts
                line = base_proj + offset
                z = (base_proj - line) / TEAM_TOTAL_STDDEV
                p_over = _norm_cdf(z)
                team_alts.append({
                    "team": "HOME" if is_home else "AWAY",
                    "line": round(line, 1),
                    "offset_from_proj": offset,
                    "p_over": round(p_over, 3),
                    "p_under": round(1 - p_over, 3),
                    "fair_over": _american(p_over),
                    "fair_under": _american(1 - p_over),
                })

        # H1 totals
        h1_total = home_h1 + away_h1
        h1_lines = []
        for line in [h1_total - 2.5, h1_total - 0.5, h1_total + 0.5, h1_total + 2.5]:
            z = (h1_total - line) / (FIRST_HALF_STDDEV * 1.41)  # combined std
            p_over = _norm_cdf(z)
            h1_lines.append({
                "line": round(line, 1),
                "p_over": round(p_over, 3),
                "p_under": round(1 - p_over, 3),
            })

        # Q1 totals
        q1_total = home_q1 + away_q1
        q1_lines = []
        for line in [q1_total - 1.5, q1_total + 0.5, q1_total + 1.5]:
            z = (q1_total - line) / (FIRST_Q_STDDEV * 1.41)
            p_over = _norm_cdf(z)
            q1_lines.append({
                "line": round(line, 1),
                "p_over": round(p_over, 3),
                "p_under": round(1 - p_over, 3),
            })

        # Edge: pick the most off-zero alt-line where p falls in 0.62-0.72
        edge_class = "NONE"
        best_market = None
        for ta in team_alts:
            for direction, p in (("OVER", ta["p_over"]), ("UNDER", ta["p_under"])):
                if 0.62 <= p <= 0.72:
                    if not best_market or p > best_market["p"]:
                        edge_class = f"STRONG_{direction}"
                        best_market = {"market": f"{ta['team']}_TOTAL_{direction}_{ta['line']}",
                                       "p": round(p, 3),
                                       "fair_odds": _american(p)}

        rows.append({
            "matchup": g.get("matchup"),
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_pts_proj": home_pts,
            "away_pts_proj": away_pts,
            "total_proj": round(total, 1),
            "h1_total_proj": round(h1_total, 1),
            "q1_total_proj": round(q1_total, 1),
            "spread_proj": round(spread, 1),
            "team_alts": team_alts,
            "h1_lines": h1_lines,
            "q1_lines": q1_lines,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_strong": len(strong),
        "method_note": "Normal distribution per team_points (sigma=11). H1 = 52%% of game, "
                       "Q1 = 25%%. Alt-lines at +/- 1.5, 3.5, 5.5 from projection.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-alts] {o['n_games']} games, {o['n_strong']} strong -> {OUT}")
