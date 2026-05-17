"""
EdgeStat -- esports + KBO live alerts (Discord webhook).

Mirrors golf_alerts.py pattern. Detects:
  - LoL series score change (e.g. 1-0 → 1-1 → 2-1 swing)
  - CS map result swing (rare for now since no live feed)
  - KBO score changes (when koreabaseball.com starts returning live)
  - POT flip across any of the three sports

State: data/.esports_alerted.json (dedup across cron cycles)
Output: data/esports_alerts.json (rolling log) + Discord webhook
"""
from __future__ import annotations

import os
import json
import urllib.request
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SEEN_PATH = os.path.join(DATA_DIR, ".esports_alerted.json")
LOG_PATH = os.path.join(DATA_DIR, "esports_alerts.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f: json.dump(payload, f, indent=2)


def _discord(content: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return False
    try:
        body = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                      headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8)
        return True
    except Exception:
        return False


def _lol_alerts(seen: Dict[str, Any]) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, "lol_state.json"))
    alerts: List[Dict[str, Any]] = []
    now = dt.datetime.now().isoformat(timespec="seconds")
    last_scores = seen.get("lol_scores") or {}
    cur_scores = {}
    for m in (state.get("live_matches") or []):
        mid = str(m.get("id"))
        a = m.get("team_a"); b = m.get("team_b")
        s_a = m.get("team_a_score") or 0
        s_b = m.get("team_b_score") or 0
        cur_scores[mid] = (s_a, s_b)
        prev = last_scores.get(mid, (0, 0))
        if (s_a, s_b) != tuple(prev):
            # Score advanced
            if s_a > prev[0]:
                alerts.append({"type": "LOL_MAP_WIN", "msg":
                    f"🎮 [{m.get('league')}] {a} wins map vs {b} (series: {s_a}-{s_b}, BO{m.get('best_of')})"})
            elif s_b > prev[1]:
                alerts.append({"type": "LOL_MAP_WIN", "msg":
                    f"🎮 [{m.get('league')}] {b} wins map vs {a} (series: {s_a}-{s_b}, BO{m.get('best_of')})"})
    seen["lol_scores"] = cur_scores
    return alerts


def _pot_flip_alerts(seen: Dict[str, Any]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    last_pots = seen.get("pots") or {}
    cur_pots = {}
    for sport, file in (("LOL", "lol_bestbet.json"),
                         ("CS", "cs_bestbet.json"),
                         ("KBO", "kbo_bestbet.json")):
        bb = _load(os.path.join(DATA_DIR, file))
        pot = bb.get("top_bet") or {}
        if not pot:
            continue
        key = f"{pot.get('kind','ML')}|{pot.get('team','')}|{pot.get('opponent','')}"
        cur_pots[sport] = key
        prev = last_pots.get(sport)
        if prev and prev != key:
            alerts.append({
                "type": f"{sport}_POT_FLIP",
                "msg": f"⚡ {sport} Play of the Day flipped: now {pot.get('team')} {pot.get('kind','ML')} "
                       f"(fair {pot.get('fair_american','?')}, {pot.get('confidence','MED')})"
            })
    seen["pots"] = cur_pots
    return alerts


def run() -> Dict[str, Any]:
    seen = _load(SEEN_PATH) or {}
    alerts: List[Dict[str, Any]] = []
    alerts.extend(_lol_alerts(seen))
    alerts.extend(_pot_flip_alerts(seen))

    seen_alert_keys = set(seen.get("alerts") or [])
    fired = []
    now = dt.datetime.now().isoformat(timespec="seconds")
    for a in alerts:
        key = f"{a['type']}|{a['msg'][:60]}"
        if key in seen_alert_keys:
            continue
        seen_alert_keys.add(key)
        if _discord(a["msg"]):
            a["discord_posted"] = True
        a["fired_at"] = now
        fired.append(a)

    seen["alerts"] = list(seen_alert_keys)[-200:]
    seen["last_run"] = now
    _save(SEEN_PATH, seen)

    log = _load(LOG_PATH).get("alerts") or []
    log.extend(fired)
    log = log[-200:]
    _save(LOG_PATH, {
        "generated_at": now,
        "n_new_alerts": len(fired),
        "alerts": log,
    })
    return {"new_alerts": len(fired), "alerts": fired}


if __name__ == "__main__":
    r = run()
    print(f"Esports alerts: {r['new_alerts']} new")
    for a in r["alerts"]:
        print(f"  [{a['type']}] {a['msg']}")
