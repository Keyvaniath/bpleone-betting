"""
EdgeStat -- per-game research depth score.

For each game in today's slate, count how many signal sources have data
available. A game with high research depth (lineup posted + Statcast for
both SPs + bullpen workload + ump tendency + recent form + H2H sample +
weather + park-handed splits + recent transactions) is one where the
model has the most context.

A low-depth game (probable pitcher TBD, lineup not posted, rookie SP with
no Statcast yet) means projections are running on thin data.

Writes data/research_depth.json keyed by matchup.

Useful overlay: when filtering bets, prefer high-depth games.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "research_depth.json")


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def build_all() -> Dict[str, Any]:
    matchups = _load("matchups.json")
    bp = _load("bullpen_workload.json").get("teams") or {}
    pm = {g["matchup"]: g for g in (_load("pitch_matchup.json").get("games") or [])}
    pr = {g["matchup"]: g for g in (_load("pitcher_rest.json").get("games") or [])}
    series = {g["matchup"]: g for g in (_load("series_context.json").get("games") or [])}
    travel = {g["matchup"]: g for g in (_load("travel.json").get("games") or [])}
    nrfi = {g["matchup"]: g for g in (_load("nrfi.json").get("games") or [])}
    f5 = {g["matchup"]: g for g in (_load("first_five.json").get("games") or [])}
    rl = {g["matchup"]: g for g in (_load("run_line.json").get("games") or [])}
    lq = {g["matchup"]: g for g in (_load("lineup_quality.json").get("games") or [])}

    out_games = []
    for g in matchups.get("games", []):
        m = g.get("matchup")
        signals: Dict[str, bool] = {
            "lineup_home": bool((g.get("lineups") or {}).get("home_posted")),
            "lineup_away": bool((g.get("lineups") or {}).get("away_posted")),
            "home_sp_id": bool((g.get("home_pitcher") or {}).get("id")),
            "away_sp_id": bool((g.get("away_pitcher") or {}).get("id")),
            "home_sp_arsenal": bool((g.get("home_pitcher") or {}).get("arsenal")),
            "away_sp_arsenal": bool((g.get("away_pitcher") or {}).get("arsenal")),
            "home_sp_career": bool((g.get("home_pitcher") or {}).get("career")),
            "away_sp_career": bool((g.get("away_pitcher") or {}).get("career")),
            "home_sp_recent": bool((g.get("home_pitcher") or {}).get("recent")),
            "away_sp_recent": bool((g.get("away_pitcher") or {}).get("recent")),
            "home_sp_pc_history": bool((g.get("home_pitcher") or {}).get("pitch_count_history")),
            "away_sp_pc_history": bool((g.get("away_pitcher") or {}).get("pitch_count_history")),
            "home_sp_h2h_vs_opp": ((g.get("home_pitcher") or {}).get("vs_opp_this_season") or {}).get("starts", 0) > 0,
            "away_sp_h2h_vs_opp": ((g.get("away_pitcher") or {}).get("vs_opp_this_season") or {}).get("starts", 0) > 0,
            "weather": bool(g.get("weather")),
            "umpire": bool((g.get("umpire") or {}).get("ump_name")),
            "bullpen_home": bool((g.get("bullpens") or {}).get("home")),
            "bullpen_away": bool((g.get("bullpens") or {}).get("away")),
            "pitch_matchup": m in pm,
            "pitcher_rest": m in pr,
            "series_ctx": m in series,
            "travel": m in travel,
            "nrfi": m in nrfi,
            "f5": m in f5,
            "run_line": m in rl,
            "lineup_quality": m in lq,
        }
        present = sum(1 for v in signals.values() if v)
        total = len(signals)
        score = round(100 * present / total, 1)
        # Tier
        if score >= 80:
            tier = "elite"
        elif score >= 65:
            tier = "high"
        elif score >= 50:
            tier = "medium"
        else:
            tier = "low"
        out_games.append({
            "matchup": m,
            "time": g.get("time"),
            "depth_score": score,
            "depth_tier": tier,
            "signals_present": present,
            "signals_total": total,
            "missing": [k for k, v in signals.items() if not v],
        })
    out_games.sort(key=lambda x: -x["depth_score"])
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
    }


def write_depth(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote research_depth -> {path}")
    print(f"  Games scored: {len(payload.get('games', []))}")
    for g in payload.get("games", [])[:5]:
        print(f"  {g['matchup']:14} | depth {g['depth_score']}% ({g['signals_present']}/{g['signals_total']}, {g['depth_tier']})")


if __name__ == "__main__":
    write_depth(build_all())
