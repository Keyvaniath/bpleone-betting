"""
EdgeStat -- per-player gamelog cache.

For every player who has open props today, pull the last 14 games from
MLB Stats API and cache the per-game stats. The /player.html page reads
this and renders a sparkline of the player's recent form.

Output: data/player_gamelogs.json
  {
    "generated_at": "...",
    "by_player_id": {
      "660271": {  // Ohtani
        "name": "Shohei Ohtani",
        "kind": "batter",      // "batter" or "pitcher"
        "games": [
          {"date": "2026-05-15", "vs": "LAA", "hits": 1, "tb": 1, "hr": 0, "k": 0, "ab": 4, "rbi": 1, "runs": 0},
          ...
        ]
      }
    }
  }

Cached separately from track_record because gamelogs are READ-ONLY.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Set

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
OUT_PATH = os.path.join(DATA_DIR, "player_gamelogs.json")

GAMELOG_DEPTH = 14
MAX_PLAYERS = 350   # quota guard -- ~350 distinct players seen today


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _player_ids_today() -> Dict[int, Dict[str, str]]:
    """Return {player_id: {name, kind}} for every player with an open prop today."""
    out: Dict[int, Dict[str, str]] = {}
    for src in (_load(PROPS_PATH).get("top_edges", []),
                 _load(PICKEM_PATH).get("props", [])):
        for p in src:
            pid = p.get("player_id")
            if not pid:
                continue
            kind = "pitcher" if (p.get("market") or "").startswith("pitcher_") else "batter"
            out[int(pid)] = {"name": p.get("player"), "kind": kind}
    return out


LEDGER_PATH = os.path.join(DATA_DIR, "all_picks_ledger.json")


def _dfs_lineup_players() -> List[Dict[str, str]]:
    """{name, kind} for every player in the published MLB DFS lineup + any
    UNSCORED receipt slate. THE SECOND SETTLEMENT-UNIVERSE HOLE (2026-09-02):
    DFS lineup players never enter the betting ledger (by design), so when the
    props boards went quota-dark the gamelog fetch universe shrank to ~nothing
    and the receipts grader scored 7-9 of 10 slots per slate as 'no box row ->
    0' -- 11 slates published avg 17 actual DK pts vs 116 projected, a -99
    'bias' that was a DATA GAP, not a projection miss. The grader's universe
    must include everyone the receipts will grade."""
    out: List[Dict[str, str]] = []
    seen: Set[str] = set()
    def _take(slots):
        for s in slots or []:
            nm = str(s.get("name") or "").strip()
            if not nm or nm.lower() in seen:
                continue
            seen.add(nm.lower())
            kind = "pitcher" if str(s.get("slot", "")).startswith("P") else "batter"
            # slots carry mlb_id since 2026-09-02 -- fetch by id when present
            # (name resolution once returned the WRONG Max Muncy).
            out.append({"name": nm, "kind": kind, "id": s.get("mlb_id")})
    dfs = _load(os.path.join(DATA_DIR, "mlb_dfs.json"))
    _take(((dfs.get("lineups") or {}).get("optimal") or {}).get("slots"))
    rec = _load(os.path.join(DATA_DIR, "mlb_dfs_receipts.json"))
    for entry in (rec.get("slates") or {}).values():
        if not entry.get("scored"):
            _take((entry.get("optimal") or {}).get("slots"))
    return out


def _pending_ledger_players() -> List[Dict[str, str]]:
    """{name, kind} for every player on a PENDING MLB ledger pick.

    THE SETTLEMENT UNIVERSE (2026-08-10): 'players with open props today' is the
    props boards' universe, NOT the ledger's -- the model prop feeds enter picks
    for players the boards never list, and when the boards go quiet (dead
    PrizePicks feed, exhausted odds quota) those players' gamelogs were never
    fetched, so their pending picks could never grade and aged into
    'unsettleable' voids with the box scores sitting one API call away. The
    grader (all_picks_tracker._grade_batter_prop) reads THIS file, so the fetch
    set must cover the ledger's pendings."""
    led = _load(LEDGER_PATH)
    seen: Set[str] = set()
    out: List[Dict[str, str]] = []
    for p in led.get("picks") or []:
        if p.get("settled") or p.get("voided"):
            continue
        if str(p.get("sport") or "").upper() not in ("MLB", "MLB-PP"):
            continue
        nm = str(p.get("player_or_matchup") or "").strip()
        if not nm or "@" in nm or nm.lower() in seen:
            continue
        seen.add(nm.lower())
        kind = "pitcher" if "pitcher" in str(p.get("market") or "").lower() else "batter"
        out.append({"name": nm, "kind": kind})
    return out


