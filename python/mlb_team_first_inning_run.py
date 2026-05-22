"""
EdgeStat -- MLB team to score in 1st inning yes/no prop.

Popular DK first-inning market. Typical pricing:
  - Elite lineup vs avg pitcher: -160 (61.5% breakeven)
  - Avg matchup: +130 (43.5% breakeven)
  - Weak lineup vs ace: +200 (33.3% breakeven)

Method:
  Mirror of mlb_pitcher_1st_inning_er but from offense side:
  expected_team_runs_first_inning = 0.55 * lineup_mult * pitcher_susceptibility
  Where pitcher_susceptibility = pitcher_ERA / 4.20 (league avg)
  P(team scores >= 1) = 1 - exp(-expected_team_runs_first)

  Cross-validates with mlb_pitcher_1st_inning_er for consistency. If the
  pitcher side says ER YES at 45% and offense side says SCORE YES at 47%,
  both are coherent (close to identical due to symmetric framing).

  STRONG_YES at p >= 0.50 vs +130 book (43.5% breakeven).
  STRONG_NO at p_no >= 0.65 vs -180 book (64.3% breakeven on NO).

Output: data/mlb_team_first_inning_run.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_first_inning_run.json")

LEAGUE_ERA = 4.20
LEAGUE_RUNS_PER_HALF = 0.55  # ~half-inning league avg


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _lineup_score_for(matchup: str, side: str,
                      lineup_data: Dict[str, Any]) -> float:
    for g in (lineup_data.get("games") or []):
        if g.get("matchup") != matchup: continue
        return _safe((g.get(side) or {}).get("score"), 50.0)
    return 50.0


def _lineup_to_mult(score: float) -> float:
    return max(0.70, min(1.35, 1.0 + (score - 50) * 0.013))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("home", "away_pitcher"), ("away", "home_pitcher")):
            # OFFENSE side faces OPPOSING starter
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            opp_pitcher_row = p_by_name.get((sp_name or "").lower(), {}) if sp_name else {}
            stats = opp_pitcher_row.get("stats") or {}
            opp_era = _safe(stats.get("era"), LEAGUE_ERA)
            pitcher_susceptibility = opp_era / LEAGUE_ERA  # 1.0 baseline

            lineup_score = _lineup_score_for(matchup, side, lineup_q)
            lineup_mult = _lineup_to_mult(lineup_score)

            expected_runs_first = LEAGUE_RUNS_PER_HALF * lineup_mult * pitcher_susceptibility
            p_score = 1 - math.exp(-expected_runs_first)
            p_no_score = 1 - p_score

            edge_class = "NONE"
            best_market = None
            # STRONG_YES at p in [0.50, 0.62] (vs +130 book = 43.5%)
            if 0.50 <= p_score <= 0.62:
                edge_class = "STRONG_YES"
                best_market = {"market": "1ST_INN_SCORE_YES",
                               "p": round(p_score, 3),
                               "fair_odds": _american(p_score)}
            # STRONG_NO at p_no in [0.65, 0.78] (vs -200 book = 66.7% breakeven)
            elif 0.65 <= p_no_score <= 0.78:
                edge_class = "STRONG_NO"
                best_market = {"market": "1ST_INN_SCORE_NO",
                               "p": round(p_no_score, 3),
                               "fair_odds": _american(p_no_score)}

            team_abbr = (g.get(side) or {}).get("team") if isinstance(g.get(side), dict) else None

            rows.append({
                "matchup": matchup,
                "side": side.upper(),
                "team": team_abbr,
                "lineup_score": round(lineup_score, 1),
                "lineup_mult": round(lineup_mult, 3),
                "opposing_pitcher": sp_name,
                "opp_era": round(opp_era, 2),
                "pitcher_susceptibility": round(pitcher_susceptibility, 3),
                "expected_runs_1st": round(expected_runs_first, 3),
                "p_score": round(p_score, 3),
                "p_no_score": round(p_no_score, 3),
                "fair_yes_odds": _american(p_score),
                "fair_no_odds": _american(p_no_score),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_score"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Offense-side mirror of pitcher_1st_inning_er. "
                       "P(team scores in 1st) = 1 - exp(-0.55 * lineup_mult * "
                       "(opp_ERA/4.20)). STRONG_YES p in [0.50, 0.62] vs +130 book; "
                       "STRONG_NO p_no in [0.65, 0.78] vs -200 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-score] {o['n_team_sides']} team-sides, {o['n_strong_edges']} strong -> {OUT}")
