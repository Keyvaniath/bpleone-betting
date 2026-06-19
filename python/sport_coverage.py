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
    ("MLB",      "MLB",            "mlb.html",      ["MLB", "MLB-PP"], "matchups.json",        "player_pot_history.json", ["mlb_*props*.json", "mlb_*totals*.json"]),
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
    ("TENNIS",   "Tennis",         "tennis.html",   ["TENNIS"],        "tennis_state.json",    None,                      ["tennis_*props*.json"]),
    ("LOL",      "LoL",            "lol.html",      ["LOL"],           "lol_state.json",       "lol_pot_history.json",    ["lol_props.json", "lol_player_props.json"]),
    ("CS",       "CS",             "cs.html",       ["CS"],            "cs_state.json",        "cs_pot_history.json",     ["cs_props.json", "cs_player_props.json"]),
    ("CWS",      "NCAA Baseball",  "cws.html",      ["CWS", "NCAA-BB"],"cws_state.json",       "cws_pot_history.json",    ["cws_*.json"]),
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


def _games_today(state_file: Optional[str]) -> Tuple[int, Optional[float]]:
    if not state_file:
        return 0, None
    s = _load(os.path.join(DATA_DIR, state_file))
    games = (s.get("games") or s.get("events") or s.get("matches")
             or s.get("cards") or s.get("upcoming_matches") or [])
    n = len(games) if isinstance(games, list) else 0
    # active_tournament style (golf): in progress counts as "a game on the board"
    at = s.get("active_tournament") if isinstance(s, dict) else None
    if not n and isinstance(at, dict) and at.get("name"):
        n = 1
    return n, _fresh_h(s)


def _props_count(globs: List[str]) -> int:
    seen, total = set(), 0
    for g in globs:
        for f in glob.glob(os.path.join(DATA_DIR, g)):
            if f in seen:
                continue
            seen.add(f)
            total += _list_len(_load(f))
    return total


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
            "roi_pct": round(net / decided * 100, 1) if decided else None}


def _pot_track(pot_file: Optional[str]) -> Dict[str, Any]:
    if not pot_file:
        return {"settled": 0, "pending": 0}
    d = _load(os.path.join(DATA_DIR, pot_file))
    hist = d.get("history") or (d if isinstance(d, list) else [])
    settled = [h for h in hist if isinstance(h, dict) and h.get("settled")]
    pending = [h for h in hist if isinstance(h, dict) and not h.get("settled")]
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
        pending = max(led["pending"], pot.get("pending", 0))
        tracking = settled > 0
        # status: LIVE if games/props today; else IN-SEASON if recently tracking/
        # pending; else OFF-SEASON.
        if n_games > 0 or n_props > 0:
            status = "LIVE"
        elif pending > 0 or settled > 0:
            status = "IN-SEASON"
        else:
            status = "OFF-SEASON"
        # tracking note: settlement WIRED but awaiting game completion vs no feed
        track_note = None
        if not tracking and pot.get("pending", 0) > 0:
            track_note = f"settlement wired -- {pot['pending']} pending, settles on game completion"
        elif not tracking and (n_props > 0 or n_games > 0 or pending > 0):
            track_note = "picks produced, none settled yet (awaiting an outcome feed)"

        if tracking:
            track_status = "tracking"
        elif status == "OFF-SEASON":
            track_status = "off-season"
        elif pot.get("pending", 0) > 0:
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
        "note": ("LIVE = producing picks/props right now; IN-SEASON = active but no slate "
                 "today; OFF-SEASON = dormant. TRACKING = settles a real record (ledger or "
                 "pot_history). A LIVE sport that isn't tracking is making picks with no "
                 "outcome feed to grade them."),
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