# Lazily-populated team_id -> home_park_name map. Lets us tag venue per game
# from the batter gamelog without N extra schedule-lookups per game.
_TEAM_VENUES: Dict[int, str] = {}


def _ensure_team_venues() -> None:
    """One-shot fetch of team_id -> home_park_name. Free, single API call."""
    global _TEAM_VENUES
    if _TEAM_VENUES:
        return
    import requests
    try:
        r = requests.get("https://statsapi.mlb.com/api/v1/teams",
                         params={"sportId": 1}, timeout=10).json()
        for t in r.get("teams") or []:
            tid = t.get("id")
            v = (t.get("venue") or {}).get("name")
            if tid and v:
                _TEAM_VENUES[tid] = v
    except Exception:
        pass


def _batter_gamelog(pid: int, n: int = GAMELOG_DEPTH) -> List[Dict[str, Any]]:
    """Pull last N games batting gamelog via MLB Stats API. Cached in stats_repo.
    Enriched with venue + is_home + is_night so downstream park / day-night
    splits can be derived without extra API calls."""
    import requests
    _ensure_team_venues()
    try:
        r = requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{pid}/stats",
            params={"stats": "gameLog", "group": "hitting", "season": dt.date.today().year},
            timeout=10,
        ).json()
        splits = ((r.get("stats") or [{}])[0].get("splits") or [])
        out = []
        for s in splits[-n:][::-1]:    # most recent first
            st = s.get("stat") or {}
            opp = (s.get("opponent") or {}).get("abbreviation") or "?"
            opp_id = (s.get("opponent") or {}).get("id")
            team_id = (s.get("team") or {}).get("id")
            d = s.get("date") or ""
            is_home = bool(s.get("isHome"))
            day_night = ((s.get("game") or {}).get("dayNight") or "").lower()
            # Venue = home team's park
            venue_team_id = team_id if is_home else opp_id
            venue = _TEAM_VENUES.get(venue_team_id) if venue_team_id else None
            hits = int(st.get("hits") or 0)
            doubles = int(st.get("doubles") or 0)
            triples = int(st.get("triples") or 0)
            hr = int(st.get("homeRuns") or 0)
            singles = hits - doubles - triples - hr
            tb = singles + 2 * doubles + 3 * triples + 4 * hr
            out.append({
                "date": d,
                "vs": opp,
                "is_home": is_home,
                "venue": venue,
                "is_night": day_night == "night",
                "game_pk": (s.get("game") or {}).get("gamePk"),
                "ab": int(st.get("atBats") or 0),
                "hits": hits,
                "tb": tb,
                "hr": hr,
                # 2B/3B were fetched but never stored -- without them every XBH
                # prop (~560 ledger picks) was ungradeable and voided.
                "doubles": doubles,
                "triples": triples,
                "rbi": int(st.get("rbi") or 0),
                "runs": int(st.get("runs") or 0),
                "k": int(st.get("strikeOuts") or 0),
                "bb": int(st.get("baseOnBalls") or 0),
                "pa": int(st.get("plateAppearances") or 0),
                # DFS receipts need these (DK: SB +5, HBP +2) -- added 2026-08-18.
                "sb": int(st.get("stolenBases") or 0),
                "hbp": int(st.get("hitByPitch") or 0),
            })
        return out
    except Exception:
        return []


