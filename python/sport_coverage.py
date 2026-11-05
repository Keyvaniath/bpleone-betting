"""
EdgeStat -- cross-sport coverage matrix.

The honest "is every desk live, producing props/bets, and TRACKING a record?"
view across all sports. For each sport it reports:
  * status    -- LIVE (games/picks today) / IN-SEASON / OFF-SEASON, derived from
                 data (games today + recency of activity), not a hardcoded calendar
  * games_today + projections -- is it producing picks right now
  * props / lines -- does it surface player props and/or game-line / outright bets
  * tracking  -- settled record + ROI, from the unified ledger (by_sport) AND the
                 per-sport pot_history (some desks settle there, e.g. LoL/golf).
                 NONE here = picks are made but nothing settles (no outcome feed).

Output: data/sport_coverage.json
"""
from __future__ import annotations

import os
import re
import json
import glob
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "sport_coverage.json")
NOW = dt.datetime.utcnow()

# code, label, page, ledger_keys, state_file, pot_history_file, prop_probe_globs
SPORTS: List[Tuple[str, str, str, List[str], Optional[str], Optional[str], List[str]]] = [
    # (2026-11-03) MLB-PP left the MLB row: it is the unverified PrizePicks import
    # (graded at the -136 break-even, feed dead since 7/9) and never merges into a headline.
    ("MLB",      "MLB",            "mlb.html",      ["MLB"],           "matchups.json",        "player_pot_history.json", ["mlb_*props*.json", "mlb_*totals*.json"]),
    ("WNBA",     "WNBA",           "wnba.html",     ["WNBA"],          "wnba_state.json",      None,                      ["wnba_*props*.json"]),
    ("GOLF",     "Golf",           "golf.html",     ["GOLF"],          "golf_state.json",      "golf_pot_history.json",   ["golf_*props*.json", "golf_bestbet.json"]),
    ("WORLDCUP", "World Cup",      "worldcup.html", ["WORLDCUP"],      "worldcup_cards.json",  None,                      ["soccer_goalscorer_props.json", "worldcup_cards.json"]),
    # Soccer props are shared across active comps, so they're attributed to World
    # Cup above (the live comp). EPL/MLS/UCL gauge LIVE off their own schedule so
    # an off-season league doesn't read LIVE on borrowed props.
    ("MLS",      "MLS",            "mls.html",      ["MLS"],           "mls_state.json",       None,                      []),
    ("EPL",      "EPL",            "epl.html",      ["EPL"],           "epl_state.json",       None,                      []),
    ("UCL",      "UCL",            "ucl.html",      ["UCL"],           "ucl_state.json",       None,                      []),
    ("NBA",      "NBA",            "nba.html",      ["NBA"],           "nba_state.json",       None,                      ["nba_*props*.json"]),
    ("NHL",      "NHL",            "nhl.html",      ["NHL"],           "nhl_state.json",       None,                      ["nhl_*props*.json"]),
    ("NFL",      "NFL",            "nfl.html",      ["NFL"],           "nfl_state.json",       None,                      ["nfl_*props*.json"]),
    ("KBO",      "KBO",            "kbo.html",      ["KBO"],           "kbo_state.json",       "kbo_pot_history.json",    ["kbo_props.json", "kbo_player_props.json"]),
    ("UFC",      "UFC",            "ufc.html",      ["UFC"],           None,                   None,                      ["ufc_*props*.json"]),
    ("F1",       "F1",             "f1.html",       ["F1"],            None,                   None,                      ["f1_*.json"]),
    ("TENNIS",   "Tennis",         "tennis.html",   ["TENNIS"],        "tennis_state.json",    "tennis_pot_history.json", ["tennis_*props*.json"]),
    ("LOL",      "LoL",            "lol.html",      ["LOL"],           "lol_state.json",       "lol_pot_history.json",    ["lol_props.json", "lol_player_props.json"]),
    ("CS",       "CS",             "cs.html",       ["CS"],            "cs_state.json",        "cs_pot_history.json",     ["cs_props.json", "cs_player_props.json"]),
    ("CWS",      "NCAA Baseball",  "cws.html",      ["CWS", "NCAA-BB"],"cws_state.json",       "cws_pot_history.json",    ["cws_*.json"]),
    # College football (2026-09-03). Registered even though the desk is
    # EXPERIMENTAL and will show 0 settled for a long while -- an unlisted desk
    # is an invisible one, and the whole point of this row is that a dark or
    # non-settling CFB feed shows up here instead of going unnoticed the way
    # historical_ncaaf.json did for a full season.
    ("NCAAF",    "College Football","ncaaf.html",   ["NCAAF", "CFB"],  "ncaaf_state.json",     None,                      ["cfb_model.json"]),
]


