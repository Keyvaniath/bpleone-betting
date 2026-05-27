"""
EdgeStat -- MLB game flow predictor.

For each MLB game, predicts the likely game flow:
  - EARLY_LEAD (1st-3rd inning offensive explosion likely)
  - LATE_DRAMA (close through 6, decided in 7-9)
  - PITCHER_DUEL (both starters dominate, low scoring)
  - BLOWOUT (one team dominates start to finish)
  - GRIND (back-and-forth scoring all game)

Useful for inning-specific bets, late-game props, and live-betting setup.

Output: data/mlb_game_flow_predictor.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_flow_predictor.json")


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
    first_inn = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))
    first_3 = _load(os.path.join(DATA_DIR, "mlb_team_first_3_innings_runs.json"))
    inn_4_6 = _load(os.path.join(DATA_DIR, "mlb_innings_4_6_totals.json"))
    inn_7_9 = _load(os.path.join(DATA_DIR, "mlb_innings_7_9_totals.json"))
    game_total = _load(os.path.join(DATA_DIR, "mlb_game_total_alt_props.json"))
    pitcher_conf = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    blowout = _load(os.path.join(DATA_DIR, "mlb_blowout_alerts.json"))

    # Per matchup signals
    first_inn_p: Dict[str, float] = {}
    for r in (first_inn.get("rows") or []):
        if isinstance(r, dict):
            m = r.get("matchup", "")
            p = _safe(r.get("p_yes") or r.get("p"))
            if m not in first_inn_p or p > first_inn_p[m]:
                first_inn_p[m] = p

    first_3_p: Dict[str, float] = {}
    for r in (first_3.get("rows") or []):
        if isinstance(r, dict):
            m = r.get("matchup", "")
            p_over = _safe(r.get("p_over"))
            first_3_p[m] = max(first_3_p.get(m, 0), p_over)

    inn_4_6_over: Dict[str, bool] = {}
    for r in (inn_4_6.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                inn_4_6_over[r.get("matchup", "")] = True

    inn_7_9_over: Dict[str, bool] = {}
    for r in (inn_7_9.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                inn_7_9_over[r.get("matchup", "")] = True

    gt_over: Dict[str, bool] = {}
    for r in (game_total.get("rows") or []):
        if isinstance(r, dict):
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                gt_over[r.get("matchup", "")] = True

    pitcher_locks_by_matchup: Dict[str, int] = {}
    for r in (pitcher_conf.get("rows") or []):
        if isinstance(r, dict) and "LOCK" in (r.get("tier") or ""):
            m = r.get("matchup", "")
            pitcher_locks_by_matchup[m] = pitcher_locks_by_matchup.get(m, 0) + 1

    blowout_matchups: set = set()
    for a in (blowout.get("alerts") or []):
        if isinstance(a, dict):
            blowout_matchups.add(a.get("matchup", ""))

    all_matchups = (set(first_inn_p) | set(first_3_p) | set(gt_over))

    predictions: List[Dict[str, Any]] = []
    for m in all_matchups:
        if not m: continue
        signals: Dict[str, int] = {}
        signals["EARLY_RUN_LIKELY"] = 1 if first_inn_p.get(m, 0) >= 0.45 else 0
        signals["FIRST_3_OVER"] = 1 if first_3_p.get(m, 0) >= 0.55 else 0
        signals["INN_4_6_OVER"] = 1 if inn_4_6_over.get(m) else 0
        signals["INN_7_9_OVER"] = 1 if inn_7_9_over.get(m) else 0
        signals["GAME_TOTAL_OVER"] = 1 if gt_over.get(m) else 0
        signals["PITCHER_LOCK_PRESENT"] = pitcher_locks_by_matchup.get(m, 0)
        signals["BLOWOUT_FLAGGED"] = 1 if m in blowout_matchups else 0

        # Classify flow
        if signals["BLOWOUT_FLAGGED"] and signals["GAME_TOTAL_OVER"]:
            flow = "BLOWOUT"
        elif signals["PITCHER_LOCK_PRESENT"] >= 2:
            flow = "PITCHER_DUEL"
        elif signals["EARLY_RUN_LIKELY"] and signals["FIRST_3_OVER"]:
            flow = "EARLY_LEAD"
        elif signals["INN_7_9_OVER"] and not signals["INN_4_6_OVER"]:
            flow = "LATE_DRAMA"
        elif signals["INN_4_6_OVER"] and signals["INN_7_9_OVER"]:
            flow = "GRIND"
        else:
            flow = "NEUTRAL"

        if flow == "NEUTRAL": continue

        predictions.append({
            "matchup": m,
            "flow": flow,
            "signals": signals,
            "recommended_markets": {
                "BLOWOUT": ["Run line -1.5 favorite", "Game total OVER",
                            "Loser bullpen blowup props"],
                "PITCHER_DUEL": ["Game total UNDER", "F5 UNDER",
                                 "Both pitchers K OVER + outs OVER (parlay)"],
                "EARLY_LEAD": ["1st inning run YES",
                               "1st 3 innings OVER",
                               "Team first to score lean"],
                "LATE_DRAMA": ["Extra innings YES", "7-9 inn OVER",
                               "Closer save YES"],
                "GRIND": ["Game total OVER", "Both teams 5+ runs"],
            }.get(flow, []),
        })

    predictions.sort(key=lambda p: p["flow"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_predictions": len(predictions),
        "by_flow": {flow: sum(1 for p in predictions if p["flow"] == flow)
                    for flow in ("BLOWOUT", "PITCHER_DUEL", "EARLY_LEAD",
                                  "LATE_DRAMA", "GRIND")},
        "method_note": "MLB game flow predictor. Classifies each game into "
                       "BLOWOUT (one team dominates), PITCHER_DUEL (both starters "
                       "LOCK), EARLY_LEAD (early run + 1st-3rd OVER), LATE_DRAMA "
                       "(7-9 OVER but not 4-6), GRIND (4-6 + 7-9 OVER).",
        "predictions": predictions,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-flow] {o['n_predictions']} predictions by_flow={o['by_flow']} -> {OUT}")
