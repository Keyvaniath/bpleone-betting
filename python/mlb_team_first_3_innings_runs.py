"""
EdgeStat -- MLB team first-3-innings runs alternate market.

The "team to score in first 3 innings yes/no" market is popular pre-game.
Variant of F5 but specifically through 3 innings. Common DK pricing:
  - Strong offense vs weak SP in hitter park: -150 to +110
  - Average matchup: +130 to +200
  - Strong starter vs weak offense: +250 to +400

Method:
  expected_runs_first_3 = LEAGUE_RUNS_PER_3_INN * lineup_mult * pitcher_susceptibility * park_factor
  Where LEAGUE_RUNS_PER_3_INN ~ 1.55 (combined avg per 3 innings).
  Half-side (for one team) ~ 0.78 runs.

  P(team scores >=1 in first 3) = 1 - exp(-expected_runs_3)

  Also exposes 2+ and 3+ thresholds for alt-market grid.

  STRONG_YES at p in [0.62, 0.74] (vs -150 book = 60% breakeven)
  STRONG_NO at p_no in [0.55, 0.68] (vs +130 NO = 43.5% breakeven)

Output: data/mlb_team_first_3_innings_runs.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_first_3_innings_runs.json")

LEAGUE_ERA = 4.20
LEAGUE_RUNS_PER_3_INN_PER_TEAM = 1.55  # half of ~3.10 combined


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


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def _lineup_score_for(matchup: str, side: str,
                      lineup_data: Dict[str, Any]) -> float:
    for g in (lineup_data.get("games") or []):
        if g.get("matchup") != matchup: continue
        return _safe((g.get(side) or {}).get("score"), 50.0)
    return 50.0


def _lineup_to_mult(score: float) -> float:
    return max(0.70, min(1.30, 1.0 + (score - 50) * 0.012))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    parks = today.get("parks") or {}
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        for side, sp_field in (("home", "away_pitcher"), ("away", "home_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            opp_pitcher_row = p_by_name.get((sp_name or "").lower(), {}) if sp_name else {}
            stats = opp_pitcher_row.get("stats") or {}
            opp_era = _safe(stats.get("era"), LEAGUE_ERA)
            pitcher_susceptibility = opp_era / LEAGUE_ERA

            lineup_score = _lineup_score_for(matchup, side, lineup_q)
            lineup_mult = _lineup_to_mult(lineup_score)

            expected_runs_3 = (LEAGUE_RUNS_PER_3_INN_PER_TEAM *
                               lineup_mult * pitcher_susceptibility *
                               (park_run_factor ** 0.6))

            p_1plus = _poisson_at_least(1, expected_runs_3)
            p_2plus = _poisson_at_least(2, expected_runs_3)
            p_3plus = _poisson_at_least(3, expected_runs_3)
            p_no_1plus = 1 - p_1plus

            edge_class = "NONE"
            best_market = None
            if 0.62 <= p_1plus <= 0.74:
                edge_class = "STRONG_YES"
                best_market = {"market": "F3_TEAM_SCORE_YES",
                               "p": round(p_1plus, 3),
                               "fair_odds": _american(p_1plus)}
            elif 0.55 <= p_no_1plus <= 0.68:
                edge_class = "STRONG_NO"
                best_market = {"market": "F3_TEAM_SCORE_NO",
                               "p": round(p_no_1plus, 3),
                               "fair_odds": _american(p_no_1plus)}

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
                "park_run_factor": park_run_factor,
                "expected_runs_first_3": round(expected_runs_3, 3),
                "p_1plus": round(p_1plus, 3),
                "p_2plus": round(p_2plus, 3),
                "p_3plus": round(p_3plus, 3),
                "fair_yes_1plus": _american(p_1plus),
                "fair_no_1plus": _american(p_no_1plus),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_1plus"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(team scores in first 3 inn) = 1 - exp(-lam). "
                       "lam = 1.55 * lineup_mult * (opp_ERA/4.20) * park^0.6. "
                       "Also exposes 2+/3+ alts. STRONG_YES p in [0.62, 0.74] vs -150 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f3-team] {o['n_team_sides']} sides, {o['n_strong_edges']} strong -> {OUT}")
