"""
EdgeStat -- NHL skater prop projections.

For each NHL skater on a team playing tonight, project:
   anytime goal scorer (AGS)  -- P(skater scores 1+)
   shots on goal over/under   -- Poisson around SOG/game
   points (G + A) over/under  -- Poisson around PTS/game
   2+ points (multi-point game)

Active-teams filter from nhl_state.json keeps the output tight during
playoff off-days.

Depends on player_stats_nhl.json having CORRECT shots_per_game and
points_per_game (recent fix to espn_player_stats.py HOCKEY_IDX).

Output: data/nhl_skater_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_props.json")

SIGMA_SOG_PCT = 0.45   # SOG std/mean ratio for variance modeling


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _poisson_p_zero(lam):
    return math.exp(-lam) if lam > 0 else 1.0


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _active_teams_today() -> set:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    active = set()
    for g in (state.get("games") or []):
        if g.get("state") == "post": continue
        for fld in ("home_team", "away_team"):
            v = g.get(fld)
            if v: active.add(v)
    return active


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_nhl.json"))
    players = stats.get("players") or []
    active_teams = _active_teams_today()
    is_playoffs = len(active_teams) > 0 and len(active_teams) <= 4

    players_out = []
    for p in players:
        if active_teams and p.get("team") not in active_teams:
            continue
        sog = p.get("shots_per_game") or 0
        pts = p.get("points_per_game") or 0
        goals = p.get("goals_per_game") or 0
        if sog < 1.0 and pts < 0.3: continue   # 4th-liners

        # Anytime goal P = 1 - Poisson(goals=0)
        p_ags = 1 - _poisson_p_zero(goals)

        props: Dict[str, Any] = {}
        # Anytime goal scorer
        if p_ags > 0.05:
            props["anytime_goal"] = {
                "p": round(p_ags, 4),
                "fair_yes": _american(p_ags),
                "fair_no": _american(1 - p_ags),
            }
        # SOG over/under at common lines (1.5 / 2.5 / 3.5 / 4.5 / 5.5)
        for line in (1.5, 2.5, 3.5, 4.5, 5.5):
            p_over = _poisson_p_over(sog, line)
            if 0.10 < p_over < 0.95:
                props[f"sog_over_{line}"] = {
                    "p": round(p_over, 4),
                    "fair_over": _american(p_over),
                    "fair_under": _american(1 - p_over),
                    "line": line,
                }
        # Points (G+A) over/under
        for line in (0.5, 1.5, 2.5):
            p_over = _poisson_p_over(pts, line)
            if 0.10 < p_over < 0.95:
                props[f"points_over_{line}"] = {
                    "p": round(p_over, 4),
                    "fair_over": _american(p_over),
                    "fair_under": _american(1 - p_over),
                    "line": line,
                }
        # 2+ points (multi-point game)
        p_2pts = 1 - sum(math.exp(-pts) * (pts ** k) / math.factorial(k) for k in (0, 1)) if pts > 0 else 0.0
        if p_2pts > 0.05:
            props["multi_point"] = {
                "p": round(p_2pts, 4),
                "fair_yes": _american(p_2pts),
                "fair_no": _american(1 - p_2pts),
            }

        if not props: continue
        players_out.append({
            "name": p.get("name"),
            "team": p.get("team_abbr"),
            "position": p.get("position"),
            "season_goals_per_game": round(goals, 2),
            "season_assists_per_game": round(p.get("assists_per_game") or 0, 2),
            "season_points_per_game": round(pts, 2),
            "season_sog_per_game": round(sog, 2),
            "p_anytime_goal": round(p_ags, 4),
            "p_2_plus_points": round(p_2pts, 4),
            "props": props,
        })

    # Sweet spot picks
    sweet = []
    for pp in players_out:
        for mkt, info in (pp.get("props") or {}).items():
            prob = info.get("p")
            if not prob or not (0.55 <= prob <= 0.88): continue
            sweet.append({
                "name": pp["name"], "team": pp["team"],
                "market": mkt, "prob": prob,
                "fair_yes": info.get("fair_yes") or info.get("fair_over"),
            })
    sweet.sort(key=lambda x: -x["prob"])

    total_props = sum(len(p.get("props") or {}) for p in players_out)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_teams_today": sorted(list(active_teams)),
        "is_playoffs": is_playoffs,
        "n_players": len(players_out),
        "n_total_props": total_props,
        "n_sweet_spot": len(sweet),
        "top_ags": sorted(players_out, key=lambda p: -p["p_anytime_goal"])[:15],
        "top_multi_point": sorted(players_out, key=lambda p: -p["p_2_plus_points"])[:10],
        "top_picks": sweet[:40],
        "players": players_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NHL skater props: {p['n_players']} players ({p['n_total_props']} props, {p['n_sweet_spot']} sweet)")
    print(f"  Active teams: {p['active_teams_today']}")
    print(f"\n  Top 5 anytime goal scorer (AGS):")
    for pp in p["top_ags"][:5]:
        print(f"    {pp['name'][:25]:25s} ({pp['team']:3s}) G/g={pp['season_goals_per_game']:.2f} -> P(goal) {pp['p_anytime_goal']*100:.0f}%")
    print(f"\n  Top 5 sweet-spot picks:")
    for x in p["top_picks"][:5]:
        print(f"    {x['name'][:22]:22s} ({x['team']:3s}) {x['market']:18s} p={x['prob']*100:.0f}% fair={x['fair_yes']}")
