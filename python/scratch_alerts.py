"""
EdgeStat -- real-time scratch + game-removal alerter.

Two failure modes for an open prop:
  1. PRE-GAME SCRATCH: player was in posted lineup, got pulled before
     first pitch (illness, DTD that didn't clear, last-minute manager
     decision). Detected by lineup_churn.py diff.
  2. IN-GAME REMOVAL: player was active, got pulled mid-game (injury,
     pinch hit, defensive sub, ejected). Detected from MLB live feed.

For both modes, this module:
  - Identifies the affected open props (DK + PP)
  - Computes the prop's status if locked (still on-pace? broken?)
  - Sends a Discord webhook ping with:
      * Player name + scratch/removal reason
      * Which prop(s) affected, what status now
      * Whether to consider hedging or live-cashing the position
  - Persists a snapshot to avoid double-alerting

State: data/.scratch_alerted.json -- set of (pid, game_pk, reason) tuples
       we've already pinged so we don't re-ping every 10 min.

Output: data/scratch_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LINEUP_CHURN_PATH = os.path.join(DATA_DIR, "lineup_churn.json")
LIVE_PROPS_PATH = os.path.join(DATA_DIR, "live_props.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
ALERTED_PATH = os.path.join(DATA_DIR, ".scratch_alerted.json")
OUT_PATH = os.path.join(DATA_DIR, "scratch_alerts.json")

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
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _load_alerted() -> Set[str]:
    data = _load(ALERTED_PATH)
    return set(data.get("seen", []))


def _save_alerted(seen: Set[str]) -> None:
    with open(ALERTED_PATH, "w") as f:
        json.dump({"seen": sorted(seen),
                   "last_update": dt.datetime.now().isoformat(timespec="seconds")}, f)


def _send_discord(content: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    try:
        body = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception:
        return False


def _detect_in_game_removals() -> List[Dict[str, Any]]:
    """For each in-progress game, check the live feed for substitution events.
    A player is 'removed' if they exited the game. We detect by comparing
    lineup vs current batters/pitchers in the boxscore.

    A more accurate version uses /game/{pk}/feed/live to get the actual
    substitution event types but that payload is large; for now we use
    boxscore + scheduledPitcher comparison."""
    matchups = _load(MATCHUPS_PATH)
    out: List[Dict[str, Any]] = []
    today = dt.date.today().isoformat()
    sched = _http(f"{MLB}/schedule?sportId=1&date={today}") or {}
    in_progress_pks = set()
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            state = (g.get("status") or {}).get("detailedState", "")
            if state not in ("Scheduled", "Pre-Game", "Warmup", "Final", "Game Over"):
                in_progress_pks.add(g.get("gamePk"))

    for game in matchups.get("games") or []:
        gp = game.get("gamePk")
        if gp not in in_progress_pks:
            continue
        bs = _http(f"{MLB}/game/{gp}/boxscore") or {}
        for side_label in ("home", "away"):
            posted = (game.get("lineups") or {}).get(side_label) or []
            team = bs.get("teams", {}).get(side_label, {})
            active_ids = set(team.get("batters") or [])
            for b in posted:
                pid = b.get("id")
                if not pid:
                    continue
                if pid not in active_ids:
                    # Player was in posted lineup but isn't in current batters
                    # -- possible mid-game removal. Check if they had any AB.
                    pkey = f"ID{pid}"
                    pl = (team.get("players") or {}).get(pkey) or {}
                    stats = (pl.get("stats") or {}).get("batting") or {}
                    ab_so_far = int(stats.get("atBats") or 0)
                    # If they have ABs but are no longer in active_ids, they were removed
                    if ab_so_far > 0:
                        out.append({
                            "kind": "in_game_removal",
                            "player_id": pid,
                            "player": b.get("name"),
                            "matchup": game.get("matchup"),
                            "game_pk": gp,
                            "ab_before_removal": ab_so_far,
                            "reason": "no longer in batter list (sub / injury / ejection)",
                        })
    return out


def _props_for_player(pid: int) -> List[Dict[str, Any]]:
    """Open DK + PP props on this player tonight."""
    live = _load(LIVE_PROPS_PATH).get("by_key") or {}
    out = []
    for k, v in live.items():
        if v.get("player_id") == pid:
            out.append(v)
    return out


def run() -> Dict[str, Any]:
    seen = _load_alerted()
    new_alerts: List[Dict[str, Any]] = []

    # 1) PRE-GAME SCRATCHES (from lineup_churn)
    churn = _load(LINEUP_CHURN_PATH)
    for r in (churn.get("removed") or []):
        pid = r.get("id")
        if pid is None:
            continue
        key = f"scratch|{pid}|{r.get('matchup')}"
        if key in seen:
            continue
        props = _props_for_player(pid)
        if not props:
            # No props on this player -- skip alerting
            continue
        new_alerts.append({
            "kind": "scratch",
            "key": key,
            "player_id": pid,
            "player": r.get("player"),
            "matchup": r.get("matchup"),
            "side": r.get("side"),
            "prev_order": r.get("prev_order"),
            "n_affected_props": len(props),
            "affected_props": props,
            "alert_msg": (f"⚠️ SCRATCH: **{r.get('player')}** removed from {r.get('matchup')} "
                          f"({r.get('side')}). {len(props)} open prop(s) affected. "
                          f"View: https://betting.bpleone.com/player.html?id={pid}"),
        })

    # 2) IN-GAME REMOVALS
    removals = _detect_in_game_removals()
    for r in removals:
        key = f"removal|{r['player_id']}|{r['game_pk']}"
        if key in seen:
            continue
        props = _props_for_player(r["player_id"])
        if not props:
            continue
        # Annotate each prop with current status from live_props
        msg_parts = []
        for p in props:
            status = p.get("status", "")
            actual = p.get("actual_so_far")
            line = p.get("line")
            note = (f"  - {p.get('market', '').replace('_',' ')} {p.get('play')} {line}: "
                    f"{actual} so far ({status})")
            msg_parts.append(note)
        new_alerts.append({
            "kind": "in_game_removal",
            "key": key,
            "player_id": r["player_id"],
            "player": r["player"],
            "matchup": r["matchup"],
            "game_pk": r["game_pk"],
            "ab_before_removal": r["ab_before_removal"],
            "n_affected_props": len(props),
            "affected_props": props,
            "alert_msg": (f"🚑 IN-GAME REMOVAL: **{r['player']}** out of {r['matchup']} after "
                          f"{r['ab_before_removal']} AB. {len(props)} open prop(s) affected.\n"
                          + "\n".join(msg_parts)
                          + f"\nPlayer: https://betting.bpleone.com/player.html?id={r['player_id']}"),
        })

    # Fire Discord pings for new alerts
    pings_sent = 0
    for a in new_alerts:
        if _send_discord(a["alert_msg"]):
            pings_sent += 1
        seen.add(a["key"])
    _save_alerted(seen)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_alerts_now": len(new_alerts),
        "n_pings_sent": pings_sent,
        "n_total_seen": len(seen),
        "alerts": new_alerts,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  New alerts this cycle: {p['n_alerts_now']}")
    print(f"  Discord pings sent:    {p['n_pings_sent']}")
    print(f"  Total seen (cumulative): {p['n_total_seen']}")
    for a in p["alerts"]:
        print(f"  - [{a['kind']}] {a['player']} -- {a['n_affected_props']} props affected")
