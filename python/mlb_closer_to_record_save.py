"""
EdgeStat -- MLB closer to record a save yes/no prop.

Popular DK alt for closer markets. Typical pricing:
  - Closer AVAILABLE on team favored to win by 1-3: +130 to +200
  - Closer UNAVAILABLE: not offered or +500+
  - Closer LIMITED: +250 to +350

Method:
  P(save) = P(team_wins_within_3) * P(closer_available) * 0.65 (closer
  conversion rate on save opportunities). Pulls:
    - team_win_prob from book ML
    - closer_status from mlb_closer_availability_tracker
    - margin distribution from team_total_edge

  STRONG_YES at p in [0.32, 0.50] (vs +180 book = 35.7%)
  STRONG_NO at p_no in [0.75, 0.88] (vs -300 NO book = 75%)

Output: data/mlb_closer_to_record_save.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_closer_to_record_save.json")


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


def _availability_factor(status: str) -> float:
    """Closer availability impact on save probability."""
    return {"AVAILABLE": 1.0, "LIMITED": 0.85,
            "UNAVAILABLE": 0.0, "UNKNOWN_CLOSER": 0.5}.get(status, 0.5)


def _american_to_prob(odds) -> float:
    """Convert American odds to implied probability."""
    if odds is None: return 0.5
    try:
        o = int(odds)
    except Exception:
        return 0.5
    if o == 0: return 0.5
    if o > 0: return 100.0 / (o + 100)
    return -o / (-o + 100)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    closer_track = _load(os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json"))
    closer_idx = {g.get("matchup"): g for g in (closer_track.get("games") or [])}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        market = g.get("market") or {}
        ml_home = market.get("ml_home")
        ml_away = market.get("ml_away")

        closer_game = closer_idx.get(matchup, {})

        for side, ml in (("home", ml_home), ("away", ml_away)):
            ci = closer_game.get(side) or {}
            if not ci.get("closer"): continue

            p_team_win = _american_to_prob(ml)
            # Of team wins, ~65% are saves (1-3 run margin) and 25% are blowouts
            # without a save. So P(save opportunity) ≈ 0.65 * P(team_wins).
            p_save_opp = p_team_win * 0.65

            status = ci.get("status") or "UNKNOWN_CLOSER"
            avail_factor = _availability_factor(status)
            closer_conversion = 0.85  # MLB closer save conversion rate

            p_save = p_save_opp * avail_factor * closer_conversion
            p_no_save = 1 - p_save

            edge_class = "NONE"
            best_market = None
            if 0.32 <= p_save <= 0.50:
                edge_class = "STRONG_YES"
                best_market = {"market": "CLOSER_SAVE_YES",
                               "p": round(p_save, 3),
                               "fair_odds": _american(p_save)}
            elif 0.75 <= p_no_save <= 0.88:
                edge_class = "STRONG_NO"
                best_market = {"market": "CLOSER_SAVE_NO",
                               "p": round(p_no_save, 3),
                               "fair_odds": _american(p_no_save)}

            rows.append({
                "matchup": matchup,
                "side": side.upper(),
                "team": ci.get("team"),
                "closer": ci.get("closer"),
                "closer_status": status,
                "availability_factor": avail_factor,
                "p_team_wins": round(p_team_win, 3),
                "p_save_opportunity": round(p_save_opp, 3),
                "p_save": round(p_save, 3),
                "p_no_save": round(p_no_save, 3),
                "fair_yes": _american(p_save),
                "fair_no": _american(p_no_save),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_save"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_closers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(save) = P(team_wins) * 0.65 (save_opp_rate) * "
                       "availability_factor * 0.85 (closer_conversion). "
                       "STRONG_YES p in [0.32, 0.50] vs +180 book; "
                       "STRONG_NO p_no in [0.75, 0.88] vs -300 NO.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[save] {o['n_closers']} closers, {o['n_strong_edges']} strong -> {OUT}")
