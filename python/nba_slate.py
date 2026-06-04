"""
EdgeStat -- shared NBA slate gate for the prop generators.

Every nba_player_*_props generator reads nba_state.games. Ungated, they fire on
whatever the slate holds -- a stale playoff matchup that already finished, a
seed/placeholder entry with no date, or (the bug that bit NFL) the next season's
schedule that ESPN starts serving months ahead. The result is a flood of picks
that can never settle and just void.

upcoming_games() returns only games that are real, dated, not yet final, and
kicking off within a short horizon -- each tagged with `game_date` so the pick is
dated to its game (clean settlement + one pick per game, instead of a fresh
re-emit every day until tip-off). One gate, used by all generators, so NBA is
correct the moment the season tips off in October.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

HORIZON_DAYS = 3   # one NBA day's slate fits comfortably; excludes far-future dumps


def upcoming_games(state: Dict[str, Any], horizon_days: int = HORIZON_DAYS) -> List[Dict[str, Any]]:
    today = dt.date.today()
    out: List[Dict[str, Any]] = []
    for g in (state.get("games") or state.get("events") or []):
        st = (g.get("status") or g.get("state") or "").lower()
        if "final" in st or (g.get("state") or "").lower() == "post":
            continue
        gd = (g.get("date") or g.get("start") or "")[:10]
        try:
            gdate = dt.date.fromisoformat(gd) if gd else None
        except Exception:
            gdate = None
        if gdate is None or not (today <= gdate <= today + dt.timedelta(days=horizon_days)):
            continue
        gg = dict(g)
        gg["game_date"] = gd
        out.append(gg)
    return out
