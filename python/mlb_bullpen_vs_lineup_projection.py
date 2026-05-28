"""
EdgeStat -- MLB bullpen vs opposing-lineup projection.

Pure-model (no odds needed). Projects expected runs the bullpen allows in
innings 7-9 against the SPECIFIC opposing lineup, adjusting for:
  - Bullpen fatigue (rested arms suppress; overworked arms inflate)
  - Opposing lineup quality (elite lineup => more runs)
  - Bullpen baseline ER/9

Used to anchor late-inning UNDER/OVER leans and closer-save confidence
independent of book lines.

Output: data/mlb_bullpen_vs_lineup_projection.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_bullpen_vs_lineup_projection.json")

LEAGUE_BULLPEN_ER9 = 4.10
LEAGUE_LINEUP_BASELINE = 50.0


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
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    # Bullpen metrics by team
    bullpen_by_team: Dict[str, Dict[str, Any]] = {}
    for r in (bullpen.get("rows") or bullpen.get("teams") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        if team:
            bullpen_by_team[team] = r

    # Lineup scores by (matchup, side)
    lq_idx: Dict[str, Dict[str, Any]] = {}
    games_meta: List[Dict[str, Any]] = []
    for g in (lq.get("games") or []):
        m = g.get("matchup") or ""
        games_meta.append(g)
        for side in ("home", "away"):
            sd = g.get(side) or {}
            lq_idx[f"{m}|{side.upper()}"] = sd

    rows: List[Dict[str, Any]] = []
    for g in games_meta:
        matchup = g.get("matchup") or ""
        for side in ("home", "away"):
            sd = g.get(side) or {}
            team = (sd.get("team") or "").upper()
            if not team: continue

            bp = bullpen_by_team.get(team, {})
            bp_er9 = _safe(bp.get("er9") or bp.get("bullpen_er9"), LEAGUE_BULLPEN_ER9)
            bp_status = (bp.get("status") or bp.get("tier") or bp.get("flag") or "").upper()

            # Opposing lineup
            opp_side = "AWAY" if side == "home" else "HOME"
            opp = lq_idx.get(f"{matchup}|{opp_side}") or {}
            opp_lineup_score = _safe(opp.get("score"), LEAGUE_LINEUP_BASELINE)

            # Fatigue multiplier
            fatigue_mult = 1.0
            if "FATIG" in bp_status or "OVERWORK" in bp_status or "TIRED" in bp_status:
                fatigue_mult = 1.15
            elif "REST" in bp_status or "FRESH" in bp_status:
                fatigue_mult = 0.92

            # Lineup multiplier: each 10 pts above 50 baseline => +6% runs
            lineup_mult = 1.0 + (opp_lineup_score - LEAGUE_LINEUP_BASELINE) / 100.0 * 0.6

            # Project ER over ~3 innings (7-9) = er9 / 9 * 3
            base_3inn = bp_er9 / 9.0 * 3.0
            proj_er_late = base_3inn * fatigue_mult * lineup_mult

            # Direction lean
            if proj_er_late >= 1.8:
                lean = "LATE_OVER_LEAN"
            elif proj_er_late <= 1.0:
                lean = "LATE_UNDER_LEAN"
            else:
                lean = "NEUTRAL"

            rows.append({
                "matchup": matchup,
                "team": team,
                "side": side.upper(),
                "bullpen_er9": round(bp_er9, 2),
                "bullpen_status": bp_status or "UNKNOWN",
                "opp_lineup_score": round(opp_lineup_score, 1),
                "fatigue_mult": round(fatigue_mult, 3),
                "lineup_mult": round(lineup_mult, 3),
                "projected_er_innings_7_9": round(proj_er_late, 2),
                "lean": lean,
            })

    rows.sort(key=lambda r: -r["projected_er_innings_7_9"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_rows": len(rows),
        "n_late_over": sum(1 for r in rows if r["lean"] == "LATE_OVER_LEAN"),
        "n_late_under": sum(1 for r in rows if r["lean"] == "LATE_UNDER_LEAN"),
        "method_note": "Pure-model bullpen vs opp-lineup late-inning ER projection. "
                       "proj_er_7_9 = (bullpen_er9/9*3) * fatigue_mult * lineup_mult. "
                       "fatigue: tired 1.15x, rested 0.92x. lineup: +0.6% runs per "
                       "point above 50 baseline. LATE_OVER >= 1.8 ER; UNDER <= 1.0.",
        "rows": rows,
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[bullpen-vs-lineup] {o['n_rows']} rows "
          f"({o['n_late_over']} OVER, {o['n_late_under']} UNDER) -> {OUT}")
