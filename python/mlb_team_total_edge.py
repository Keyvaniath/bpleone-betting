"""
EdgeStat -- MLB team total edge synthesizer.

Cross-references for each game-side:
  1) Lineup quality score (offense input from lineup_quality_index)
  2) Opposing pitcher edge composite (pitching input)
  3) Park run factor + weather (environment)
  4) Book team total line (target)

Produces directional lean OVER/UNDER for team total:
  - STRONG_OVER:  elite_lineup vs bad_spot_pitcher in offense-friendly park
  - STRONG_UNDER: weak_lineup vs elite_matchup_pitcher in pitcher park

The math:
  expected_runs = 4.5 (league avg) * lineup_mult * pitcher_quality_mult * park_mult
  edge_pct vs book line = (expected_runs - book_line) / book_line

Inputs:
  - mlb_lineup_quality_index.json
  - mlb_pitcher_edge_composite.json
  - matchups.json (book team totals if present)
  - today.json (park factors)

Output: data/mlb_team_total_edge.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_total_edge.json")

# League average per-TEAM runs per game (not combined).
# MLB 2024-25 avg combined ~9 runs/game -> 4.5 per team.
LEAGUE_RUNS_PER_TEAM = 4.5


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


def _lineup_to_mult(score: float) -> float:
    """Map 0-100 lineup score to runs multiplier (0.75 - 1.30)."""
    # 50 = baseline 1.0; 70+ = 1.20-1.30; 35 = 0.80
    return max(0.75, min(1.30, 1.0 + (score - 50) * 0.012))


def _pitcher_to_mult(edge_score: float) -> float:
    """Higher pitcher edge_score = harder to score against. Returns inverse mult."""
    # 50 baseline, 80+ elite (mult 0.75), 30 bad spot (mult 1.25)
    return max(0.70, min(1.30, 1.0 - (edge_score - 50) * 0.010))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))

    parks = today.get("parks") or {}

    # Index lineup quality by matchup
    lq_idx: Dict[str, Dict[str, Any]] = {}
    for g in (lineup_q.get("games") or []):
        m = g.get("matchup") or ""
        if m: lq_idx[m] = g

    # Index pitcher edge by (matchup, side)
    pe_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher_edge.get("rows") or []):
        key = f"{r.get('matchup','')}|{r.get('side','')}"
        pe_idx[key] = r

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        market = g.get("market") or {}
        total_book = _safe(market.get("total"), 8.5)
        # Default team totals: half of game total each side, but we use lineup
        # quality + pitcher to differentiate
        team_total_baseline = total_book / 2.0

        lq_game = lq_idx.get(matchup, {})

        for side in ("home", "away"):
            lineup_side = lq_game.get(side) or {}
            lineup_score = _safe(lineup_side.get("score"), 50.0)
            lineup_mult = _lineup_to_mult(lineup_score)

            # Pitcher facing this side is the OPPOSING starter
            opp_side = "HOME" if side == "away" else "AWAY"
            pitcher_row = pe_idx.get(f"{matchup}|{opp_side}", {})
            pitcher_edge_score = _safe(pitcher_row.get("edge_score"), 50.0)
            pitcher_mult = _pitcher_to_mult(pitcher_edge_score)

            # Expected runs for this side: league per-team baseline * factors
            expected_runs = (LEAGUE_RUNS_PER_TEAM *
                             lineup_mult * pitcher_mult * park_run_factor)
            # Anchor to book a bit (Bayesian shrinkage toward consensus)
            anchor_weight = 0.40  # 40% to book, 60% to model
            anchored_runs = team_total_baseline * anchor_weight + expected_runs * (1 - anchor_weight)

            edge_runs = anchored_runs - team_total_baseline
            edge_pct = (edge_runs / team_total_baseline) * 100 if team_total_baseline > 0 else 0.0

            direction = "NEUTRAL"
            if edge_runs >= 0.45:
                direction = "STRONG_OVER"
            elif edge_runs >= 0.20:
                direction = "LEAN_OVER"
            elif edge_runs <= -0.45:
                direction = "STRONG_UNDER"
            elif edge_runs <= -0.20:
                direction = "LEAN_UNDER"

            team_abbr = (g.get(side) or {}).get("team") if isinstance(g.get(side), dict) else None

            rows.append({
                "matchup": matchup,
                "side": side.upper(),
                "team": team_abbr,
                "park": park,
                "lineup_score": round(lineup_score, 1),
                "lineup_mult": round(lineup_mult, 3),
                "opposing_pitcher": pitcher_row.get("pitcher"),
                "pitcher_edge_score": round(pitcher_edge_score, 1),
                "pitcher_mult": round(pitcher_mult, 3),
                "park_run_factor": round(park_run_factor, 3),
                "book_team_total": team_total_baseline,
                "model_expected_runs_raw": round(expected_runs, 2),
                "model_expected_runs_anchored": round(anchored_runs, 2),
                "edge_runs": round(edge_runs, 2),
                "edge_pct": round(edge_pct, 1),
                "direction": direction,
            })

    rows.sort(key=lambda r: -abs(r["edge_runs"]))
    strong = [r for r in rows if r["direction"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Team total = league_baseline * lineup_mult * pitcher_mult * "
                       "park_factor, Bayesian-shrunk 40% toward book half-total. "
                       "STRONG_OVER/UNDER at +/- 0.45 runs vs book; LEAN at +/- 0.20.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tt-edge] {o['n_team_sides']} team-sides, {o['n_strong_edges']} strong -> {OUT}")
