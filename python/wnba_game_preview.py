"""
EdgeStat -- WNBA per-game preview synthesizer.

For each WNBA game, produces a unified preview from:
  - Top player ceiling/fade picks per side (from wnba_player_confluence_score)
  - Team alts (from wnba_team_alts_props)
  - 20+ pts / DD / threes signals

Each game gets a tier:
  GAME_LOCK   = 2+ player LOCKs on same side
  GAME_STRONG = at least 1 player LOCK
  GAME_LEAN   = 2+ player STRONGs
  GAME_PASS   = no aligned signals

Output: data/wnba_game_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_game_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "wnba_player_confluence_score.json"))
    team_alts = _load(os.path.join(DATA_DIR, "wnba_team_alts_props.json"))

    # Group players by matchup
    players_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (conf.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        players_by_matchup.setdefault(m, []).append(r)

    team_alts_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (team_alts.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        team_alts_by_matchup.setdefault(m, []).append(r)

    previews: List[Dict[str, Any]] = []
    for matchup, players in players_by_matchup.items():
        if not matchup: continue

        # Group locks by team
        locks_by_team: Dict[str, int] = {}
        strong_by_team: Dict[str, int] = {}
        for p in players:
            if "LOCK" in (p.get("tier") or ""):
                locks_by_team[p.get("team") or ""] = locks_by_team.get(p.get("team") or "", 0) + 1
            elif "STRONG" in (p.get("tier") or ""):
                strong_by_team[p.get("team") or ""] = strong_by_team.get(p.get("team") or "", 0) + 1

        locks = [p for p in players if "LOCK" in (p.get("tier") or "")]
        strong = [p for p in players if "STRONG" in (p.get("tier") or "")]
        fades = [p for p in players if "FADE" in (p.get("tier") or "")]

        max_team_locks = max(locks_by_team.values()) if locks_by_team else 0

        if max_team_locks >= 2:
            tier = "GAME_LOCK"
        elif len(locks) >= 1:
            tier = "GAME_STRONG"
        elif len(strong) >= 2:
            tier = "GAME_LEAN"
        else:
            tier = "GAME_PASS"

        angle: List[str] = []
        for p in locks:
            angle.append(f"{p.get('player')} PTS OVER + DD YES + 20+ pts YES")
        for s in strong[:3]:
            angle.append(f"{s.get('player')} PTS OVER + REB OVER")
        for fd in fades:
            angle.append(f"FADE {fd.get('player')} PTS UNDER")

        previews.append({
            "matchup": matchup,
            "tier": tier,
            "n_player_locks": len(locks),
            "n_player_strong": len(strong),
            "n_player_fades": len(fades),
            "locks_by_team": locks_by_team,
            "top_player_picks": [
                {"player": p.get("player"), "team": p.get("team"),
                 "tier": p.get("tier"), "score": p.get("composite_score")}
                for p in (locks + strong)[:5]
            ],
            "recommended_angles": angle,
        })

    tier_order = {"GAME_LOCK": 4, "GAME_STRONG": 3, "GAME_LEAN": 2, "GAME_PASS": 1}
    previews.sort(key=lambda g: (-tier_order.get(g["tier"], 0),
                                  -g.get("n_player_locks", 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(previews),
        "n_locks": sum(1 for g in previews if g["tier"] == "GAME_LOCK"),
        "n_strong": sum(1 for g in previews if g["tier"] == "GAME_STRONG"),
        "n_lean": sum(1 for g in previews if g["tier"] == "GAME_LEAN"),
        "method_note": "Per-game WNBA preview. GAME_LOCK = 2+ player LOCKs on "
                       "same team; STRONG = 1+ player LOCK; LEAN = 2+ STRONGs.",
        "previews": previews,
        "locks_and_strong": [g for g in previews
                             if g["tier"] in ("GAME_LOCK", "GAME_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-preview] {o['n_games']} games "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN) -> {OUT}")
