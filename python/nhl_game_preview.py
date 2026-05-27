"""
EdgeStat -- NHL per-game preview synthesizer.

For each NHL game, produces a unified preview combining:
  - Both goalie confluence scores (HOME + AWAY)
  - Both team confluence scores
  - Top skater ceiling picks per side
  - Game total SOG + period totals signals

Each game gets a tier:
  GAME_LOCK   = GOALIE_LOCK on one side + TEAM_LOCK on opposing side
  GAME_STRONG = at least 1 LOCK across goalie/team/skater
  GAME_LEAN   = at least 2 STRONGs aligned
  GAME_PASS   = no aligned signals

Output: data/nhl_game_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_game_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    goalies = _load(os.path.join(DATA_DIR, "nhl_goalie_confluence_score.json"))
    teams = _load(os.path.join(DATA_DIR, "nhl_team_confluence_score.json"))
    skaters = _load(os.path.join(DATA_DIR, "nhl_skater_confluence_score.json"))
    sog_total = _load(os.path.join(DATA_DIR, "nhl_game_total_sog.json"))
    period = _load(os.path.join(DATA_DIR, "nhl_period_totals_props.json"))

    goalies_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (goalies.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        goalies_by_matchup.setdefault(m, []).append(r)

    teams_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (teams.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        teams_by_matchup.setdefault(m, []).append(r)

    skaters_by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for r in (skaters.get("rows") or []):
        if not isinstance(r, dict): continue
        m = r.get("matchup") or ""
        skaters_by_matchup.setdefault(m, []).append(r)

    sog_over: Dict[str, bool] = {}
    for r in (sog_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            sog_over[r.get("matchup", "")] = True

    period_over: Dict[str, bool] = {}
    for r in (period.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            period_over[r.get("matchup", "")] = True

    all_matchups = (set(goalies_by_matchup) | set(teams_by_matchup)
                    | set(skaters_by_matchup))

    previews: List[Dict[str, Any]] = []
    for matchup in all_matchups:
        if not matchup: continue
        goalie_rows = goalies_by_matchup.get(matchup, [])
        team_rows = teams_by_matchup.get(matchup, [])
        skater_rows = skaters_by_matchup.get(matchup, [])

        goalie_locks = [g for g in goalie_rows if "LOCK" in (g.get("tier") or "")]
        goalie_strong = [g for g in goalie_rows if "STRONG" in (g.get("tier") or "")]
        goalie_fades = [g for g in goalie_rows if "FADE" in (g.get("tier") or "")]
        team_locks = [t for t in team_rows if "LOCK" in (t.get("tier") or "")]
        team_strong = [t for t in team_rows if "STRONG" in (t.get("tier") or "")]
        skater_locks = [s for s in skater_rows if "LOCK" in (s.get("tier") or "")]
        skater_strong = [s for s in skater_rows if "STRONG" in (s.get("tier") or "")]

        if goalie_locks and team_locks:
            tier = "GAME_LOCK"
        elif goalie_locks or team_locks or len(skater_locks) >= 2:
            tier = "GAME_STRONG"
        elif len(goalie_strong) + len(team_strong) + len(skater_strong) >= 2:
            tier = "GAME_LEAN"
        else:
            tier = "GAME_PASS"

        angle: List[str] = []
        for g in goalie_locks:
            angle.append(f"{g.get('goalie')} saves OVER + 30+ saves YES + win YES")
        for t in team_locks:
            angle.append(f"{t.get('team')} team total OVER + 4+ goals YES")
        for s in skater_locks:
            angle.append(f"{s.get('skater')} SOG OVER + anytime goal YES")
        if sog_over.get(matchup):
            angle.append(f"{matchup} game total SOG OVER")
        if period_over.get(matchup):
            angle.append(f"{matchup} period totals OVER")
        for gf in goalie_fades:
            angle.append(f"FADE {gf.get('goalie')} saves UNDER + opp 4+ goals YES")

        previews.append({
            "matchup": matchup,
            "tier": tier,
            "n_goalie_locks": len(goalie_locks),
            "n_team_locks": len(team_locks),
            "n_skater_locks": len(skater_locks),
            "n_goalie_fades": len(goalie_fades),
            "goalie_summary": [
                {"goalie": g.get("goalie"), "tier": g.get("tier"),
                 "score": g.get("composite_score")}
                for g in goalie_rows
            ],
            "team_summary": [
                {"team": t.get("team"), "side": t.get("side"),
                 "tier": t.get("tier"), "score": t.get("composite_score")}
                for t in team_rows
            ],
            "top_skater_picks": [
                {"skater": s.get("skater"), "tier": s.get("tier"),
                 "score": s.get("composite_score")}
                for s in (skater_locks + skater_strong)[:5]
            ],
            "recommended_angles": angle,
        })

    tier_order = {"GAME_LOCK": 4, "GAME_STRONG": 3, "GAME_LEAN": 2, "GAME_PASS": 1}
    previews.sort(key=lambda g: (-tier_order.get(g["tier"], 0),
                                  -(g.get("n_goalie_locks", 0)
                                    + g.get("n_team_locks", 0))))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(previews),
        "n_locks": sum(1 for g in previews if g["tier"] == "GAME_LOCK"),
        "n_strong": sum(1 for g in previews if g["tier"] == "GAME_STRONG"),
        "n_lean": sum(1 for g in previews if g["tier"] == "GAME_LEAN"),
        "n_pass": sum(1 for g in previews if g["tier"] == "GAME_PASS"),
        "method_note": "Per-game NHL preview. Combines goalie + team + skater "
                       "confluence scores + SOG/period totals. GAME_LOCK = "
                       "GOALIE_LOCK + TEAM_LOCK; STRONG = 1+ LOCK; LEAN = 2+ "
                       "STRONGs aligned.",
        "previews": previews,
        "locks_and_strong": [g for g in previews
                             if g["tier"] in ("GAME_LOCK", "GAME_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-game-preview] {o['n_games']} games "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN, {o['n_pass']} PASS) -> {OUT}")
