"""F1 racing scoreboard (events, no head-to-head; just lists upcoming/current race)."""
from __future__ import annotations
import os, json, datetime as dt, urllib.request
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "f1_state.json")
URL = "https://site.api.espn.com/apis/site/v2/sports/racing/f1/scoreboard"


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
        out = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"), "active": False, "n_races": 0, "races": [], "error": "ESPN F1 unreachable"}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f: json.dump(out, f, indent=2)
        return out

    races = []
    for ev in (sb.get("events") or []):
        comps = ev.get("competitions") or []
        # (2026-11-03) an F1 event lists every session (FP1, FP2, FP3, Qual,
        # Race) as a competition; comps[0] is FP1, so the card printed practice
        # as "Final" with a practice start time. Take the competition whose
        # type is the Race (abbreviation "Race" / type id 3); if ESPN has not
        # listed a race session, fall back to the latest session and say which.
        def _ctype(c):
            t = c.get("type") or {}
            return str(t.get("abbreviation") or ""), str(t.get("id") or "")
        race_c = next((c for c in comps if _ctype(c)[0].lower() == "race" or _ctype(c)[1] == "3"), None)
        first = race_c or (comps[-1] if comps else {})
        session = _ctype(first)[0] or None
        status = ((first.get("status") or {}).get("type") or {}) or (ev.get("status") or {}).get("type", {})
        competitors = sorted(first.get("competitors") or [],
                             key=lambda c: (c.get("order") is None, c.get("order") or 0))
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
            "session": session,                                  # (2026-11-03) "Race" unless ESPN lacks one
            "is_race_session": race_c is not None,               # (2026-11-03)
            "weekend_start": ev.get("date"),                     # (2026-11-03) FP1 time, kept for reference
            "start_date": first.get("date") or ev.get("date"),   # (2026-11-03) the selected session's start
            "venue": (ev.get("venue") or {}).get("fullName") or (first.get("venue") or {}).get("fullName"),
            "status": status.get("description"),
            "is_complete": status.get("completed", False),
            "drivers": drivers[:10],
        })

    # (2026-11-03) generated_at is UTC (f1.html labels it UTC; it was local time).
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
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