def _load(p) -> Any:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _list_len(d: Any) -> int:
    """Largest list found in a dict (games / props / projections / picks)."""
    if isinstance(d, list):
        return len(d)
    if not isinstance(d, dict):
        return 0
    best = 0
    for v in d.values():
        if isinstance(v, list):
            best = max(best, len(v))
    return 0 if best == 0 else best


def _fresh_h(d: Any) -> Optional[float]:
    g = d.get("generated_at") or d.get("updated_at") if isinstance(d, dict) else None
    if not g:
        return None
    try:
        t = dt.datetime.fromisoformat(str(g).replace("Z", "").split("+")[0])
        return (NOW - t).total_seconds() / 3600
    except Exception:
        return None


def _today_et() -> dt.date:
    """(2026-11-03) Today's date in US Eastern time (zoneinfo, else UTC-5)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        return (dt.datetime.utcnow() - dt.timedelta(hours=5)).date()


def _et_date(v: Any) -> Optional[dt.date]:
    """(2026-11-03) ISO timestamp (UTC 'Z' or offset) or bare date -> ET calendar date."""
    if not v:
        return None
    s = str(v).strip()
    try:
        if len(s) == 10:
            return dt.date.fromisoformat(s)
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            return t.astimezone(ZoneInfo("America/New_York")).date()
        except Exception:
            return (t.astimezone(dt.timezone.utc) - dt.timedelta(hours=5)).date()
    except Exception:
        return None


def _games_today(state_file: Optional[str]) -> Tuple[int, Optional[float]]:
    if not state_file:
        return 0, None
    s = _load(os.path.join(DATA_DIR, state_file))
    games = (s.get("games") or s.get("events") or s.get("matches")
             or s.get("cards") or s.get("upcoming_matches") or [])
    games = games if isinstance(games, list) else []
    # (2026-11-03) count only games ON TODAY'S ET DATE (or in progress). State files
    # also carry last week's finals and next week's fixtures (WNBA 11/01 final, CWS
    # 6/22 final, CS 11/09), which made off-season desks read LIVE. A game with no
    # date field at all still counts (no evidence either way).
    today = _today_et()
    n = 0
    for g in games:
        if not isinstance(g, dict):
            n += 1
            continue
        if str(g.get("state") or "").lower() in ("in", "live", "inprogress", "in_progress"):
            n += 1
            continue
        d = _et_date(g.get("date") or g.get("start_time") or g.get("commence_time")
                     or g.get("game_date") or g.get("startTime"))
        if d is None or d == today:
            n += 1
    # active_tournament style (golf): in progress counts as "a game on the board"
    at = s.get("active_tournament") if isinstance(s, dict) else None
    if not n and isinstance(at, dict) and at.get("name"):
        n = 1
    return n, _fresh_h(s)


def _games_upcoming(state_file: Optional[str], days: int = 14) -> int:
    """(2026-11-04) Games in the desk's state dated today..today+days (ET). This is
    the schedule evidence for IN-SEASON -- a props file regenerated in the
    off-season is not (WNBA/World Cup/KBO/CWS read IN-SEASON on one)."""
    if not state_file:
        return 0
    s = _load(os.path.join(DATA_DIR, state_file))
    games = (s.get("games") or s.get("events") or s.get("matches")
             or s.get("cards") or s.get("upcoming_matches") or s.get("schedule") or [])
    games = games if isinstance(games, list) else []
    today = _today_et()
    n = 0
    for g in games:
        if not isinstance(g, dict):
            continue
        d = _et_date(g.get("date") or g.get("start_time") or g.get("commence_time")
                     or g.get("game_date") or g.get("startTime") or g.get("start_date"))
        if d is not None and today <= d <= today + dt.timedelta(days=days):
            n += 1
    for k in ("next_event_date", "next_game_date", "next_race_date", "next_date"):
        d = _et_date(s.get(k)) if isinstance(s, dict) else None
        if d is not None and today <= d <= today + dt.timedelta(days=days):
            n += 1
    return n


def _props_count(globs: List[str]) -> int:
    seen, total = set(), 0
    for g in globs:
        for f in glob.glob(os.path.join(DATA_DIR, g)):
            if f in seen:
                continue
            seen.add(f)
            d = _load(f)
            # (2026-11-03) a props file older than 48h is a leftover, not today's board
            age = _fresh_h(d)
            if age is not None and age > 48:
                continue
            total += _list_len(d)
    return total


# (2026-11-03) Price class of each desk's ledger record. Only MLB game lines and the
# NFL desk game lines carry a sportsbook price (class A/B); everything else -- all
# player props and every other sport -- is graded at the model's own fair odds (C),
# so its ROI is calibration, not a betting ROI. by_sport carries no class split.
BOOK_PRICED_MIX = {"MLB": "mixed: B game lines + C props", "NFL": "mixed: A/B desk game lines + C props"}
LIVE_STATE_MAX_H = 36   # (2026-11-03) a state file older than this can't show "today"


def _ledger_track(keys: List[str], ledger: Dict[str, Any]) -> Dict[str, Any]:
    bs = ledger.get("by_sport") or {}
    settled = wins = losses = pending = 0
    net = 0.0
    last_date = ""
    for k in keys:
        v = bs.get(k) or {}
        settled += int(v.get("settled") or 0)
        wins += int(v.get("wins") or 0)
        losses += int(v.get("losses") or 0)
        pending += int(v.get("pending") or 0)
        net += float(v.get("net_units") or 0)
    decided = wins + losses
    return {"settled": settled, "wins": wins, "losses": losses, "pending": pending,
            "roi_pct": round(net / decided * 100, 1) if decided else None,
            "hit_rate": round(wins / decided, 4) if decided else None}


def _pot_track(pot_file: Optional[str]) -> Dict[str, Any]:
    if not pot_file:
        return {"settled": 0, "pending": 0}
    d = _load(os.path.join(DATA_DIR, pot_file))
    hist = d.get("history") or (d if isinstance(d, list) else [])
    settled = [h for h in hist if isinstance(h, dict) and h.get("settled")]
    pending = [h for h in hist if isinstance(h, dict) and not h.get("settled") and not h.get("voided")]
    return {"settled": len(settled), "pending": len(pending), "record": d.get("record") or d.get("wins")}


def run() -> Dict[str, Any]:
    ledger = _load(os.path.join(DATA_DIR, "ledger_summary.json"))
    rows: List[Dict[str, Any]] = []
    n_live = n_tracking = 0

    for code, label, page, keys, state_file, pot_file, probes in SPORTS:
        n_games, state_fresh = _games_today(state_file)
        n_props = _props_count(probes)
        led = _ledger_track(keys, ledger)
        pot = _pot_track(pot_file)
        settled = max(led["settled"], pot["settled"])
        pending = max(led["pending"], (pot.get("pending") or 0))
        tracking = settled > 0
        # status (2026-11-03): LIVE only when the desk's state shows games TODAY and
        # that state is fresh -- a leftover props file or an old settled record no
        # longer makes a dormant desk read LIVE. IN-SEASON = picks pending or fresh
        # props on the board; else OFF-SEASON.
        fresh = state_fresh is None or state_fresh <= LIVE_STATE_MAX_H
        if n_games > 0 and fresh:
            status = "LIVE"
        elif pending > 0 or (_games_upcoming(state_file) > 0 if state_file
                             else (n_props > 0 and fresh)):   # (2026-11-04) schedule, not a props refresh
            status = "IN-SEASON"
        else:
            status = "OFF-SEASON"
        # tracking note: settlement WIRED but awaiting game completion vs no feed
        track_note = None
        if not tracking and (pot.get("pending") or 0) > 0:
            track_note = f"settlement wired -- {pot['pending']} pending, settles on game completion"
        elif not tracking and (n_props > 0 or n_games > 0 or pending > 0):
            track_note = "picks produced, none settled yet (awaiting an outcome feed)"

        if tracking:
            track_status = "tracking"
        elif status == "OFF-SEASON":
            track_status = "off-season"
        elif (pot.get("pending") or 0) > 0:
            track_status = "pending"
        elif n_props > 0 or n_games > 0 or pending > 0:
            track_status = "no-feed"
        else:
            track_status = "none"

        if status == "LIVE":
            n_live += 1
        if tracking:
            n_tracking += 1

        rows.append({
            "sport": label, "code": code, "page": page,
            "status": status,
            "games_today": n_games,
            "projections": n_props,
            "has_props": n_props > 0,
            "tracking": tracking,
            "settled": settled,
            "pending": pending,
            "record": f"{led['wins']}-{led['losses']}" if led["wins"] + led["losses"] else None,
            "roi_pct": led["roi_pct"],
            "hit_rate": led["hit_rate"],
            # (2026-11-03) price basis of the ledger record; class C -> calibration only
            "price_basis": BOOK_PRICED_MIX.get(code, "C: model fair odds"),
            "roi_is_betting_roi": False,
            "track_status": track_status,
            "track_note": track_note,
            "state_fresh_h": round(state_fresh, 1) if state_fresh is not None else None,
        })

    order = {"LIVE": 0, "IN-SEASON": 1, "OFF-SEASON": 2}
    rows.sort(key=lambda r: (order.get(r["status"], 3), -(r["settled"] or 0), -(r["projections"] or 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "totals": {
            "n_sports": len(rows),
            "n_live": n_live,
            "n_tracking": n_tracking,
            # kept for back-compat with the old page
            "n_games_all_sports": sum(r["games_today"] for r in rows),
            "n_strong_edges_all_sports": sum(r["projections"] for r in rows),
        },
        "note": ("LIVE = games on today's (fresh) board; IN-SEASON = picks pending or a game "
                 "scheduled in the next 14 days (desks with no schedule feed: fresh props); "
                 "OFF-SEASON = dormant. TRACKING = settles a real "
                 "record (ledger or pot_history). Per-sport ROI mixes price classes and is "
                 "mostly at the model's own fair odds (class C) -- calibration, not a "
                 "betting ROI. MLB-PP (unverified PrizePicks) is not in any row."),   # (2026-11-03)
        "sports": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    t = o["totals"]
    print(f"[sport-coverage] {t['n_sports']} sports · {t['n_live']} live · {t['n_tracking']} tracking")
    for s in o["sports"]:
        rec = f" {s['record']} {s['roi_pct']:+.0f}%" if s["record"] and s["roi_pct"] is not None else ""
        flag = "" if s["tracking"] else ("  <-- " + s["track_note"] if s["track_note"] else "")
        print(f"  {s['sport']:14s} {s['status']:10s} games={s['games_today']:2d} props={s['projections']:4d} "
              f"track={'Y' if s['tracking'] else 'N'}{rec}{flag}")
