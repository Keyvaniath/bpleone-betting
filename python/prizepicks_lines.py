"""
EdgeStat -- FREE multi-sport PrizePicks lines feed.

PrizePicks' public projections API is free (no key) and carries the real,
current player-prop menu -- the lines + the flat-payout format that IS the
market for pick'em. pickem.py already pulls MLB; this pulls EVERY in-season
PrizePicks league so the props value board isn't MLB-only.

PrizePicks is flat-payout, so there are no per-prop odds to fetch -- the line
itself plus the fixed multiplier is the whole market, and the model's CALIBRATED
probability vs the flat break-even is the edge (prizepicks_value.py). This makes
the player-prop product fully free; the only thing still paid-gated is a
sportsbook's player-prop line for a soft-line cross-check (ESPN's free feed is
game-lines only, and a book's prop API is fragile / ToS-gray).

Output: data/prizepicks_lines.json -> the live PrizePicks menu, all sports.
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "prizepicks_lines.json")
PP_API = "https://api.prizepicks.com/projections"

# PrizePicks league ids (in-season set; off-season ids just return nothing).
LEAGUES = {"MLB": 2, "WNBA": 3, "NBA": 7, "NHL": 8}

# PrizePicks sits behind Cloudflare; a bare UA gets 403. Browser-style headers.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://app.prizepicks.com",
    "Referer": "https://app.prizepicks.com/",
}


def _fetch(league_id: int) -> Dict[str, Any]:
    url = f"{PP_API}?league_id={league_id}&per_page=1000&single_stat=true"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _player_index(included: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for inc in included or []:
        if inc.get("type") in ("new_player", "player"):
            a = inc.get("attributes") or {}
            idx[str(inc.get("id"))] = {
                "name": a.get("display_name") or a.get("name"),
                "team": a.get("team") or a.get("team_name"),
                "position": a.get("position"),
            }
    return idx


def fetch_league(sport: str, league_id: int) -> List[Dict[str, Any]]:
    try:
        d = _fetch(league_id)
    except Exception as e:
        print(f"[pp-lines] {sport} fetch failed: {e!r}")
        return []
    players = _player_index(d.get("included") or [])
    rows: List[Dict[str, Any]] = []
    for p in (d.get("data") or []):
        a = p.get("attributes") or {}
        if a.get("odds_type") and a.get("odds_type") != "standard":
            continue  # skip demon/goblin alt-payout lines -- keep the standard board
        pid = str((((p.get("relationships") or {}).get("new_player") or {}).get("data") or {}).get("id"))
        pl = players.get(pid) or {}
        line = a.get("line_score")
        if line is None or not pl.get("name"):
            continue
        rows.append({
            "sport": sport,
            "player": pl.get("name"),
            "team": pl.get("team") or a.get("description"),
            "stat_type": a.get("stat_type"),
            "line": line,
            "start_time": a.get("start_time"),
        })
    return rows


def run(leagues: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    leagues = leagues or LEAGUES
    lines: List[Dict[str, Any]] = []
    for i, (sport, lid) in enumerate(leagues.items()):
        if i:
            time.sleep(1.5)   # be polite -- PrizePicks rate-limits rapid hits (429)
        lines.extend(fetch_league(sport, lid))
    by_sport: Dict[str, int] = {}
    for r in lines:
        by_sport[r["sport"]] = by_sport.get(r["sport"], 0) + 1
    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "source": "prizepicks public projections API (free, no key)",
        "format": "flat-payout pick'em -- the line + fixed multiplier is the whole market; "
                  "edge = model calibrated prob vs the per-leg break-even (see prizepicks-value).",
        "n_lines": len(lines),
        "by_sport": by_sport,
        "lines": lines,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[pp-lines] {o['n_lines']} PrizePicks lines (free) by sport: {o['by_sport']} -> {OUT}")
    for r in o["lines"][:10]:
        print(f"    {r['sport']:4s} {str(r['player'])[:22]:22s} {str(r['stat_type'])[:22]:22s} {r['line']}")
