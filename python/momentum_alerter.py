"""
EdgeStat -- live momentum alert dispatcher.

Reads live_momentum.json each cycle. Tracks which alerts have ALREADY been
fired (in .momentum_alerted.json) so we don't double-post.

For BIG_SWING / REVERSAL / SUSTAINED alerts: posts to Discord webhook if
DISCORD_WEBHOOK_URL is set, otherwise just logs to alerts file.

Output: data/momentum_history.json -- rolling history of every alert fired
        data/.momentum_alerted.json -- state of what's been fired
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MOMENTUM_PATH = os.path.join(DATA_DIR, "live_momentum.json")
STATE_PATH = os.path.join(DATA_DIR, ".momentum_alerted.json")
HISTORY_PATH = os.path.join(DATA_DIR, "momentum_history.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _post_discord(content: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url: return False
    try:
        data = json.dumps({"content": content}).encode()
        req = urllib.request.Request(url, data=data,
                                       headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 204
    except Exception:
        return False


# Alert priority: which types are worth pinging?
HIGH_PRIORITY = {"BIG_SWING_HOME", "BIG_SWING_AWAY", "REVERSAL_HOME", "REVERSAL_AWAY"}
MED_PRIORITY = {"SUSTAINED_HOME", "SUSTAINED_AWAY"}


def run() -> Dict[str, Any]:
    momentum = _load(MOMENTUM_PATH)
    state = _load(STATE_PATH) or {"fired_keys": []}
    history = _load(HISTORY_PATH) or {"entries": []}
    fired = set(state.get("fired_keys") or [])
    now_iso = dt.datetime.now().isoformat(timespec="seconds")

    posted: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []

    for alert in momentum.get("alerts") or []:
        atype = alert.get("alert_type")
        if not atype: continue
        # Build unique key per (game, alert_type, swing direction)
        key = f"{alert.get('game_pk')}|{atype}|{alert.get('p_home_win_now',0)*100:.0f}"
        priority = "HIGH" if atype in HIGH_PRIORITY else "MED" if atype in MED_PRIORITY else "LOW"
        if priority == "LOW": continue
        if key in fired:
            suppressed.append({"key": key, "reason": "already-fired"})
            continue
        fired.add(key)
        # Build message
        msg = (f"⚡ **{atype.replace('_',' ')}** | {alert['matchup']} {alert['score']}\n"
               f"P(home) {alert.get('p_home_win_prev', '?')*100:.1f}% → "
               f"{alert['p_home_win_now']*100:.1f}% "
               f"({'+' if (alert['delta_pp'] or 0) > 0 else ''}{alert['delta_pp']:.1f}pp) "
               f"| sustain={alert['sustained_n']}")
        posted_ok = _post_discord(msg)
        record = {
            "ts": now_iso, "key": key, "priority": priority,
            "alert_type": atype, "matchup": alert["matchup"], "score": alert["score"],
            "p_home_win_now": alert["p_home_win_now"], "delta_pp": alert["delta_pp"],
            "sustained_n": alert["sustained_n"], "posted_to_discord": posted_ok,
            "msg": msg,
        }
        posted.append(record)
        history.setdefault("entries", []).append(record)

    # Cap history at 1000 entries
    history["entries"] = history["entries"][-1000:]
    state["fired_keys"] = list(fired)[-2000:]   # cap to avoid growing forever

    payload = {
        "generated_at": now_iso,
        "n_alerts_seen": len(momentum.get("alerts") or []),
        "n_posted": len(posted),
        "n_suppressed_already_fired": len(suppressed),
        "posted_now": posted,
        "discord_configured": bool(os.environ.get("DISCORD_WEBHOOK_URL")),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f: json.dump(state, f, indent=2)
    with open(HISTORY_PATH, "w") as f: json.dump(history, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Momentum alerter: {p['n_alerts_seen']} alerts seen, "
          f"{p['n_posted']} posted, {p['n_suppressed_already_fired']} suppressed (already fired)")
    print(f"  Discord configured: {p['discord_configured']}")
    for r in p["posted_now"]:
        print(f"  [{r['priority']}] {r['alert_type']:18s} {r['matchup']:45s} delta={r['delta_pp']:+.1f}pp posted={r['posted_to_discord']}")
