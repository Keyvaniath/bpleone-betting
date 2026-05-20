"""
EdgeStat -- SHARP ACTION radar.

For every game-line pick in todays_top_plays.top_25, compares the line at
recording / opening time vs the latest book line. Surfaces:

   POSITIVE SHARP signal -- market moving TOWARD model pick (line shifted
     5+ pp implied prob in our direction since open). Suggests sharps
     agree with the model.

   NEGATIVE SHARP signal -- market moving AWAY (line shifted against us).
     Suggests the public bet our side and sharps are fading.

   NEUTRAL -- line stable.

Differs from locks_clv.py (which only does the 5 daily locks) by
tracking the FULL top-25 board so Brandon can see where sharp action
agrees / disagrees BEFORE locking it in.

Output: data/sharp_action_radar.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "sharp_action_radar.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_implied(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def _find_game_in_clv(matchup: str, clv_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not matchup: return None
    target = matchup.lower().replace(" ", "").replace("@", "")
    games = clv_data.get("games") or {}
    for gk, g in games.items():
        gm = (g.get("matchup") or "").lower().replace(" ", "").replace("@", "")
        if target in gm or gm in target: return g
        if target in gk.lower().replace("_", ""): return g
    return None


def _line_at(snap: Dict[str, Any], market: str) -> Optional[int]:
    if "ml_home" in market: return snap.get("home_ml")
    if "ml_away" in market: return snap.get("away_ml")
    if "over_" in market: return snap.get("total_over")
    if "under_" in market: return snap.get("total_under")
    return None


def _detect_signal(pick: Dict[str, Any], clv_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    market = (pick.get("market") or "").lower()
    if not any(k in market for k in ("ml_home", "ml_away", "over_", "under_")):
        return None
    if any(k in market for k in ("pp_", "vs_sp", "situational")):
        return None
    matchup = pick.get("player_or_matchup")
    game = _find_game_in_clv(matchup, clv_data)
    if not game: return None
    snaps = game.get("snapshots") or []
    if len(snaps) < 2: return None

    opening = game.get("opening") or snaps[0]
    latest = snaps[-1]
    open_am = _line_at(opening, market)
    latest_am = _line_at(latest, market)
    if open_am is None or latest_am is None: return None
    open_implied = _american_to_implied(open_am)
    latest_implied = _american_to_implied(latest_am)
    if open_implied is None or latest_implied is None: return None

    shift_pp = (latest_implied - open_implied) * 100   # pp the market moved toward our side
    signal_strength = "POSITIVE" if shift_pp >= 3 else ("NEGATIVE" if shift_pp <= -3 else "NEUTRAL")
    intensity = ("ELITE" if abs(shift_pp) >= 8 else
                  "STRONG" if abs(shift_pp) >= 5 else
                  "MODERATE" if abs(shift_pp) >= 3 else "WEAK")

    return {
        "matchup": matchup,
        "market": market,
        "model_prob": pick.get("prob"),
        "model_edge_pct": pick.get("edge_pct"),
        "opening_american": open_am,
        "opening_implied_pct": round(open_implied * 100, 2),
        "latest_american": latest_am,
        "latest_implied_pct": round(latest_implied * 100, 2),
        "shift_pp": round(shift_pp, 2),
        "signal": signal_strength,
        "intensity": intensity,
        "n_snapshots": len(snaps),
    }


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    clv_data = _load(os.path.join(DATA_DIR, "live_clv.json"))
    picks = top_plays.get("top_25") or []

    signals: List[Dict[str, Any]] = []
    for pick in picks:
        s = _detect_signal(pick, clv_data)
        if s: signals.append(s)

    positive = [s for s in signals if s["signal"] == "POSITIVE"]
    negative = [s for s in signals if s["signal"] == "NEGATIVE"]
    neutral = [s for s in signals if s["signal"] == "NEUTRAL"]

    positive.sort(key=lambda x: -x["shift_pp"])
    negative.sort(key=lambda x: x["shift_pp"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_picks_analyzed": len(signals),
        "n_positive_sharp": len(positive),
        "n_negative_sharp": len(negative),
        "n_neutral": len(neutral),
        "positive_signals": positive[:15],
        "negative_signals": negative[:10],
        "neutral_signals": neutral[:10],
        "note": ("Sharp action radar: tracks how every top-25 board pick's "
                  "book line has moved since open. Positive shift = market "
                  "agreeing with model (sharps follow). Negative shift = "
                  "fading (sharps disagree). 5+pp shift is material."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Sharp action radar: {p['n_picks_analyzed']} game-line picks tracked")
    print(f"  Positive sharps: {p['n_positive_sharp']} | Negative: {p['n_negative_sharp']} | Neutral: {p['n_neutral']}")
    if p["positive_signals"]:
        print(f"\n  Top POSITIVE sharp signals (market moving with us):")
        for s in p["positive_signals"][:5]:
            print(f"    [{s['intensity']:8s}] {s['matchup'][:25]:25s} {s['market']:18s}  "
                  f"{s['opening_implied_pct']:.1f}% -> {s['latest_implied_pct']:.1f}% "
                  f"({'+' if s['shift_pp']>=0 else ''}{s['shift_pp']:.1f}pp)")
    if p["negative_signals"]:
        print(f"\n  Top NEGATIVE sharp signals (market fading us):")
        for s in p["negative_signals"][:5]:
            print(f"    [{s['intensity']:8s}] {s['matchup'][:25]:25s} {s['market']:18s}  "
                  f"{s['opening_implied_pct']:.1f}% -> {s['latest_implied_pct']:.1f}% "
                  f"({s['shift_pp']:.1f}pp)")
