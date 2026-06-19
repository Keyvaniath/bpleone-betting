"""
EdgeStat -- golf live tournament alerts.

Detects dramatic shifts in the live leaderboard since the last poll cycle:
  - Lead change (new player at #1)
  - Top-5 churn (a player exited or entered top 5)
  - Big win-prob shifts (P(win) moved >= 10pp for any player)
  - POT (Play of the Tournament) flip (model's top pick changed)

Fires Discord notification on first occurrence of each. State persisted
in .golf_alerted.json so the same event doesn't double-fire.

Output: data/golf_alerts.json + Discord webhook (if DISCORD_WEBHOOK_URL set).
"""
from __future__ import annotations

import os
import json
import urllib.request
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, "golf_state.json")
PROPS_PATH = os.path.join(DATA_DIR, "golf_props.json")
BESTBET_PATH = os.path.join(DATA_DIR, "golf_bestbet.json")
ALERT_LOG = os.path.join(DATA_DIR, "golf_alerts.json")
SEEN_PATH = os.path.join(DATA_DIR, ".golf_alerted.json")


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path: str, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def _discord(content: str):
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    try:
        body = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                      headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8)
        return True
    except Exception as e:
        print(f"  discord post failed: {e}")
        return False


def _touch_idle(note: str):
    """Between tournaments there are no alerts to fire, but still refresh
    golf_alerts.json so it reflects CURRENT (idle) state with a fresh timestamp
    instead of leaving a stale last-tournament snapshot (which never updated and
    perpetually tripped the data-freshness auditor). Preserves the alert log."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    log = _load(ALERT_LOG).get("alerts") or []
    _save(ALERT_LOG, {
        "generated_at": now,
        "tournament": None,
        "note": note,
        "n_new_alerts": 0,
        "alerts": log[-200:],
    })


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    props = _load(PROPS_PATH)
    bestbet = _load(BESTBET_PATH)
    seen = _load(SEEN_PATH) or {}

    t = state.get("active_tournament") or {}
    if not t.get("name") or t.get("is_complete"):
        _touch_idle("no active tournament")
        return {"alerts": [], "note": "no active tournament"}

    tname = t["name"]
    field = state.get("field") or []
    if not field:
        _touch_idle("empty field")
        return {"alerts": [], "note": "empty field"}

    leader = field[0]
    leader_name = leader.get("name")
    top5 = [p.get("name") for p in field[:5]]

    # POT lookup
    pot = (bestbet.get("top_bet") or {})
    pot_player = pot.get("player")
    pot_type = pot.get("type")

    # Win-prob delta — compare to last snapshot
    last_pwins = seen.get("pwins") or {}
    cur_pwins = {p["name"]: p.get("p_win", 0) for p in (props.get("players") or [])}

    alerts = []
    now = dt.datetime.now().isoformat(timespec="seconds")

    # 1. Lead change
    last_leader = seen.get("leader_name")
    if last_leader and last_leader != leader_name:
        alerts.append({
            "type": "LEAD_CHANGE",
            "msg": f"⛳ LEAD CHANGE at {tname}: {leader_name} ({leader.get('total_to_par','?')}) overtakes {last_leader}",
        })

    # 2. Top-5 churn
    last_top5 = set(seen.get("top5") or [])
    cur_top5 = set(top5)
    entered = cur_top5 - last_top5
    exited = last_top5 - cur_top5
    if entered and last_top5:
        alerts.append({
            "type": "TOP5_IN",
            "msg": f"⛳ Top-5 INTO at {tname}: {', '.join(sorted(entered))}",
        })
    if exited and last_top5:
        alerts.append({
            "type": "TOP5_OUT",
            "msg": f"⛳ Top-5 OUT at {tname}: {', '.join(sorted(exited))}",
        })

    # 3. Big win-prob shift (>= 10pp)
    for name, cur in cur_pwins.items():
        prev = last_pwins.get(name, 0)
        delta = cur - prev
        if abs(delta) >= 0.10 and last_pwins:  # only after we have a baseline
            sign = "📈" if delta > 0 else "📉"
            alerts.append({
                "type": "WINPROB_SHIFT",
                "msg": f"{sign} {name} P(win) {prev*100:.1f}% → {cur*100:.1f}% (Δ {delta*100:+.1f}pp) at {tname}",
            })

    # 4. POT flip
    last_pot = seen.get("pot_key")
    cur_pot_key = f"{pot_type}|{pot_player}|{pot.get('opponent','')}" if pot_player else None
    if last_pot and cur_pot_key and last_pot != cur_pot_key:
        alerts.append({
            "type": "POT_FLIP",
            "msg": f"⛳ Play of the Tournament FLIPPED at {tname}: now {pot_player}{' vs ' + pot.get('opponent') if pot.get('opponent') else ''} {pot_type} (fair {pot.get('fair_american','?'):+d})",
        })

    # Fire each new alert exactly once
    seen_alerts = set(seen.get("alerts") or [])
    fired = []
    for a in alerts:
        key = f"{tname}|{a['type']}|{a['msg'][:50]}"
        if key in seen_alerts:
            continue
        seen_alerts.add(key)
        if _discord(a["msg"]):
            a["discord_posted"] = True
        a["fired_at"] = now
        fired.append(a)

    # Update seen snapshot
    new_seen = {
        "leader_name": leader_name,
        "top5": top5,
        "pwins": cur_pwins,
        "pot_key": cur_pot_key,
        "alerts": list(seen_alerts)[-200:],   # cap to last 200
        "last_run": now,
    }
    _save(SEEN_PATH, new_seen)

    # Append fired alerts to log
    log = _load(ALERT_LOG).get("alerts") or []
    log.extend(fired)
    log = log[-200:]      # cap
    _save(ALERT_LOG, {
        "generated_at": now,
        "tournament": tname,
        "n_new_alerts": len(fired),
        "alerts": log,
    })
    return {"alerts": fired, "log_size": len(log)}


if __name__ == "__main__":
    r = run()
    print(f"Golf alerts: {len(r.get('alerts',[]))} new, log size {r.get('log_size','?')}")
    for a in r.get("alerts", []):
        print(f"  {a['type']}: {a['msg']}")
