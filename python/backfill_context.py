"""
EdgeStat -- one-shot backfill for track_record context tags.

Walks data/track_record.json and, for each settled prop missing the new
`ump` / `venue` / `is_night` context fields, looks up the gamePk for that
player's game on that date (via MLB Stats API schedule), fetches the
boxscore, extracts the HP umpire + venue + day/night, and updates the
record in place.

Result: the vs-umpire panel on /player.html renders against ALL historical
settled props, not just ones settled going forward.

Rate-friendly: caches (date, team) -> gamePk so we don't refetch.
Caps at MAX_BACKFILL_PER_RUN records per execution to stay polite.
Idempotent: skips records that already have ump or venue.

Run manually:  python backfill_context.py [max_records]
"""
from __future__ import annotations

import os
import sys
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
MLB = "https://statsapi.mlb.com/api/v1"
HTTP_TIMEOUT = 10
DEFAULT_MAX = 500

_sched_cache: Dict[str, Dict[str, Any]] = {}     # date -> raw schedule
_box_cache: Dict[int, Dict[str, Any]] = {}        # gamePk -> boxscore


def _http_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _schedule_for_date(date_iso: str) -> Dict[str, Any]:
    if date_iso in _sched_cache:
        return _sched_cache[date_iso]
    data = _http_json(f"{MLB}/schedule?sportId=1&date={date_iso}") or {}
    _sched_cache[date_iso] = data
    return data


def _boxscore(game_pk: int) -> Dict[str, Any]:
    if game_pk in _box_cache:
        return _box_cache[game_pk]
    data = _http_json(f"{MLB}/game/{game_pk}/boxscore") or {}
    _box_cache[game_pk] = data
    return data


def _find_game_for_player(date_iso: str, player_id: int) -> Optional[Dict[str, Any]]:
    """Given a date + player_id, find that player's game's schedule entry."""
    sched = _schedule_for_date(date_iso)
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            # Cheap pre-filter via teams; we'll confirm via boxscore lookup
            pk = g.get("gamePk")
            if pk is None:
                continue
            bs = _boxscore(pk)
            for side in ("home", "away"):
                team = bs.get("teams", {}).get(side, {})
                if f"ID{player_id}" in (team.get("players") or {}):
                    return g
    return None


def _hp_umpire(bs: Dict[str, Any]) -> Optional[str]:
    for o in bs.get("officials") or []:
        kind = (o.get("officialType") or "").lower()
        if "home plate" in kind or "homeplate" in kind:
            return (o.get("official") or {}).get("fullName")
    return None


def run(max_records: int = DEFAULT_MAX) -> Dict[str, Any]:
    if not os.path.exists(TR_PATH):
        print("track_record.json missing -- nothing to do")
        return {"processed": 0, "tagged": 0}
    with open(TR_PATH) as f:
        tr = json.load(f)
    props = tr.get("props") or []
    processed = 0
    tagged = 0
    for r in props:
        if r.get("ump") or r.get("venue"):
            continue  # already enriched
        date = r.get("date")
        pid = r.get("player_id")
        if not date or not pid:
            continue
        if processed >= max_records:
            break
        processed += 1
        sched_entry = _find_game_for_player(date, pid)
        if not sched_entry:
            continue
        pk = sched_entry.get("gamePk")
        bs = _boxscore(pk) if pk else {}
        ump = _hp_umpire(bs)
        venue = (sched_entry.get("venue") or {}).get("name")
        is_night = (sched_entry.get("dayNight") or "").lower() == "night"
        if ump or venue:
            r["ump"] = ump
            r["venue"] = venue
            r["game_pk"] = pk
            r["is_night"] = is_night
            tagged += 1
        if processed % 50 == 0:
            print(f"  processed {processed}, tagged {tagged}, cache {len(_box_cache)} boxscores")
    # Write back
    with open(TR_PATH, "w") as f:
        json.dump(tr, f, indent=2)
    return {"processed": processed, "tagged": tagged,
            "boxscores_fetched": len(_box_cache),
            "schedules_fetched": len(_sched_cache)}


if __name__ == "__main__":
    mx = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MAX
    p = run(mx)
    print(f"\nBackfill complete: processed {p['processed']}, tagged {p['tagged']} "
          f"({p['boxscores_fetched']} boxscores, {p['schedules_fetched']} schedules)")