def _pitcher_gamelog(pid: int, n: int = GAMELOG_DEPTH) -> List[Dict[str, Any]]:
    """Pull last N starts pitching gamelog via MLB Stats API directly so we
    can enrich with venue + is_home + is_night (the stats_repo wrapper
    doesn't surface those). Falls back to sr if the direct call fails."""
    import requests
    _ensure_team_venues()
    try:
        r = requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{pid}/stats",
            params={"stats": "gameLog", "group": "pitching", "season": dt.date.today().year},
            timeout=10,
        ).json()
        splits = ((r.get("stats") or [{}])[0].get("splits") or [])
        out = []
        for s in splits[-n:][::-1]:
            st = s.get("stat") or {}
            opp = (s.get("opponent") or {}).get("abbreviation") or "?"
            opp_id = (s.get("opponent") or {}).get("id")
            team_id = (s.get("team") or {}).get("id")
            d = s.get("date") or ""
            is_home = bool(s.get("isHome"))
            day_night = ((s.get("game") or {}).get("dayNight") or "").lower()
            venue_team_id = team_id if is_home else opp_id
            venue = _TEAM_VENUES.get(venue_team_id) if venue_team_id else None
            # ip comes as "5.2" string -- keep raw, downstream normalizes
            out.append({
                "date": d,
                "vs": opp,
                "is_home": is_home,
                "venue": venue,
                "is_night": day_night == "night",
                "game_pk": (s.get("game") or {}).get("gamePk"),
                "ip": st.get("inningsPitched"),
                "k": int(st.get("strikeOuts") or 0),
                "er": int(st.get("earnedRuns") or 0),
                "bb": int(st.get("baseOnBalls") or 0),
                "h": int(st.get("hits") or 0),
                "hr": int(st.get("homeRuns") or 0),
                "bf": int(st.get("battersFaced") or 0),
                # DFS receipts: DK W +4 -- per-game win credit (added 2026-08-18).
                "win": int(st.get("wins") or 0),
            })
        if out:
            return out
    except Exception:
        pass
    # Fallback to stats_repo
    try:
        gl = sr.pitcher_gamelog(pid) or []
        out = []
        for g in gl[:n]:
            out.append({
                "date": g.get("date"),
                "vs": g.get("opp"),
                "is_home": None, "venue": None, "is_night": None,
                "ip": g.get("ip"),
                "k": g.get("k"),
                "er": g.get("er"),
                "bb": g.get("bb"),
                "h": g.get("h"),
            })
        return out
    except Exception:
        return []


def run() -> Dict[str, Any]:
    pids = _player_ids_today()
    # Extend with the SETTLEMENT universe: players on pending MLB ledger picks
    # whose gamelogs the grader needs. Names resolve to ids via the cached
    # people-search (sr.pitcher_id_by_name is a generic person lookup).
    have_names = {str(v.get("name") or "").lower() for v in pids.values()}
    n_ledger = 0
    # DFS lineup players join the fetch set (2026-09-02) -- the receipts grader
    # reads this cache, so its universe must cover them (see _dfs_lineup_players).
    for info in _pending_ledger_players() + _dfs_lineup_players():
        if len(pids) >= MAX_PLAYERS:
            break
        if info["name"].lower() in have_names:
            continue
        # A row that already knows its mlb id (DFS lineup slots) skips name
        # resolution entirely -- names are not unique (two Max Muncys).
        pid = info.get("id") or sr.pitcher_id_by_name(info["name"])
        if pid and int(pid) not in pids:
            pids[int(pid)] = {"name": info["name"], "kind": info["kind"]}
            have_names.add(info["name"].lower())
            n_ledger += 1
    pids_limited = dict(list(pids.items())[:MAX_PLAYERS])
    print(f"  pulling gamelogs for {len(pids_limited)} players "
          f"({len(pids) - n_ledger} with props today + {n_ledger} from pending "
          f"ledger picks + DFS lineups)")
    out: Dict[str, Any] = {}
    for i, (pid, info) in enumerate(pids_limited.items()):
        if i % 50 == 0:
            print(f"    {i}/{len(pids_limited)}...")
        games = _batter_gamelog(pid) if info["kind"] == "batter" else _pitcher_gamelog(pid)
        out[str(pid)] = {"name": info["name"], "kind": info["kind"], "games": games}
    # NO-CLOBBER: an empty fetch (outage, empty boards) must not overwrite a
    # useful cache with nothing -- the grader would lose its only box-score
    # source. Keep the old file and say so.
    if not out:
        prev = _load(OUT_PATH)
        if prev.get("by_player_id"):
            print("  no players resolved -- keeping the existing gamelog cache "
                  f"({len(prev['by_player_id'])} players) instead of clobbering it")
            return prev
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "depth": GAMELOG_DEPTH,
        "n_players": len(out),
        "by_player_id": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_players']} players")
