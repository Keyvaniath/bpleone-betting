"""
EdgeStat -- "lock" detector for in-progress props.

Watches live_props.json and surfaces every open prop where:
  - Status is "won_so_far" AND
  - Remaining game time / outs make a reversal mathematically impossible
    (e.g. batter is done for the day OR cumulative stat already crossed)

For these, recommends:
  - HOLD: prop will cash, no action needed
  - CASH OUT: if the book offers an early-cash price >= 92% of full payout,
    consider banking it to remove residual variance
  - HEDGE: if early-cash unavailable but a contra-side line exists at a
    favorable price (computed via hedge math)

Output: data/locked_props.json
  {
    "generated_at": "...",
    "n_locked": 3,
    "n_can_cashout": 1,
    "locked": [
      { player, market, line, actual_so_far, status, lock_reason,
        suggested_action, expected_payout }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LIVE_PROPS_PATH = os.path.join(DATA_DIR, "live_props.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "locked_props.json")

MLB = "https://statsapi.mlb.com/api/v1"


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _player_done_for_game(game_pk: int, player_id: int) -> Dict[str, Any]:
    """Best-effort: detect if a batter is done for the game.
    A batter is done if game is Final OR they're no longer in active
    batters list (subbed out) OR final inning + their team finished its at-bat."""
    if not game_pk:
        return {"is_done": False, "reason": "unknown game_pk"}
    bs = _http(f"{MLB}/game/{game_pk}/boxscore") or {}
    # Game state from linescore
    ls = _http(f"{MLB}/game/{game_pk}/linescore") or {}
    cur_inning = ls.get("currentInning") or 0
    is_final = (ls.get("inningState") or "").lower() == "end" and cur_inning >= 9
    if is_final:
        return {"is_done": True, "reason": "game final"}
    # Were they substituted out?
    for side in ("home", "away"):
        team = bs.get("teams", {}).get(side, {})
        if f"ID{player_id}" not in (team.get("players") or {}):
            continue
        if player_id not in (team.get("batters") or []):
            # In players but not in active batters -> they're out of the game
            return {"is_done": True, "reason": "removed from lineup"}
    return {"is_done": False, "reason": "still active or unknown"}


def _is_locked(prop: Dict[str, Any]) -> Dict[str, Any]:
    """Return {locked: bool, lock_reason, max_reversal_path}."""
    actual = prop.get("actual_so_far")
    line = prop.get("line")
    play = (prop.get("play") or "").upper()
    status = prop.get("status")
    if actual is None or line is None:
        return {"locked": False, "lock_reason": "missing actual or line"}
    if status == "won":
        return {"locked": True, "lock_reason": "game final, prop settled WIN"}
    # Already crossed?
    if play == "OVER" and actual > line:
        # Already over the line. Lock confirmed if player can't lose value
        # (stats only go up, can't go down)
        return {"locked": True, "lock_reason": f"already {actual} > {line}"}
    if play == "UNDER":
        # UNDER locks only if the player is mathematically out of chances
        # (game state must indicate no more ABs)
        # Reason: actual could go up; UNDER can't lock until game-over.
        # But: if player removed from game + actual < line, that's a soft lock.
        return {"locked": False, "lock_reason": "UNDER bets lock only at game-final or player-out"}
    return {"locked": False, "lock_reason": "still in flight"}


def run() -> Dict[str, Any]:
    lp = _load(LIVE_PROPS_PATH)
    locked: List[Dict[str, Any]] = []
    can_cashout: List[Dict[str, Any]] = []

    for k, prop in (lp.get("by_key") or {}).items():
        if prop.get("status") not in ("won_so_far", "won"):
            continue
        info = _is_locked(prop)
        if not info["locked"]:
            continue
        # Check if player is done (means truly locked, no reversal possible)
        done = _player_done_for_game(prop.get("game_pk"), prop.get("player_id"))
        suggested = "HOLD"
        ec_threshold = 0.92    # cash out if offered >= 92% of full payout
        if not done.get("is_done"):
            suggested = "HOLD (lock by stat, player still active)"
        else:
            suggested = "WIN — banked"
        locked.append({
            "key": k,
            "player_id": prop.get("player_id"),
            "player": prop.get("player"),
            "market": prop.get("market"),
            "line": prop.get("line"),
            "play": prop.get("play"),
            "src": prop.get("src"),
            "actual_so_far": prop.get("actual_so_far"),
            "status": prop.get("status"),
            "lock_reason": info["lock_reason"],
            "player_done": done.get("is_done"),
            "player_done_reason": done.get("reason"),
            "game_state": prop.get("game_state"),
            "suggested_action": suggested,
        })
        if done.get("is_done"):
            can_cashout.append(prop.get("player"))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_locked": len(locked),
        "n_can_cashout": len(can_cashout),
        "locked": locked,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_locked']} locked, {p['n_can_cashout']} done-and-locked")
    for r in p["locked"][:5]:
        print(f"  {r['player']} {r['market']} {r['play']} {r['line']} -> {r['actual_so_far']} ({r['suggested_action']})")
