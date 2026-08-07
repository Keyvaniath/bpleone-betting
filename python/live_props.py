"""
EdgeStat -- live in-game prop tracker.

For every prop on tonight's slate (DraftKings + PrizePicks combined),
fetches the current live box score from MLB Stats API and reports each
player's CURRENT stat line vs their prop line. Tells Brandon at a glance
which OVERs are already cashing, which are dead, and which are mid-flight.

For each prop:
  - actual_so_far: current stat value (e.g. 1 hit through 4 ABs)
  - status: "won" / "lost" / "in_progress" / "scheduled" / "no_game"
  - delta_to_line: how many more outcome units needed to cross the line
  - implied_remaining_pa: rough PA budget remaining for the player
  - game_state: inning + score + bases (for context)

Hits the MLB Stats API in-game feed once per gamePk (cached).
Output: data/live_props.json keyed by `{player_id}_{market}_{line}`.

Pipeline: this runs from the live-games workflow (every 5-10 min), not
the daily pipeline. It's safe to run repeatedly -- idempotent.
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "live_props.json")

MLB = "https://statsapi.mlb.com/api/v1"
HTTP_TIMEOUT = 10


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _http_json(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _schedule_today() -> List[Dict[str, Any]]:
    """All MLB games for today with gamePk + status."""
    today = dt.date.today().isoformat()
    data = _http_json(f"{MLB}/schedule?sportId=1&date={today}") or {}
    games = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            games.append(g)
    return games


def _boxscore(gp: int) -> Dict[str, Any]:
    return _http_json(f"{MLB}/game/{gp}/boxscore") or {}


def _linescore(gp: int) -> Dict[str, Any]:
    return _http_json(f"{MLB}/game/{gp}/linescore") or {}


def _player_stat(bs: Dict[str, Any], pid: int, kind: str) -> Optional[Dict[str, Any]]:
    """Find a player's CURRENT-game stat block in either team's box."""
    for side in ("home", "away"):
        team = bs.get("teams", {}).get(side, {})
        pkey = f"ID{pid}"
        p = (team.get("players") or {}).get(pkey)
        if not p:
            continue
        stats = (p.get("stats") or {}).get(kind) or {}
        return stats
    return None


def _actual_for_market(bs: Dict[str, Any], pid: int, market: str) -> Optional[float]:
    if market == "pitcher_strikeouts":
        s = _player_stat(bs, pid, "pitching")
        if not s:
            return None
        return float(s.get("strikeOuts") or 0)
    if market in ("batter_hits", "batter_total_bases", "batter_home_runs",
                  "batter_runs_scored", "batter_rbis", "batter_doubles",
                  "batter_singles"):
        s = _player_stat(bs, pid, "batting")
        if not s:
            return None
        hits = int(s.get("hits") or 0)
        doubles = int(s.get("doubles") or 0)
        triples = int(s.get("triples") or 0)
        hr = int(s.get("homeRuns") or 0)
        singles = hits - doubles - triples - hr
        tb = singles + 2 * doubles + 3 * triples + 4 * hr
        if market == "batter_hits":         return float(hits)
        if market == "batter_total_bases":  return float(tb)
        if market == "batter_home_runs":    return float(hr)
        if market == "batter_runs_scored":  return float(s.get("runs") or 0)
        if market == "batter_rbis":         return float(s.get("rbi") or 0)
        if market == "batter_doubles":      return float(doubles)
        if market == "batter_singles":      return float(singles)
    return None


def _game_state_str(ls: Dict[str, Any]) -> str:
    """Compact 'B3 2-1 LAA·SF runners 1B 2B' string from linescore."""
    if not ls:
        return ""
    cur = ls.get("currentInning")
    half = ls.get("inningHalf", "")
    away_r = (ls.get("teams") or {}).get("away", {}).get("runs", 0)
    home_r = (ls.get("teams") or {}).get("home", {}).get("runs", 0)
    outs = ls.get("outs")
    if cur is None:
        return ""
    h = "T" if (half or "").upper() == "TOP" else "B"
    out_s = f" · {outs} out" if outs is not None else ""
    return f"{h}{cur} · {away_r}-{home_r}{out_s}"


def _build_player_to_gamepk() -> Dict[int, int]:
    """Map every player on tonight's slate to their gamePk via matchups.json."""
    m = _load(MATCHUPS_PATH)
    out: Dict[int, int] = {}
    for g in m.get("games") or []:
        gp = g.get("gamePk")
        if not gp:
            continue
        for side in ("home", "away"):
            for b in (g.get("lineups") or {}).get(side) or []:
                pid = b.get("id")
                if pid:
                    out[pid] = gp
        for p_side in ("home_pitcher", "away_pitcher"):
            p = g.get(p_side) or {}
            if p.get("id"):
                out[p["id"]] = gp
    return out


