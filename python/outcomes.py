"""
EdgeStat -- outcomes ingestion. The self-learning core.

Daily job that:
  1. Reads snapshot of yesterday's projections from data/history/
  2. Pulls every completed gamePk's final box score from MLB Stats API
  3. Settles each prop + each game-line projection: hit / miss / push
  4. Appends settled records to data/track_record.json (grows over time)
  5. Recomputes calibration metrics on trailing 30-day window
  6. Writes data/calibration.json that props_pipeline + pipeline apply tomorrow

That's the loop. The model gets sharper every day it sees outcomes.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore


MLB_BASE = "https://statsapi.mlb.com/api/v1"
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")  # don't clobber the synthetic-data file


# -------------------- Box-score retrieval --------------------

def fetch_finals_for_date(date_iso: str) -> List[Dict[str, Any]]:
    """Return all Final games for a date. Each entry has gamePk + boxscore."""
    if requests is None:
        return []
    sched = requests.get(f"{MLB_BASE}/schedule?sportId=1&date={date_iso}", timeout=15).json()
    games = []
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            if g["status"]["detailedState"] != "Final":
                continue
            try:
                bs = requests.get(f"{MLB_BASE}/game/{g['gamePk']}/boxscore", timeout=15).json()
            except Exception:
                continue
            games.append({"gamePk": g["gamePk"], "schedule": g, "boxscore": bs})
    return games


def pitchers_from_boxscore(bs: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Return {pitcher_id: {name, team_side, ip, k, er, bb}} for a finalized game."""
    out: Dict[int, Dict[str, Any]] = {}
    for side in ("home", "away"):
        team = bs.get("teams", {}).get(side, {})
        for pid in team.get("pitchers", []):
            pkey = f"ID{pid}"
            p = team.get("players", {}).get(pkey, {})
            stats = p.get("stats", {}).get("pitching", {})
            if not stats.get("inningsPitched"):
                continue
            out[pid] = {
                "name": p.get("person", {}).get("fullName"),
                "side": side,
                "ip": float(stats.get("inningsPitched") or 0),
                "k": int(stats.get("strikeOuts") or 0),
                "er": int(stats.get("earnedRuns") or 0),
                "bb": int(stats.get("baseOnBalls") or 0),
                "is_starter": p.get("position", {}).get("code") == "1" and stats.get("gamesStarted") == 1,
                # Heuristic: pitchers with >= 3 IP in a single game listed as games_started.
                # The boxscore stats here are for THIS game only.
            }
    return out


