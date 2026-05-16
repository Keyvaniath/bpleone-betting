"""
EdgeStat -- slate-wide steam radar (multi-cycle line-move tracker).

Maintains a rolling history of the last 5 line snapshots per prop and
detects "steam moves" -- consistent directional movement across 3+
consecutive cycles. Different from line_timing.py (cycle-over-cycle) by
looking at the FULL trajectory.

A steam alert means the market is moving in one direction repeatedly --
sharp money is hitting it. Fade or follow depending on your read.

Output: data/steam_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
HISTORY_PATH = os.path.join(DATA_DIR, ".line_history.json")
OUT_PATH = os.path.join(DATA_DIR, "steam_alerts.json")

MAX_HISTORY = 5
STEAM_MIN_CYCLES = 3
STEAM_MIN_CENTS = 12     # cumulative move of 12+ cents across 3 cycles = steam


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _key(p):
    return f"{p.get('player_id')}|{p.get('market')}|{p.get('line')}"


def run() -> Dict[str, Any]:
    props = _load(PROPS_PATH).get("top_edges") or []
    history = _load(HISTORY_PATH).get("by_key") or {}
    now_iso = dt.datetime.now().isoformat(timespec="seconds")
    new_history: Dict[str, List[Dict[str, Any]]] = {}
    alerts: List[Dict[str, Any]] = []

    for p in props:
        k = _key(p)
        prev = history.get(k) or []
        snap = {
            "ts": now_iso,
            "over": p.get("dk_over"),
            "under": p.get("dk_under"),
        }
        new_hist = (prev + [snap])[-MAX_HISTORY:]
        new_history[k] = new_hist
        if len(new_hist) < STEAM_MIN_CYCLES:
            continue

        # Look at the last 3 (or 5) overs and unders -- detect monotonic move
        for side in ("over", "under"):
            prices = [s[side] for s in new_hist if s.get(side) is not None]
            if len(prices) < STEAM_MIN_CYCLES:
                continue
            tail = prices[-STEAM_MIN_CYCLES:]
            cumulative_move = tail[-1] - tail[0]
            # Is it monotonic? Each step in same direction?
            monotonic = all((tail[i + 1] - tail[i]) * (tail[1] - tail[0]) >= 0
                            for i in range(len(tail) - 1))
            if monotonic and abs(cumulative_move) >= STEAM_MIN_CENTS:
                alerts.append({
                    "player": p.get("player"),
                    "player_id": p.get("player_id"),
                    "market": p.get("market"),
                    "line": p.get("line"),
                    "side_moving": side.upper(),
                    "history": tail,
                    "cumulative_move_cents": cumulative_move,
                    "direction": "sharpening" if cumulative_move < 0 else "softening",
                    "note": ("Line has moved consistently against this side -- sharp money flowing"
                             if cumulative_move < 0
                             else "Line has drifted toward this side -- public money / soft action"),
                })

    alerts.sort(key=lambda a: -abs(a["cumulative_move_cents"]))

    payload = {
        "generated_at": now_iso,
        "n_props_tracked": len(new_history),
        "n_alerts": len(alerts),
        "alerts": alerts[:40],
    }
    with open(HISTORY_PATH, "w") as f:
        json.dump({"by_key": new_history, "last_update": now_iso}, f)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_props_tracked']} props, {p['n_alerts']} steam alerts")
    for a in p["alerts"][:6]:
        print(f"  {a['player']:25} {a['market']:25} {a['side_moving']:6} {a['cumulative_move_cents']:+5d}c ({a['direction']})")
