"""F1 racing scoreboard (events, no head-to-head; just lists upcoming/current race)."""
from __future__ import annotations
import os, json, datetime as dt, urllib.request
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "f1_state.json")
URL = "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def run() -> Dict[str, Any]:
    sb = _http(URL)
    if not sb:
        out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "active": False, "n_races": 0, "races": [], "error": "ESPN F1 unreachable"}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(out, f, indent=2)
        return out

    races = []
    for ev in (sb.get("events") or []):
        status = (ev.get("status") or {}).get("type", {})
        comps = ev.get("competitions") or []
        first = comps[0] if comps else {}
        competitors = first.get("competitors") or []
        # F1 events have many drivers; pull top 10 by position
        drivers = []
        for c in competitors[:15]:
            athlete = c.get("athlete") or {}
            drivers.append({
                "position": c.get("order"),
                "driver": athlete.get("displayName"),
                "team": (c.get("driver") or {}).get("team", {}).get("displayName") if isinstance(c.get("driver"), dict) else None,
                "status": (c.get("status") or {}).get("type", {}).get("description"),
            })
        races.append({
            "id": ev.get("id"),
            "name": ev.get("name"),
            "short_name": ev.get("shortName"),
            "start_date": ev.get("date"),
            "venue": (ev.get("venue") or {}).get("fullName") or (first.get("venue") or {}).get("fullName"),
            "status": status.get("description"),
            "is_complete": status.get("completed", False),
            "drivers": drivers[:10],
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active": len(races) > 0,
        "league": "F1",
        "n_races": len(races),
        "races": races,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"F1: {p['n_races']} races")
    for r in p["races"]:
        print(f"  {r['name']} @ {r['venue']} -- {r['status']}")
        for d in r["drivers"][:5]:
            print(f"    P{d['position']}: {d['driver']}")
