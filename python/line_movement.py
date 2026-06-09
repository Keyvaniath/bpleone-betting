"""
EdgeStat -- line movement / steam detector (from the free ESPN odds history).

Reads data/odds_history.json (the timestamped open->current odds trail written by
espn_odds.py every heartbeat) and, per game, measures how the market has moved
since it opened:
  - moneyline: the home team's de-vig-free implied probability shift (pp). A
    positive shift means the line shortened on the home side -> money came in on
    home. This is the "where the sharp money went" signal.
  - total: how many runs/points the posted total moved (over/under steam).

A move is flagged STEAM when it clears a threshold (a real market signal, not
noise). 100% free, multi-sport (MLB/NBA/NHL/WNBA), no paid key.

Output: data/line_movement.json -> line-movement.html
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY = os.path.join(DATA_DIR, "odds_history.json")
OUT = os.path.join(DATA_DIR, "line_movement.json")

STEAM_ML_PP = 2.5     # home implied prob shifted >= this many pp -> moneyline steam
STEAM_TOTAL = 0.5     # total moved >= this many points -> total steam


def _load(p) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _implied(american) -> Optional[float]:
    if american is None:
        return None
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    return 100.0 / (a + 100.0) if a >= 0 else abs(a) / (abs(a) + 100.0)


def _devig_home(ml_home, ml_away) -> Optional[float]:
    ih, ia = _implied(ml_home), _implied(ml_away)
    if ih is None or ia is None or (ih + ia) <= 0:
        return ih
    return ih / (ih + ia)


def run() -> Dict[str, Any]:
    hist = _load(HISTORY).get("history") or {}
    movers: List[Dict[str, Any]] = []
    for key, seq in hist.items():
        if not isinstance(seq, list) or len(seq) < 2:
            continue
        try:
            sport, matchup, gdate = key.split("|")
        except ValueError:
            continue
        o, c = seq[0], seq[-1]   # open, current
        home_open = _devig_home(o.get("ml_home"), o.get("ml_away"))
        home_now = _devig_home(c.get("ml_home"), c.get("ml_away"))
        ml_move_pp = round((home_now - home_open) * 100, 2) if (home_open is not None and home_now is not None) else None
        tot_move = None
        if c.get("total") is not None and o.get("total") is not None:
            tot_move = round(c["total"] - o["total"], 1)

        ml_steam = ml_move_pp is not None and abs(ml_move_pp) >= STEAM_ML_PP
        tot_steam = tot_move is not None and abs(tot_move) >= STEAM_TOTAL
        if ml_move_pp is None and tot_move is None:
            continue
        away, _, home = matchup.partition(" @ ")
        movers.append({
            "sport": sport,
            "matchup": matchup,
            "game_date": gdate,
            "snapshots": len(seq),
            "ml_open": {"home": o.get("ml_home"), "away": o.get("ml_away")},
            "ml_now": {"home": c.get("ml_home"), "away": c.get("ml_away")},
            "ml_move_pp": ml_move_pp,
            "ml_money_toward": (home if (ml_move_pp or 0) > 0 else away) if ml_move_pp else None,
            "total_open": o.get("total"),
            "total_now": c.get("total"),
            "total_move": tot_move,
            "total_money_toward": ("OVER" if (tot_move or 0) > 0 else "UNDER") if tot_move else None,
            "steam": bool(ml_steam or tot_steam),
            "steam_kind": (["ML"] if ml_steam else []) + (["TOTAL"] if tot_steam else []),
        })

    movers.sort(key=lambda m: -max(abs(m.get("ml_move_pp") or 0), abs((m.get("total_move") or 0) * 5)))
    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "source": "ESPN/DraftKings free odds history (no key)",
        "n_games": len(movers),
        "n_steam": sum(1 for m in movers if m["steam"]),
        "thresholds": {"ml_pp": STEAM_ML_PP, "total": STEAM_TOTAL},
        "note": "Open->current move since the line was posted. Home moneyline implied-prob "
                "shift (de-vigged) shows where the money went; total move is over/under steam. "
                "Needs >=2 snapshots per game -- fills in as the heartbeat polls through the day.",
        "movers": movers,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[line-movement] {o['n_games']} games with movement, {o['n_steam']} steam -> {OUT}")
    for m in o["movers"][:8]:
        bits = []
        if m["ml_move_pp"] is not None:
            bits.append(f"ML {m['ml_move_pp']:+.1f}pp -> {m['ml_money_toward']}")
        if m["total_move"] is not None:
            bits.append(f"total {m['total_move']:+.1f} -> {m['total_money_toward']}")
        flag = " [STEAM]" if m["steam"] else ""
        print(f"    {m['sport']:4s} {m['matchup']:14s} {' | '.join(bits)}{flag}")
