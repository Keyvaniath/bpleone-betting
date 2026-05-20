"""
EdgeStat -- LIVE alerter (real-time in-game edges + lock notifications).

Runs every live-games cron (10 min) and fires Discord webhooks for:

   LOCKED_WON   prop just clinched -> cash out at the book or hold
   LOCKED_LOST  prop just broke    -> move on
   STEAM        sharp money 5+pp shift toward our pick
   AT_RISK      lock dropped into <40% live -> consider hedge
   LIVE_EDGE    model live WP diverges 8+pp from book live ML

State (data/.live_alerted.json) prevents duplicate alerts -- each
event ID is fired only once.

Webhook URL from env DISCORD_WEBHOOK_URL (set as GitHub secret).
Silently stubs out when no webhook configured.
"""
from __future__ import annotations

import os
import json
import urllib.request
import urllib.error
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATE_PATH = os.path.join(DATA_DIR, ".live_alerted.json")
OUT = os.path.join(DATA_DIR, "live_alerts.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _post_discord(content: str) -> bool:
    if not WEBHOOK: return False
    try:
        body = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(
            WEBHOOK, data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status in (200, 204)
    except Exception:
        return False


def run() -> Dict[str, Any]:
    state = _load(STATE_PATH)
    fired_ids = set(state.get("fired_ids") or [])
    new_alerts: List[Dict[str, Any]] = []
    new_fired: List[str] = []

    # 1. In-game lock transitions (LOCKED_WON / LOCKED_LOST / AT_RISK)
    locks = _load(os.path.join(DATA_DIR, "in_game_locks.json"))
    for r in (locks.get("all") or []):
        status = r.get("status")
        if status not in ("LOCKED_WON", "LOCKED_LOST", "AT_RISK"): continue
        # Don't alert if game hasn't started (status is ON_TRACK at I0 etc.)
        if r.get("stat_val") is None and r.get("detail", "").startswith("0 thru I0"): continue
        alert_id = f"lock|{r.get('pick_id')}|{status}"
        if alert_id in fired_ids: continue
        emoji = {"LOCKED_WON": "✅", "LOCKED_LOST": "❌", "AT_RISK": "⚠️"}.get(status, "🔔")
        msg = (f"{emoji} **{status.replace('_', ' ')}** -- {r.get('player_or_matchup')} "
               f"{r.get('market','?')} -- {r.get('detail','')}")
        new_alerts.append({"type": status, "id": alert_id, "message": msg, "pick": r})
        new_fired.append(alert_id)

    # 2. Sharp action STEAM signals
    sharp = _load(os.path.join(DATA_DIR, "sharp_action_radar.json"))
    for s in (sharp.get("positive_signals") or []):
        if s.get("intensity") not in ("STRONG", "ELITE"): continue
        alert_id = f"sharp|{s.get('matchup')}|{s.get('market')}|{round(s.get('shift_pp',0))}"
        if alert_id in fired_ids: continue
        msg = (f"📡 **SHARP STEAM ({s['intensity']})** -- {s['matchup']} {s['market']}: "
               f"line moved {s['opening_implied_pct']}% -> {s['latest_implied_pct']}% "
               f"(+{s['shift_pp']:.1f}pp toward our pick)")
        new_alerts.append({"type": "SHARP_STEAM", "id": alert_id, "message": msg, "signal": s})
        new_fired.append(alert_id)

    # 3. Live edge divergence (model vs book live ML)
    live_edges = _load(os.path.join(DATA_DIR, "live_edges.json"))
    for e in (live_edges.get("edges") or [])[:10]:
        edge_pp = e.get("edge_pp") or 0
        if abs(edge_pp) < 8: continue
        alert_id = f"liveedge|{e.get('matchup')}|{round(edge_pp)}"
        if alert_id in fired_ids: continue
        side = "favorable" if edge_pp > 0 else "fade"
        msg = (f"⚡ **LIVE EDGE** -- {e.get('matchup','?')} I{e.get('inning','?')}: "
               f"model {(e.get('model_p',0)*100):.0f}% vs book {(e.get('book_implied',0)*100):.0f}% "
               f"({edge_pp:+.1f}pp {side})")
        new_alerts.append({"type": "LIVE_EDGE", "id": alert_id, "message": msg, "edge": e})
        new_fired.append(alert_id)

    # 4. Pipeline health critical
    health = _load(os.path.join(DATA_DIR, "pipeline_health.json"))
    if health.get("overall_status") == "CRITICAL":
        # Once per day for staleness alerts
        date_key = f"health|critical|{dt.date.today().isoformat()}"
        if date_key not in fired_ids:
            msg = f"🚨 **PIPELINE STALE** -- {health.get('suggested_action','data freshness critical')}"
            new_alerts.append({"type": "PIPELINE_STALE", "id": date_key, "message": msg})
            new_fired.append(date_key)

    # Fire to Discord (rate-limited: max 6 per cycle to avoid spam)
    sent_count = 0
    for a in new_alerts[:6]:
        if _post_discord(a["message"]):
            sent_count += 1

    # Persist fired IDs (cap at 5000 entries)
    fired_ids.update(new_fired)
    if len(fired_ids) > 5000:
        fired_ids = set(list(fired_ids)[-5000:])
    with open(STATE_PATH, "w") as f:
        json.dump({"fired_ids": list(fired_ids),
                    "last_run": dt.datetime.now().isoformat(timespec="seconds")}, f)

    # Public-readable alerts log (latest only)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "webhook_configured": bool(WEBHOOK),
        "n_new_alerts": len(new_alerts),
        "n_sent_to_discord": sent_count,
        "alerts": new_alerts,
    }
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Live alerter: {p['n_new_alerts']} new alerts (webhook: {'YES' if p['webhook_configured'] else 'NO'})")
    print(f"  Sent to Discord: {p['n_sent_to_discord']}")
    for a in p["alerts"][:10]:
        print(f"  [{a['type']}] {a['message'][:100]}")
