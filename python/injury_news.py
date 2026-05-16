"""
EdgeStat -- injury-news scraper.

Pulls each MLB team's recent transactions feed (which includes 60-day IL,
15-day IL, day-to-day, paternity, suspension, etc.) and flags any change
that affects a player on tonight's slate (lineup OR open prop).

For each new news item, fires a Discord ping if DISCORD_WEBHOOK_URL is set.

Output: data/injury_news.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Set


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
SEEN_PATH = os.path.join(DATA_DIR, ".injury_news_seen.json")
OUT_PATH = os.path.join(DATA_DIR, "injury_news.json")

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


def _slate_player_ids() -> Set[int]:
    """Every player on tonight's lineups + open-prop list."""
    out: Set[int] = set()
    for g in (_load(MATCHUPS_PATH).get("games") or []):
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                if b.get("id"):
                    out.add(b["id"])
        for p_side in ("home_pitcher", "away_pitcher"):
            p = g.get(p_side) or {}
            if p.get("id"):
                out.add(p["id"])
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        if p.get("player_id"):
            out.add(p["player_id"])
    for p in (_load(PICKEM_PATH).get("props") or []):
        if p.get("player_id"):
            out.add(p["player_id"])
    return out


def run() -> Dict[str, Any]:
    slate_ids = _slate_player_ids()
    seen_data = _load(SEEN_PATH)
    seen_ids = set(seen_data.get("transaction_ids") or [])

    # Pull last 3 days of transactions (covers overnight news + day-of scratches)
    today = dt.date.today()
    start = (today - dt.timedelta(days=3)).isoformat()
    end = today.isoformat()
    data = _http(f"{MLB}/transactions?startDate={start}&endDate={end}") or {}
    txs = data.get("transactions") or []

    new_alerts: List[Dict[str, Any]] = []
    pings = 0
    for tx in txs:
        tx_id = tx.get("id")
        if tx_id in seen_ids:
            continue
        person = tx.get("person") or {}
        pid = person.get("id")
        if pid is None or pid not in slate_ids:
            seen_ids.add(tx_id)
            continue
        ttype = tx.get("typeDesc") or tx.get("typeCode")
        desc = tx.get("description") or ""
        date = tx.get("date") or ""
        # Only alert on injury-related transactions
        is_injury = any(k in (ttype or "").lower() or k in desc.lower() for k in
                         ["injur", " il", "10-day", "15-day", "60-day", "day-to-day", "concuss"])
        if not is_injury:
            seen_ids.add(tx_id)
            continue
        alert = {
            "tx_id": tx_id,
            "date": date,
            "player_id": pid,
            "player": person.get("fullName"),
            "type": ttype,
            "description": desc,
            "team": (tx.get("toTeam") or tx.get("fromTeam") or {}).get("name"),
        }
        new_alerts.append(alert)
        msg = (f"🏥 INJURY NEWS: **{alert['player']}** ({alert['team']}) — {alert['type']}\n"
                f"_{desc}_\nPlayer page: https://betting.bpleone.com/player.html?id={pid}")
        if _send_discord(msg):
            pings += 1
        seen_ids.add(tx_id)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "scanned_window": f"{start} to {end}",
        "n_transactions_scanned": len(txs),
        "n_alerts_new": len(new_alerts),
        "n_pings_sent": pings,
        "alerts": new_alerts,
    }
    with open(SEEN_PATH, "w") as f:
        json.dump({"transaction_ids": sorted(seen_ids),
                   "last_update": dt.datetime.now().isoformat(timespec="seconds")}, f)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Scanned {p['n_transactions_scanned']} transactions, {p['n_alerts_new']} new injury alerts, {p['n_pings_sent']} pings sent")
    for a in p["alerts"][:5]:
        print(f"  - {a['player']:25} ({a['type']}) -- {a['description'][:80]}")
