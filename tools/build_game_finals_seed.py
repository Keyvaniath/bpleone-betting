"""Build data/game_finals_{nfl,nhl}.json -- every regular-season + playoff final
from ESPN's public scoreboard, last season through yesterday.

The game-lines desk (python/game_lines_desk.py) rates teams with a
margin-of-victory Elo; it needs more history than the rolling 7-14 day
historical_* windows keep. This seed is fetched once (and re-run to extend);
the desk merges each day's finals on top of it, keyed by ESPN event id.

Usage: python tools/build_game_finals_seed.py [nfl|nhl ...]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.request

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASE = "https://site.api.espn.com/apis/site/v2/sports"
SPORTS = {
    # sport: (espn path, first day of last season's regular season)
    "nfl": ("football/nfl", dt.date(2025, 9, 4)),
    "nhl": ("hockey/nhl", dt.date(2025, 10, 7)),
}


def _get(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None


def _final(ev, board_date):
    st = ((ev.get("status") or {}).get("type") or {})
    if not st.get("completed"):
        return None
    stype = ((ev.get("season") or {}).get("type"))
    if stype not in (2, 3):            # 1 = preseason, 4 = off-season / exhibitions
        return None
    comp = (ev.get("competitions") or [{}])[0]
    side = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    h, a = side.get("home"), side.get("away")
    if not h or not a:
        return None
    try:
        hs, as_ = int(h.get("score")), int(a.get("score"))
    except (TypeError, ValueError):
        return None
    return {"id": str(ev.get("id")), "date": board_date, "season": (ev.get("season") or {}).get("year"),
            "season_type": stype, "neutral": bool(comp.get("neutralSite")),
            "home": (h.get("team") or {}).get("abbreviation"), "away": (a.get("team") or {}).get("abbreviation"),
            "home_score": hs, "away_score": as_,
            "ot": (st.get("detail") or "").upper().startswith(("FINAL/OT", "FINAL/SO", "FINAL/2OT"))
                  or "OT" in (st.get("shortDetail") or "").upper() or "SO" in (st.get("shortDetail") or "").upper()}


def build(sport):
    path, start = SPORTS[sport]
    out_path = os.path.join(REPO, "data", f"game_finals_{sport}.json")
    try:
        with open(out_path, encoding="utf-8") as f:
            have = {g["id"]: g for g in json.load(f).get("games") or []}
    except Exception:
        have = {}
    day, end = start, dt.date.today() - dt.timedelta(days=1)
    n_calls = 0
    while day <= end:
        sb = _get(f"{BASE}/{path}/scoreboard?dates={day:%Y%m%d}&limit=100")
        n_calls += 1
        for ev in (sb or {}).get("events") or []:
            g = _final(ev, day.isoformat())
            if g:
                have[g["id"]] = g
        day += dt.timedelta(days=1)
    games = sorted(have.values(), key=lambda g: (g["date"], g["id"]))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "sport": sport,
                   "source": f"ESPN scoreboard {path}, season types 2-3, {start} -> {end}",
                   "n_games": len(games), "games": games}, f, indent=0)
    print(f"{sport}: {len(games)} finals ({n_calls} scoreboard calls) -> {out_path}")


if __name__ == "__main__":
    for s in (sys.argv[1:] or list(SPORTS)):
        build(s)
