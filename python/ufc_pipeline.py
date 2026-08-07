"""UFC fight card scoreboard (next/current event + fights with fighter records)."""
from __future__ import annotations
import os, json, datetime as dt, urllib.request
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "ufc_state.json")
URL = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def run() -> Dict[str, Any]:
    sb = _http(URL)
    if not sb:
        out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "active": False, "n_events": 0, "events": [], "error": "ESPN UFC unreachable"}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(out, f, indent=2)
        return out

    events = []
    for ev in (sb.get("events") or []):
        status = (ev.get("status") or {}).get("type", {})
        fights = []
        for c in (ev.get("competitions") or [])[:15]:
            fighters = c.get("competitors") or []
            if len(fighters) < 2: continue
            a = fighters[0]
            b = fighters[1]
            a_athlete = a.get("athlete") or {}
            b_athlete = b.get("athlete") or {}
            fights.append({
                "id": c.get("id"),
                # ESPN puts weight class in type.abbreviation -- the .text key
                # does not exist and falling back to c.get("date") returned a
                # timestamp ("2026-05-30T08:00Z") instead. Fixed to use the
                # right field.
                "weight_class": (c.get("type") or {}).get("abbreviation") or (c.get("type") or {}).get("text") or "Unknown",
                "fighter_a": a_athlete.get("displayName"),
                "fighter_b": b_athlete.get("displayName"),
                "fighter_a_record": (a.get("records") or [{}])[0].get("summary"),
                "fighter_b_record": (b.get("records") or [{}])[0].get("summary"),
                "winner": a_athlete.get("displayName") if a.get("winner") else b_athlete.get("displayName") if b.get("winner") else None,
                "status": (c.get("status") or {}).get("type", {}).get("description"),
            })
        events.append({
            "id": ev.get("id"),
            "name": ev.get("name"),
            "start_date": ev.get("date"),
            "venue": (ev.get("venue") or {}).get("fullName"),
            "status": status.get("description"),
            "n_fights": len(fights),
            "fights": fights,
        })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active": len(events) > 0,
        "league": "UFC",
        "n_events": len(events),
        "events": events,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"UFC: {p['n_events']} events")
    for e in p["events"]:
        print(f"  {e['name']} @ {e['venue']} -- {e['n_fights']} fights")
        for f in e["fights"][:5]:
            print(f"    {f['fighter_a']} ({f['fighter_a_record']}) vs {f['fighter_b']} ({f['fighter_b_record']})")