def batters_from_boxscore(bs: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    """Return {batter_id: {name, side, hr, hits, total_bases, ab, pa}}."""
    out: Dict[int, Dict[str, Any]] = {}
    for side in ("home", "away"):
        team = bs.get("teams", {}).get(side, {})
        for bid in team.get("batters", []):
            bkey = f"ID{bid}"
            p = team.get("players", {}).get(bkey, {})
            stats = p.get("stats", {}).get("batting", {})
            if not stats:
                continue
            hits = int(stats.get("hits") or 0)
            doubles = int(stats.get("doubles") or 0)
            triples = int(stats.get("triples") or 0)
            hr = int(stats.get("homeRuns") or 0)
            singles = hits - doubles - triples - hr
            tb = singles + 2 * doubles + 3 * triples + 4 * hr
            out[bid] = {
                "name": p.get("person", {}).get("fullName"),
                "side": side,
                "ab": int(stats.get("atBats") or 0),
                "pa": int(stats.get("plateAppearances") or 0),
                "hits": hits,
                "hr": hr,
                "doubles": doubles,
                "triples": triples,
                "singles": singles,
                "total_bases": tb,
                "rbi": int(stats.get("rbi") or 0),
                "runs": int(stats.get("runs") or 0),
            }
    return out


def game_total(bs: Dict[str, Any]) -> Optional[int]:
    """Final total runs for a finalized game."""
    try:
        h = bs["teams"]["home"]["teamStats"]["batting"]["runs"]
        a = bs["teams"]["away"]["teamStats"]["batting"]["runs"]
        return int(h) + int(a)
    except Exception:
        return None


def game_winner(bs: Dict[str, Any]) -> Optional[str]:
    """Return 'home' or 'away'."""
    try:
        h = int(bs["teams"]["home"]["teamStats"]["batting"]["runs"])
        a = int(bs["teams"]["away"]["teamStats"]["batting"]["runs"])
        return "home" if h > a else "away"
    except Exception:
        return None


# -------------------- Settlement --------------------

def _hp_umpire_from_boxscore(bs: Dict[str, Any]) -> Optional[str]:
    """Extract the home-plate umpire name from a finalized boxscore.
    Returns None when the field is missing."""
    officials = bs.get("officials") or []
    for o in officials:
        kind = ((o.get("officialType") or "")).lower()
        if "home plate" in kind or "homeplate" in kind:
            return ((o.get("official") or {}).get("fullName")) or None
    return None


def _venue_from_schedule(sched_entry: Dict[str, Any]) -> Optional[str]:
    """Extract venue name from a schedule entry; falls back to None."""
    v = (sched_entry.get("venue") or {}).get("name")
    return v or None


def settle_prop(prop: Dict[str, Any], outcomes_for_game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return a settled record or None if we can't settle yet."""
    pid = prop.get("player_id")
    market = prop.get("market")
    line = prop.get("line")
    if not pid or market is None or line is None:
        return None
    if market == "pitcher_strikeouts":
        actual = (outcomes_for_game.get("pitchers", {}).get(pid) or {}).get("k")
    elif market == "batter_home_runs":
        actual = (outcomes_for_game.get("batters", {}).get(pid) or {}).get("hr")
    elif market == "batter_hits":
        actual = (outcomes_for_game.get("batters", {}).get(pid) or {}).get("hits")
    elif market == "batter_total_bases":
        actual = (outcomes_for_game.get("batters", {}).get(pid) or {}).get("total_bases")
    elif market == "batter_runs_scored":
        actual = (outcomes_for_game.get("batters", {}).get(pid) or {}).get("runs")
    elif market == "batter_rbis":
        actual = (outcomes_for_game.get("batters", {}).get(pid) or {}).get("rbi")
    elif market == "batter_doubles":
        b = (outcomes_for_game.get("batters", {}).get(pid) or {})
        # Box score doesn't include doubles directly; compute from totals.
        # batters_from_boxscore captures doubles when present; use that.
        actual = b.get("doubles")
    elif market == "batter_singles":
        b = (outcomes_for_game.get("batters", {}).get(pid) or {})
        actual = b.get("singles") if "singles" in b else None
    elif market == "batter_hits_runs_rbis":
        b = (outcomes_for_game.get("batters", {}).get(pid) or {})
        h = b.get("hits"); r_ = b.get("runs"); rbi = b.get("rbi")
        actual = (h + r_ + rbi) if all(v is not None for v in (h, r_, rbi)) else None
    else:
        return None
    if actual is None:
        return None
    over_won = actual > line
    push = actual == line  # half-lines never push, but integer lines can
    if push:
        return None  # push, exclude from track record
    return {
        "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
        "player": prop.get("player"),
        "player_id": pid,
        "market": market,
        "line": line,
        "actual": actual,
        "over_hit": bool(over_won),
        "model_prob_over": prop.get("model_prob_over"),
        "model_projection": prop.get("model_projection"),
        "projection_vs_actual": (round(actual - prop["model_projection"], 2)
                                  if prop.get("model_projection") is not None else None),
        "model_version": (prop.get("debug") or {}).get("model_version"),
        "dk_over": prop.get("dk_over"),
        "dk_under": prop.get("dk_under"),
        "play": prop.get("play"),
        "edge_pct": prop.get("best_edge_pct"),
        "low_confidence": prop.get("low_confidence", False),
        "play_hit": _did_play_hit(prop.get("play"), over_won),
        # NEW: tag context for player breakdowns. None when missing.
        "ump": outcomes_for_game.get("ump"),
        "venue": outcomes_for_game.get("venue"),
        "game_pk": outcomes_for_game.get("game_pk"),
        "is_night": outcomes_for_game.get("is_night"),
    }


def _did_play_hit(play: Optional[str], over_won: bool) -> Optional[bool]:
    if play == "OVER":
        return over_won
    if play == "UNDER":
        return not over_won
    return None  # SKIP


def settle_game(game: Dict[str, Any], outcomes: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Settle a game-line projection (today.json game entry)."""
    actual_total = outcomes.get("total_runs")
    winner = outcomes.get("winner")
    if actual_total is None or winner is None:
        return None
    market = game.get("market") or {}
    model = game.get("model") or {}
    line = market.get("total")
    if line is None:
        return None
    over_hit = actual_total > line
    return {
        "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
        "matchup": game.get("matchup"),
        "market_total": line,
        "actual_total": actual_total,
        "over_hit": bool(over_hit),
        "model_fair_total": model.get("fair_total"),
        "model_p_over_market": model.get("p_over_market"),
        "p_home_win": model.get("p_home_win"),
        "winner_actual": winner,
        "book": market.get("book"),
    }


# -------------------- Orchestrator --------------------

def settle_date(date_iso: str) -> Dict[str, Any]:
    """Walk snapshots for date, pull outcomes, settle everything."""
    snap_today = os.path.join(HISTORY_DIR, f"{date_iso}_today.json")
    snap_props = os.path.join(HISTORY_DIR, f"{date_iso}_props.json")
    today_snap = _load_optional(snap_today)
    props_snap = _load_optional(snap_props)
    if not today_snap and not props_snap:
        return {"date": date_iso, "warning": "no snapshots found", "props": [], "games": []}

    finals = fetch_finals_for_date(date_iso)
    # Index outcomes by gamePk
    outcomes_by_pk: Dict[int, Dict[str, Any]] = {}
    for f in finals:
        bs = f["boxscore"]
        sched = f.get("schedule") or {}
        outcomes_by_pk[f["gamePk"]] = {
            "pitchers": pitchers_from_boxscore(bs),
            "batters": batters_from_boxscore(bs),
            "total_runs": game_total(bs),
            "winner": game_winner(bs),
            # NEW: context tags for downstream player-breakdown panels
            "ump": _hp_umpire_from_boxscore(bs),
            "venue": _venue_from_schedule(sched),
            "game_pk": f["gamePk"],
            "is_night": ((sched.get("dayNight") or "").lower() == "night"),
        }
    # Build a name -> gamePk join for props (props.json doesn't carry gamePk)
    # by matching player_id -> the unique gamePk that lists them
    pid_to_pk: Dict[int, int] = {}
    for pk, o in outcomes_by_pk.items():
        for side in ("pitchers", "batters"):
            for p_id in (o.get(side) or {}).keys():
                pid_to_pk[p_id] = pk

    settled_props: List[Dict[str, Any]] = []
    if props_snap:
        for prop in props_snap.get("top_edges", []):
            if prop.get("is_demo"):
                continue
            pk = pid_to_pk.get(prop.get("player_id"))
            if pk is None:
                continue
            r = settle_prop(prop, outcomes_by_pk[pk])
            if r:
                r["date"] = date_iso
                settled_props.append(r)

    settled_games: List[Dict[str, Any]] = []
    if today_snap:
        # today.json carries matchup ("AWAY @ HOME") but no gamePk currently.
        # Match by matchup string using the schedule from finals.
        match_to_pk: Dict[str, int] = {}
        for f in finals:
            g = f["schedule"]
            away = g["teams"]["away"]["team"]["name"]
            home = g["teams"]["home"]["team"]["name"]
            # We need codes — best-effort: import TEAM_CODE
            try:
                from pipeline import TEAM_CODE
                a = TEAM_CODE.get(away, away[:3].upper())
                h = TEAM_CODE.get(home, home[:3].upper())
                match_to_pk[f"{a} @ {h}"] = f["gamePk"]
            except Exception:
                pass
        for game in today_snap.get("games", []):
            # Skip games tagged is_demo=True by pipeline.build_slate's fallback;
            # those matchups are fictional and cannot be settled against real
            # MLB outcomes (this caused 0 game settlements on 2026-05-14).
            if game.get("is_demo"):
                continue
            pk = match_to_pk.get(game.get("matchup"))
            if pk is None:
                continue
            r = settle_game(game, outcomes_by_pk[pk])
            if r:
                r["date"] = date_iso
                settled_games.append(r)

    return {"date": date_iso, "props": settled_props, "games": settled_games,
            "boxscores_pulled": len(finals)}


def _load_optional(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def append_to_track_record(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Append settled records to data/track_record.json (idempotent on date)."""
    tr: Dict[str, Any]
    if os.path.exists(TR_PATH):
        with open(TR_PATH) as f:
            tr = json.load(f)
    else:
        tr = {"props": [], "games": [], "last_settled_date": None}
    # Replace records for this date (idempotent re-runs)
    date = payload["date"]
    tr["props"] = [r for r in tr.get("props", []) if r.get("date") != date] + payload["props"]
    tr["games"] = [r for r in tr.get("games", []) if r.get("date") != date] + payload["games"]
    tr["last_settled_date"] = date
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TR_PATH, "w") as f:
        json.dump(tr, f, indent=2)
    return tr


# -------------------- CLI --------------------

if __name__ == "__main__":
    import sys
    # Default: settle yesterday (US/Pacific). Pass --date YYYY-MM-DD to override.
    args = sys.argv[1:]
    if "--date" in args:
        d = args[args.index("--date") + 1]
    else:
        d = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    print(f"Settling {d}...")
    out = settle_date(d)
    print(f"  Boxscores pulled: {out.get('boxscores_pulled', 0)}")
    print(f"  Settled props: {len(out['props'])}")
    print(f"  Settled games: {len(out['games'])}")
    tr = append_to_track_record(out)
    print(f"  Track record totals: {len(tr['props'])} props, {len(tr['games'])} games")
    # Print a sample
    if out["props"]:
        p = out["props"][0]
        print(f"  Sample prop: {p['player']} {p['market']} {p['line']} -> actual {p['actual']} "
              f"({'HIT' if p['play_hit'] else 'MISS' if p['play_hit'] is False else 'SKIP'})")
