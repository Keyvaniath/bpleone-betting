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


def _batter_gamelog(pid: int, n: int = GAMELOG_DEPTH) -> List[Dict[str, Any]]:
    """Pull last N games batting gamelog via MLB Stats API. Cached in stats_repo."""
    import requests
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
            d = s.get("date") or ""
            hits = int(st.get("hits") or 0)
            doubles = int(st.get("doubles") or 0)
            triples = int(st.get("triples") or 0)
            hr = int(st.get("homeRuns") or 0)
            singles = hits - doubles - triples - hr
            tb = singles + 2 * doubles + 3 * triples + 4 * hr
            out.append({
                "date": d,
                "vs": opp,
                "ab": int(st.get("atBats") or 0),
                "hits": hits,
                "tb": tb,
                "hr": hr,
                "rbi": int(st.get("rbi") or 0),
                "runs": int(st.get("runs") or 0),
                "k": int(st.get("strikeOuts") or 0),
                "bb": int(st.get("baseOnBalls") or 0),
            })
        return out
    except Exception:
        return []


def _pitcher_gamelog(pid: int, n: int = GAMELOG_DEPTH) -> List[Dict[str, Any]]:
    """Pull last N starts pitching gamelog. Pitchers start every 4-5 days,
    so 14 games covers ~60 days of starts."""
    try:
        gl = sr.pitcher_gamelog(pid) or []
        out = []
        for g in gl[:n]:
            out.append({
                "date": g.get("date"),
                "vs": g.get("opp"),
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
    pids_limited = dict(list(pids.items())[:MAX_PLAYERS])
    print(f"  pulling gamelogs for {len(pids_limited)} players (of {len(pids)} with props today)")
    out: Dict[str, Any] = {}
    for i, (pid, info) in enumerate(pids_limited.items()):
        if i % 50 == 0:
            print(f"    {i}/{len(pids_limited)}...")
        games = _batter_gamelog(pid) if info["kind"] == "batter" else _pitcher_gamelog(pid)
        out[str(pid)] = {"name": info["name"], "kind": info["kind"], "games": games}
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
