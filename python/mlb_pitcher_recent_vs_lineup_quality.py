"""
EdgeStat -- MLB pitcher recent-form vs opposing lineup quality composite.

Cross-references mlb_pitcher_form_tracker (HEATING_UP / COOLING_DOWN status)
with mlb_lineup_quality_index (opposing lineup tier) to produce a single
"matchup verdict" per pitcher:

  POWER_MATCHUP:    Heating-up pitcher vs weak/bottom lineup
                    -> AGGRESSIVE K_OVER + QS_YES + opp_TT_UNDER
  GOOD_MATCHUP:     Steady pitcher vs weak lineup OR heating-up vs league-avg
                    -> LEAN K_OVER + QS_YES
  EVEN_MATCHUP:     Steady vs league-avg
                    -> No bias
  DIFFICULT_SPOT:   Steady vs above-avg lineup OR cooling-down vs league-avg
                    -> LEAN K_UNDER + opp_TT_OVER
  AMBUSH_RISK:      Cooling-down pitcher vs elite/above-avg lineup
                    -> AGGRESSIVE K_UNDER + opp_TT_OVER + 1ST_INN_ER_YES

Output: data/mlb_pitcher_recent_vs_lineup_quality.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_recent_vs_lineup_quality.json")


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


def _classify(pitcher_status: str, lineup_tier: str) -> Dict[str, Any]:
    """Return verdict + leans for the (pitcher_status, lineup_tier) cross."""
    # Lineup tier ordinal
    weak_tiers = {"bottom_tier", "weak"}
    elite_tiers = {"elite", "above_avg"}
    avg_tiers = {"league_avg"}

    if pitcher_status == "HEATING_UP" and lineup_tier in weak_tiers:
        return {"verdict": "POWER_MATCHUP",
                "leans": ["K_OVER_AGGRESSIVE", "QS_YES", "OPP_TT_UNDER", "OUTS_OVER"]}
    if pitcher_status == "COOLING_DOWN" and lineup_tier in elite_tiers:
        return {"verdict": "AMBUSH_RISK",
                "leans": ["K_UNDER_AGGRESSIVE", "OPP_TT_OVER", "1ST_INN_ER_YES",
                          "QS_NO", "OUTS_UNDER"]}
    if pitcher_status in ("HEATING_UP", "HOT_K") and lineup_tier in avg_tiers:
        return {"verdict": "GOOD_MATCHUP",
                "leans": ["K_OVER", "QS_YES_LEAN"]}
    if pitcher_status in ("STEADY",) and lineup_tier in weak_tiers:
        return {"verdict": "GOOD_MATCHUP",
                "leans": ["K_OVER_LEAN", "QS_YES_LEAN"]}
    if pitcher_status in ("COOLING_DOWN", "COLD_K") and lineup_tier in avg_tiers:
        return {"verdict": "DIFFICULT_SPOT",
                "leans": ["K_UNDER", "OPP_TT_OVER_LEAN"]}
    if pitcher_status == "STEADY" and lineup_tier in elite_tiers:
        return {"verdict": "DIFFICULT_SPOT",
                "leans": ["K_UNDER_LEAN", "OPP_TT_OVER_LEAN"]}
    return {"verdict": "EVEN_MATCHUP", "leans": []}


def run() -> Dict[str, Any]:
    form_tracker = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    # Index lineup quality by matchup + side
    lq_idx: Dict[str, Dict[str, Any]] = {}
    for g in (lineup_q.get("games") or []):
        m = g.get("matchup") or ""
        for side in ("home", "away"):
            s = g.get(side) or {}
            key = f"{m}|{side.upper()}"
            lq_idx[key] = s

    rows_out: List[Dict[str, Any]] = []
    for r in (form_tracker.get("rows") or []):
        if not isinstance(r, dict): continue
        matchup = r.get("matchup") or ""
        side = r.get("side") or ""
        # Pitcher faces OPPOSING lineup
        opp_side = "AWAY" if side == "HOME" else "HOME"
        opp_lineup = lq_idx.get(f"{matchup}|{opp_side}") or {}
        opp_lineup_tier = opp_lineup.get("tier") or "league_avg"
        opp_lineup_score = _safe(opp_lineup.get("score"), 50.0)

        pitcher_status = r.get("status") or "STEADY"
        verdict_info = _classify(pitcher_status, opp_lineup_tier)

        rows_out.append({
            "matchup": matchup,
            "side": side,
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "pitcher_form_status": pitcher_status,
            "season_k_per_9": r.get("season_k_per_9"),
            "season_era": r.get("season_era"),
            "recent_k_per_9_l3": r.get("recent_k_per_9_l3"),
            "recent_era_l3": r.get("recent_era_l3"),
            "opp_lineup_tier": opp_lineup_tier,
            "opp_lineup_score": opp_lineup_score,
            "verdict": verdict_info["verdict"],
            "leans": verdict_info["leans"],
        })

    # Tier counts
    n_power = sum(1 for r in rows_out if r["verdict"] == "POWER_MATCHUP")
    n_ambush = sum(1 for r in rows_out if r["verdict"] == "AMBUSH_RISK")
    n_good = sum(1 for r in rows_out if r["verdict"] == "GOOD_MATCHUP")
    n_diff = sum(1 for r in rows_out if r["verdict"] == "DIFFICULT_SPOT")

    rows_out.sort(key=lambda r: {
        "POWER_MATCHUP": 0, "AMBUSH_RISK": 1, "GOOD_MATCHUP": 2,
        "DIFFICULT_SPOT": 3, "EVEN_MATCHUP": 4
    }.get(r["verdict"], 5))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows_out),
        "n_power_matchups": n_power,
        "n_ambush_risks": n_ambush,
        "n_good_matchups": n_good,
        "n_difficult_spots": n_diff,
        "method_note": "Cross-references pitcher_form_tracker (HEATING_UP / COOLING_DOWN) "
                       "with opp lineup_quality_index tier (elite / league_avg / weak). "
                       "Surfaces POWER_MATCHUP (heating vs weak) for aggressive K_OVER "
                       "and AMBUSH_RISK (cooling vs elite) for aggressive K_UNDER.",
        "rows": rows_out,
        "power_matchups": [r for r in rows_out if r["verdict"] == "POWER_MATCHUP"],
        "ambush_risks": [r for r in rows_out if r["verdict"] == "AMBUSH_RISK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[form-lineup] {o['n_starters']} starters, {o['n_power_matchups']} POWER, "
          f"{o['n_ambush_risks']} AMBUSH, {o['n_good_matchups']} GOOD, "
          f"{o['n_difficult_spots']} DIFFICULT -> {OUT}")
