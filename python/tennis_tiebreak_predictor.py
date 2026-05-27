"""
EdgeStat -- Tennis tiebreak predictor.

Surfaces matches with high tiebreak probability:
  - Close p_match_win (between 0.40 and 0.60)
  - Both players ACES_OVER lean (big servers)
  - LOW_DFS lean (efficient serving)
  - Total games OVER lean (longer match)
  - BREAKS UNDER lean (fewer breaks = more held serves = tiebreak)

When 3+ signals align, recommend tiebreak in match YES + total games
OVER.

Output: data/tennis_tiebreak_predictor.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_tiebreak_predictor.json")


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


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    match_win = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))
    dfs = _load(os.path.join(DATA_DIR, "tennis_double_faults_props.json"))
    games = _load(os.path.join(DATA_DIR, "tennis_total_games_props.json"))
    breaks = _load(os.path.join(DATA_DIR, "tennis_breaks_of_serve.json"))

    # Build match-level data
    match_close: Dict[str, bool] = {}
    for r in (match_win.get("rows") or []):
        if not isinstance(r, dict): continue
        p_win = _safe(r.get("p_win") or r.get("p_match_win"))
        if 0.40 <= p_win <= 0.60:
            match_close[r.get("match") or r.get("matchup") or ""] = True

    aces_overs_by_match: Dict[str, int] = {}
    for r in (aces.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            m = r.get("match") or r.get("matchup") or ""
            aces_overs_by_match[m] = aces_overs_by_match.get(m, 0) + 1

    df_unders_by_match: Dict[str, int] = {}
    for r in (dfs.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:
            m = r.get("match") or r.get("matchup") or ""
            df_unders_by_match[m] = df_unders_by_match.get(m, 0) + 1

    games_over: Dict[str, bool] = {}
    for r in (games.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            games_over[r.get("match") or r.get("matchup") or ""] = True

    breaks_under: Dict[str, bool] = {}
    for r in (breaks.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:
            breaks_under[r.get("match") or r.get("matchup") or ""] = True

    all_matches = set(match_close.keys())

    predictions: List[Dict[str, Any]] = []
    for m in all_matches:
        signals: Dict[str, int] = {}
        signals["CLOSE_MATCH"] = 1 if match_close.get(m) else 0
        signals["BOTH_ACES_OVER"] = 1 if aces_overs_by_match.get(m, 0) >= 2 else 0
        signals["LOW_DFS_BOTH"] = 1 if df_unders_by_match.get(m, 0) >= 2 else 0
        signals["GAMES_OVER"] = 1 if games_over.get(m) else 0
        signals["BREAKS_UNDER"] = 1 if breaks_under.get(m) else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        predictions.append({
            "match": m,
            "n_positive_signals": n_positive,
            "signals": signals,
            "recommended_markets": [
                "Tiebreak in match YES",
                "Total games OVER",
                "Match goes 3 sets",
            ],
        })

    predictions.sort(key=lambda p: -p["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_predictions": len(predictions),
        "method_note": "Tennis tiebreak predictor. 3+ signals: CLOSE_MATCH "
                       "(p_win 40-60%), BOTH_ACES_OVER, LOW_DFS_BOTH, "
                       "GAMES_OVER, BREAKS_UNDER. Recommends tiebreak YES + "
                       "total games OVER.",
        "predictions": predictions,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-tiebreak] {o['n_predictions']} predictions -> {OUT}")
