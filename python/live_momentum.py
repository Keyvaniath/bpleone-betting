"""
EdgeStat -- live game momentum tracker.

Each live-games poll snapshots P(home_win) for every in-progress MLB game.
This module computes the SWING between the prior snapshot and the current:
  - magnitude: |p_now - p_prev|
  - direction: HOME_GAINED / AWAY_GAINED
  - sustained_n: how many consecutive polls the trend held
  - reversal flag: if direction flipped within last 2 polls

High-magnitude sustained swings = momentum bets (back the team riding it).
High-magnitude reversals = mean-reversion bets (fade the recent move).

Persists state in data/.live_momentum_state.json so the next poll can
compute deltas. Output: data/live_momentum.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LIVE_STATE_PATH = os.path.join(DATA_DIR, "live_state.json")
STATE_PATH = os.path.join(DATA_DIR, ".live_momentum_state.json")
OUT_PATH = os.path.join(DATA_DIR, "live_momentum.json")

SWING_THRESHOLD = 0.05  # 5pp swing = noticeable
BIG_SWING = 0.10        # 10pp = big


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    live = _load(LIVE_STATE_PATH)
    prev_state = _load(STATE_PATH)
    polled_at = live.get("polled_at") or dt.datetime.now().isoformat(timespec="seconds")

    momentum: List[Dict[str, Any]] = []
    new_state: Dict[str, Any] = {}
    for g in live.get("games") or []:
        pk = str(g.get("game_pk"))
        if not pk: continue
        p_now = g.get("p_home_win")
        if p_now is None: continue
        prev = prev_state.get(pk, {})
        p_prev = prev.get("p_home_win")
        prev_dir = prev.get("last_direction")
        sustained_n = prev.get("sustained_n", 0)
        history = prev.get("history", [])
        history.append({"polled_at": polled_at, "p_home_win": round(p_now, 4)})
        history = history[-10:]  # keep last 10 polls

        if p_prev is not None:
            delta = p_now - p_prev
            abs_delta = abs(delta)
            cur_dir = "HOME" if delta > 0.005 else "AWAY" if delta < -0.005 else "FLAT"
            reversal = (cur_dir != "FLAT" and prev_dir and prev_dir != "FLAT" and cur_dir != prev_dir)
            if cur_dir == prev_dir and cur_dir != "FLAT":
                sustained_n += 1
            elif cur_dir != "FLAT":
                sustained_n = 1
            else:
                sustained_n = 0
        else:
            delta = 0.0
            abs_delta = 0.0
            cur_dir = "FLAT"
            reversal = False
            sustained_n = 0

        # Build alert
        alert_type = None
        if abs_delta >= BIG_SWING:
            alert_type = "BIG_SWING_" + cur_dir
        elif abs_delta >= SWING_THRESHOLD:
            alert_type = "SWING_" + cur_dir
        if reversal and abs_delta >= SWING_THRESHOLD:
            alert_type = "REVERSAL_" + cur_dir
        if sustained_n >= 3 and abs_delta >= 0.01:
            alert_type = "SUSTAINED_" + cur_dir

        momentum.append({
            "matchup": f"{g.get('away','?')} @ {g.get('home','?')}",
            "game_pk": int(pk) if pk.isdigit() else pk,
            "score": f"{g.get('away_runs',0)}-{g.get('home_runs',0)}",
            "state": g.get("state"),
            "p_home_win_prev": p_prev,
            "p_home_win_now": p_now,
            "delta_pp": round(delta * 100, 1) if p_prev is not None else None,
            "direction": cur_dir,
            "sustained_n": sustained_n,
            "reversal": reversal,
            "alert_type": alert_type,
        })
        new_state[pk] = {
            "p_home_win": p_now,
            "last_direction": cur_dir,
            "sustained_n": sustained_n,
            "history": history,
        }

    # Sort by abs delta desc
    momentum.sort(key=lambda m: -abs(m.get("delta_pp") or 0))
    alerts = [m for m in momentum if m.get("alert_type")]

    payload = {
        "generated_at": polled_at,
        "n_games": len(momentum),
        "n_alerts": len(alerts),
        "games": momentum,
        "alerts": alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    with open(STATE_PATH, "w") as f: json.dump(new_state, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Live momentum: {p['n_games']} games tracked, {p['n_alerts']} alerts")
    for m in p["games"]:
        marker = f"[{m['alert_type']}]" if m.get("alert_type") else ""
        delta_str = f"{m['delta_pp']:+.1f}pp" if m.get("delta_pp") is not None else "first-poll"
        print(f"  {m['matchup']:45s} {m['score']:6s} P_now={m['p_home_win_now']*100:5.1f}% {delta_str:10s} dir={m['direction']:4s} sustain={m['sustained_n']} {marker}")
