"""
EdgeStat -- lineup churn watcher.

Diffs current matchups.json lineups vs the prior snapshot (saved on the
last run). Detects:
  - Players newly added to a lineup
  - Players removed from a lineup (scratched / pinch / left game)
  - Lineup order shifts (#3 batter dropped to #6 etc.)

For each removed player, flags any open props on them as STALE so the
front-end can show a warning. For each added player, surfaces them as a
NEW PROP CANDIDATE alert.

Runs cheap & often (could fit in live-games.yml). Idempotent: stores a
.lineup_prev.json snapshot at writeback time.

Output: data/lineup_churn.json
  {
    "generated_at": "...",
    "n_added": 2, "n_removed": 1, "n_shifts": 3,
    "added":   [{matchup, side, player, order}],
    "removed": [{matchup, side, player, prev_order}],
    "shifts":  [{matchup, side, player, from, to}],
    "affected_props": [{player, market, line, status: 'scratched'}]   # joinable with props
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
PREV_PATH = os.path.join(DATA_DIR, ".lineup_prev.json")
OUT_PATH = os.path.join(DATA_DIR, "lineup_churn.json")


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _snapshot(matchups: Dict[str, Any]) -> Dict[str, Any]:
    """Project current matchups into a compact lineup snapshot for diffing."""
    out: Dict[str, Any] = {}
    for g in matchups.get("games") or []:
        key = g.get("matchup") or ""
        lineups = g.get("lineups") or {}
        out[key] = {}
        for side in ("home", "away"):
            entries = []
            for b in lineups.get(side) or []:
                entries.append({"id": b.get("id"), "name": b.get("name"),
                                  "order": b.get("order"), "pos": b.get("pos")})
            out[key][side] = entries
    return out


def _diff(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    added, removed, shifts = [], [], []
    for matchup, sides in curr.items():
        prev_sides = prev.get(matchup) or {}
        for side, entries in sides.items():
            prev_entries = prev_sides.get(side) or []
            prev_by_id = {e.get("id"): e for e in prev_entries if e.get("id")}
            curr_by_id = {e.get("id"): e for e in entries if e.get("id")}
            for pid, e in curr_by_id.items():
                if pid not in prev_by_id:
                    added.append({"matchup": matchup, "side": side,
                                   "player": e.get("name"), "id": pid,
                                   "order": e.get("order")})
                else:
                    if e.get("order") != prev_by_id[pid].get("order"):
                        shifts.append({"matchup": matchup, "side": side,
                                        "player": e.get("name"), "id": pid,
                                        "from": prev_by_id[pid].get("order"),
                                        "to": e.get("order")})
            for pid, e in prev_by_id.items():
                if pid not in curr_by_id:
                    removed.append({"matchup": matchup, "side": side,
                                     "player": e.get("name"), "id": pid,
                                     "prev_order": e.get("order")})
    return {"added": added, "removed": removed, "shifts": shifts}


def _affected_props(removed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """For each removed player, list all open DK + PP props on them."""
    rem_ids = {r["id"] for r in removed}
    aff: List[Dict[str, Any]] = []
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        if p.get("player_id") in rem_ids:
            aff.append({"player": p.get("player"), "player_id": p.get("player_id"),
                         "market": p.get("market"), "line": p.get("line"),
                         "source": "DK", "status": "scratched"})
    for p in (_load(PICKEM_PATH).get("props") or []):
        if p.get("player_id") in rem_ids:
            aff.append({"player": p.get("player"), "player_id": p.get("player_id"),
                         "market": p.get("market"), "line": p.get("pp_line"),
                         "source": "PP", "status": "scratched"})
    return aff


def run() -> Dict[str, Any]:
    matchups = _load(MATCHUPS_PATH)
    curr = _snapshot(matchups)
    prev = _load(PREV_PATH)
    diff = _diff(prev, curr) if prev else {"added": [], "removed": [], "shifts": []}
    aff = _affected_props(diff["removed"])
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_added": len(diff["added"]),
        "n_removed": len(diff["removed"]),
        "n_shifts": len(diff["shifts"]),
        "added": diff["added"],
        "removed": diff["removed"],
        "shifts": diff["shifts"],
        "affected_props": aff,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    # Persist current snapshot for next diff
    with open(PREV_PATH, "w") as f:
        json.dump(curr, f)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  +{p['n_added']} added · -{p['n_removed']} removed · {p['n_shifts']} order shifts")
    if p["removed"]:
        print(f"  scratched today: {', '.join(r['player'] for r in p['removed'][:10])}")
    if p["affected_props"]:
        print(f"  affected props: {len(p['affected_props'])}")