def run() -> Dict[str, Any]:
    sched = _schedule_today()
    state_by_pk: Dict[int, str] = {}
    final_pks: set = set()
    in_prog_pks: set = set()
    not_yet_pks: set = set()
    for g in sched:
        pk = g.get("gamePk")
        if not pk:
            continue
        status = (g.get("status") or {}).get("detailedState", "")
        state_by_pk[pk] = status
        if status == "Final":
            final_pks.add(pk)
        elif status in ("Scheduled", "Pre-Game", "Warmup"):
            not_yet_pks.add(pk)
        else:
            in_prog_pks.add(pk)

    pid_to_pk = _build_player_to_gamepk()

    # Cache box + line scores once per gamePk
    box_cache: Dict[int, Dict[str, Any]] = {}
    line_cache: Dict[int, Dict[str, Any]] = {}
    def _bs(pk):
        if pk not in box_cache:
            box_cache[pk] = _boxscore(pk)
        return box_cache[pk]
    def _ls(pk):
        if pk not in line_cache:
            line_cache[pk] = _linescore(pk)
        return line_cache[pk]

    # Combine props
    all_props: List[Dict[str, Any]] = []
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        all_props.append({**p, "src": "DK"})
    for p in (_load(PICKEM_PATH).get("props") or []):
        all_props.append({**p, "line": p.get("pp_line"), "src": "PP"})

    by_key: Dict[str, Dict[str, Any]] = {}
    for p in all_props:
        pid = p.get("player_id")
        market = p.get("market")
        line = p.get("line")
        if pid is None or market is None or line is None:
            continue
        pk = pid_to_pk.get(pid)
        if pk is None:
            status = "no_game"
            actual = None
            gs = ""
        elif pk in not_yet_pks:
            status = "scheduled"
            actual = None
            gs = state_by_pk.get(pk, "")
        else:
            bs = _bs(pk)
            ls = _ls(pk)
            actual = _actual_for_market(bs, pid, market)
            gs = _game_state_str(ls)
            if pk in final_pks:
                if actual is None:
                    status = "scheduled"
                else:
                    status = "won" if actual > line else ("lost" if actual <= line else "lost")
            else:
                if actual is None:
                    status = "in_progress"
                else:
                    # Already crossed -> won (only for OVER). For UNDER, only locks at game end.
                    over_won = actual > line
                    play = (p.get("play") or "").upper()
                    if play == "OVER" and over_won:
                        status = "won_so_far"
                    elif play == "OVER":
                        status = "in_progress"
                    elif play == "UNDER":
                        status = "lost_so_far" if over_won else "in_progress"
                    else:
                        status = "in_progress"
        key = f"{pid}_{market}_{line}"
        by_key[key] = {
            "player_id": pid,
            "player": p.get("player"),
            "market": market,
            "line": line,
            "play": p.get("play"),
            "src": p.get("src"),
            "actual_so_far": actual,
            "delta_to_line": (None if actual is None else round(line - actual + 0.5, 1)),
            "status": status,
            "game_state": gs,
            "game_pk": pk,
        }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_props": len(by_key),
        "n_in_progress": sum(1 for v in by_key.values() if v["status"] == "in_progress"),
        "n_won_so_far": sum(1 for v in by_key.values() if v["status"] == "won_so_far"),
        "n_lost_so_far": sum(1 for v in by_key.values() if v["status"] == "lost_so_far"),
        "n_won": sum(1 for v in by_key.values() if v["status"] == "won"),
        "n_lost": sum(1 for v in by_key.values() if v["status"] == "lost"),
        "by_key": by_key,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_props']} props tracked")
    print(f"  in-progress: {p['n_in_progress']}")
    print(f"  on track to WIN: {p['n_won_so_far']}")
    print(f"  on track to LOSE: {p['n_lost_so_far']}")
    print(f"  final WON: {p['n_won']}")
    print(f"  final LOST: {p['n_lost']}")
