"""
EdgeStat -- Reverse Line Movement (RLM) detector.

Sharp-money signal: when a line moves AGAINST the public bet percentage, that's
sharp action. Example: 73% of bets on Yankees -150, but line moves to -135 ->
RLM. Books are protecting against sharps, telling us where they expect the
real action to land.

Reads:
  - data/sharp_action_radar.json (line movement over time)
  - data/today.json (current consensus / public-side estimates)
  - data/live_clv.json (Bovada per-game open / current line history)

Output: data/reverse_line_movement.json

Frontend uses this on /trends and the dashboard sharp-flow tile to highlight
RLM picks ("BOOK FADED THE PUBLIC").
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "reverse_line_movement.json")

# Thresholds for RLM classification
MIN_PUBLIC_PCT = 60   # Public has to be at least 60% on one side
MIN_LINE_MOVE_PP = 3   # Line moved >= 3pp in opposite direction
STRONG_RLM_LINE_PP = 6  # Big RLM = >= 6pp


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _to_pp(odds_open: float, odds_now: float) -> float:
    """Convert American odds delta to implied-probability delta (in percentage points)."""
    def implied(odds):
        if odds is None: return None
        odds = float(odds)
        if odds < 0:
            return abs(odds) / (abs(odds) + 100) * 100
        return 100 / (odds + 100) * 100
    a = implied(odds_open)
    b = implied(odds_now)
    if a is None or b is None: return 0.0
    return b - a  # positive = line shortened on this side


def run() -> Dict[str, Any]:
    clv = _load(os.path.join(DATA_DIR, "live_clv.json"))

    # live_clv.games is a list of per-game snapshot histories
    games_obj = clv.get("games", [])
    if isinstance(games_obj, dict): games_obj = list(games_obj.values())

    rlm_picks: List[Dict[str, Any]] = []

    for g in games_obj:
        snapshots = g.get("snapshots") or []
        # Filter to pre-game snapshots only (in-game movement is reactive, not sharp)
        pre = [s for s in snapshots if s.get("state") == "pre"]
        if len(pre) < 2: continue

        open_snap = pre[0]
        close_snap = pre[-1]

        # Home side analysis
        for side, ml_key, opp_ml_key in [("home", "home_ml", "away_ml"),
                                          ("away", "away_ml", "home_ml")]:
            open_odds = open_snap.get(ml_key)
            close_odds = close_snap.get(ml_key)
            if open_odds is None or close_odds is None: continue

            delta_pp = _to_pp(open_odds, close_odds)
            # Public favorite heuristic: side with shorter (more negative) opening odds
            try:
                opening_implied = (abs(float(open_odds)) / (abs(float(open_odds)) + 100) * 100
                                   if float(open_odds) < 0
                                   else 100 / (float(open_odds) + 100) * 100)
            except Exception:
                continue

            # Assume public is on side that opens shorter (>55% implied)
            if opening_implied < 55: continue  # Not the favorite side
            # RLM: this favored side's odds got LONGER (line moved against)
            if delta_pp <= -MIN_LINE_MOVE_PP:
                strength = "STRONG" if abs(delta_pp) >= STRONG_RLM_LINE_PP else "STANDARD"
                rlm_picks.append({
                    "matchup": g.get("matchup"),
                    "pick": f"{side.upper()} ML",
                    "side": side.upper(),
                    "public_pct": round(opening_implied, 1),
                    "open_odds": open_odds,
                    "current_odds": close_odds,
                    "line_delta_pp": round(delta_pp, 2),
                    "rlm_strength": strength,
                    "interpretation": (
                        f"Open {open_odds} -> {close_odds} on {side.upper()} -- "
                        f"line moved {abs(delta_pp):.1f}pp AGAINST favored side, sharp money the other way"
                    ),
                })

    # Sort by magnitude
    rlm_picks.sort(key=lambda r: abs(r["line_delta_pp"]), reverse=True)
    strong = [r for r in rlm_picks if r["rlm_strength"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total_evaluated": len(games_obj),
        "n_rlm_picks": len(rlm_picks),
        "n_strong_rlm": len(strong),
        "thresholds": {
            "min_public_pct": MIN_PUBLIC_PCT,
            "min_line_move_pp": MIN_LINE_MOVE_PP,
            "strong_threshold_pp": STRONG_RLM_LINE_PP,
        },
        "rlm_picks": rlm_picks,
        "strong_only": strong,
        "note": "Reverse Line Movement -- books move line AGAINST public majority. Sharp signal.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[rlm] {o['n_rlm_picks']} RLM picks ({o['n_strong_rlm']} strong) -> {OUT}")
