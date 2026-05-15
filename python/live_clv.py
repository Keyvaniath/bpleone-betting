"""
EdgeStat -- live in-game CLV tracking.

Polls Bovada for live MLB lines every cron tick and APPENDS each snapshot
to data/live_clv.json so we can:
  1. Watch line movement DURING the game (live moneyline / total drift)
  2. Compute TRUE CLV when a bet is placed mid-game: the user marks an
     entry point and we measure where the line was vs where it closed
     (final snapshot before the game ends).
  3. Compare model's live win-prob (from live_games.py) to book's live
     implied prob -- the live edge.

Pairs with python/live_games.py which polls the gumbo feed for game state +
win-expectancy. live_games tells us "where the model thinks the game is",
live_clv tells us "where the book is pricing it." The gap is the live edge.

Output schema:
  data/live_clv.json = {
    "polled_at": "...",
    "games": {
      "{home}_at_{away}": {
        "matchup": "PHI @ PIT",
        "snapshots": [
          {"t": "2026-05-15T19:05:00", "home_ml": -135, "away_ml": +113,
           "total": 8.0, "total_over": -110, "total_under": -110,
           "state": "pre" | "live" | "final",
           "live_inning": null | "T5", "live_outs": null | 2,
           "live_home_score": null | 3, "live_away_score": null | 2},
          ...
        ],
        "opening": {snapshot from first poll},
        "closing": {last snapshot when state=="final"},
        "clv_home_ml": (open_implied - close_implied) * 100,  # percentage points
        "clv_total":   close_total - open_total,              # total points drift
        "clv_home_ml_pct": ...                                # % move in implied prob
      }
    }
  }

The 10-min cron is plenty fast for line tracking in MLB (slower-moving
than NBA/NFL live markets).
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import bovada


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "live_clv.json")


def _load() -> Dict[str, Any]:
    if not os.path.exists(OUT_PATH):
        return {"polled_at": None, "games": {}}
    try:
        with open(OUT_PATH) as f:
            return json.load(f)
    except Exception:
        return {"polled_at": None, "games": {}}


def _implied_pct(ml: Optional[int]) -> Optional[float]:
    if ml is None:
        return None
    if ml >= 0:
        return 100.0 / (ml + 100)
    return (-ml) / (-ml + 100)


def _state_label(event_status: Optional[str], event_live: bool) -> str:
    """Bovada status field: 'U' = upcoming, 'I' = in-progress, 'F' = final.
    `live` boolean is set on in-progress events."""
    if event_live or (event_status or "").upper() in ("I", "IP", "LIVE", "IN_PROGRESS"):
        return "live"
    if (event_status or "").upper() in ("F", "FINAL", "FINISHED"):
        return "final"
    return "pre"


def _bovada_raw_events() -> List[Dict[str, Any]]:
    """Re-use bovada.fetch_raw, extract events with live/status metadata
    that the existing fetch_game_lines drops."""
    raw = bovada.fetch_raw()
    events: List[Dict[str, Any]] = []
    for grp in raw:
        for ev in grp.get("events") or []:
            events.append(ev)
    return events


def _key(matchup: str) -> str:
    """Stable per-game key. matchup is like 'PHI @ PIT'."""
    return matchup.replace(" ", "_").replace("@", "at").replace("__", "_")


def run() -> Dict[str, Any]:
    state = _load()
    now_iso = dt.datetime.now().isoformat(timespec="seconds")
    state["polled_at"] = now_iso

    events = _bovada_raw_events()
    game_lines = bovada.fetch_game_lines()  # already-parsed snapshot

    for ev in events:
        parsed = bovada.parse_game_lines(ev)
        if not parsed or parsed.get("home_ml") is None:
            continue
        matchup = parsed.get("matchup")
        if not matchup:
            continue
        key = _key(matchup)

        ev_status = ev.get("status")
        ev_live = bool(ev.get("live"))
        state_label = _state_label(ev_status, ev_live)

        # Build live-game state metadata from event notes / boxscore if present.
        # Bovada event.notes carries "Top 5th" etc on live games.
        notes = ev.get("notes") or ""

        snap = {
            "t": now_iso,
            "home_ml": parsed["home_ml"],
            "away_ml": parsed["away_ml"],
            "total": parsed["total"],
            "total_over": parsed["total_over"],
            "total_under": parsed["total_under"],
            "state": state_label,
            "notes": notes,
            "home_ml_implied_pct": round((_implied_pct(parsed["home_ml"]) or 0) * 100, 2),
        }

        g = state["games"].setdefault(key, {
            "matchup": matchup,
            "snapshots": [],
            "opening": None,
            "closing": None,
        })
        # Append only if line meaningfully changed or this is the first poll
        snaps = g["snapshots"]
        if (not snaps) or (snap["home_ml"] != snaps[-1]["home_ml"]
                            or snap["total"] != snaps[-1]["total"]
                            or snap["state"] != snaps[-1]["state"]):
            snaps.append(snap)
        if g["opening"] is None:
            g["opening"] = snap
        if state_label == "final":
            g["closing"] = snap

    # CLV computations for games that have BOTH opening + closing
    for g in state["games"].values():
        o = g.get("opening")
        c = g.get("closing")
        if o and c:
            o_imp = _implied_pct(o["home_ml"]) or 0
            c_imp = _implied_pct(c["home_ml"]) or 0
            g["clv_home_ml_pp"] = round((c_imp - o_imp) * 100, 2)
            g["clv_home_ml_pct"] = round(((c_imp / o_imp) - 1) * 100, 2) if o_imp > 0 else None
            if o.get("total") is not None and c.get("total") is not None:
                g["clv_total"] = round(c["total"] - o["total"], 2)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = run()
    print(f"Polled at {s['polled_at']}")
    games = s.get("games", {})
    live = sum(1 for g in games.values()
               if g.get("snapshots") and g["snapshots"][-1].get("state") == "live")
    final = sum(1 for g in games.values()
                if g.get("snapshots") and g["snapshots"][-1].get("state") == "final")
    print(f"  Tracking {len(games)} games  ({live} live, {final} final)")
    for k, g in list(games.items())[:5]:
        sn = g["snapshots"]
        last = sn[-1] if sn else {}
        print(f"  {g['matchup']:15} snaps={len(sn)} state={last.get('state')} "
              f"home_ml={last.get('home_ml')} total={last.get('total')} "
              f"CLV_pp={g.get('clv_home_ml_pp')}")
