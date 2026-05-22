"""
EdgeStat -- MLB inning-by-inning score probability matrix.

For each game/team, computes P(team scores in inning N) for innings 1-9.
Useful for in-game live betting and 'scoring in inning N' DK markets.

Method:
  Per-team expected_runs (from mlb_team_total_edge) divides across innings:
    - 1st inning: 12% of total (~0.11 per team in avg game)
    - 2nd-3rd: 11% each (~0.10)
    - 4th-6th: 11% each
    - 7th: 11%
    - 8th-9th: 11.5% each (closer fatigue)

  Apply pitcher fatigue penalty in late innings (innings 6+ when starter
  pulled, bullpen takes over with higher implied rate).

  P(team scores in inning N) = 1 - exp(-lam_inning_N)

Output: data/mlb_inning_probability_matrix.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_inning_probability_matrix.json")


INNING_SHARES = {
    1: 0.115, 2: 0.110, 3: 0.110, 4: 0.110, 5: 0.110,
    6: 0.110, 7: 0.110, 8: 0.115, 9: 0.110,
}


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


def run() -> Dict[str, Any]:
    tt_edge = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    bp_fatigue = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))

    bp_idx = {g.get("matchup"): g for g in (bp_fatigue.get("games") or [])}

    rows_out: List[Dict[str, Any]] = []
    for r in (tt_edge.get("rows") or []):
        if not isinstance(r, dict): continue
        matchup = r.get("matchup") or ""
        side = r.get("side") or ""
        team_total_lam = _safe(r.get("model_expected_runs_anchored"),
                               r.get("model_expected_runs_raw"))
        if team_total_lam <= 0: continue

        # Opp bullpen fatigue boosts late-inning rates
        bp_game = bp_idx.get(matchup, {})
        opp_side = "away_pen" if side == "HOME" else "home_pen"
        opp_pen = bp_game.get(opp_side) or {}
        late_inning_mult = 1.0
        if opp_pen.get("tier") == "GASSED":
            late_inning_mult = 1.30
        elif opp_pen.get("tier") == "TIRED":
            late_inning_mult = 1.15
        elif opp_pen.get("tier") == "FRESH":
            late_inning_mult = 0.92

        # Compute per-inning lambdas
        innings_data: Dict[str, Any] = {}
        for inn, share in INNING_SHARES.items():
            mult = late_inning_mult if inn >= 7 else 1.0
            lam = team_total_lam * share * mult
            p_score = 1 - math.exp(-lam)
            innings_data[f"inning_{inn}"] = {
                "expected_runs": round(lam, 3),
                "p_scores": round(p_score, 3),
            }

        # Identify highest-prob inning
        max_inning = max(innings_data, key=lambda k: innings_data[k]["p_scores"])

        rows_out.append({
            "matchup": matchup,
            "side": side,
            "team": r.get("team"),
            "team_total_lam": round(team_total_lam, 2),
            "opp_bullpen_tier": opp_pen.get("tier"),
            "late_inning_mult": round(late_inning_mult, 2),
            "by_inning": innings_data,
            "highest_prob_inning": max_inning,
            "highest_p": innings_data[max_inning]["p_scores"],
        })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows_out),
        "method_note": "Per-inning lambda = team_total * inning_share[N] * "
                       "late_inning_mult (when N >= 7, boosted by opp bullpen "
                       "GASSED/TIRED). P(team scores in inning N) = 1 - exp(-lam).",
        "rows": rows_out,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[inn-matrix] {o['n_team_sides']} team-sides -> {OUT}")
