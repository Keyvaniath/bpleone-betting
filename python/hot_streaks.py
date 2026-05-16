"""
EdgeStat -- cross-slate hot-streak heatmap.

For every player on tonight's slate, computes a "heat" score from player_gamelogs
+ player_breakdowns recent form vs season:
  - Batters: OPS_L7 - OPS_season, HR_per_game_L7 - season_HR_per_game
  - Pitchers: K9_recent - K9_season, ERA_recent - ERA_season

Output: data/hot_streaks.json
  { hot_batters: [...], cold_batters: [...], hot_pitchers: [...], cold_pitchers: [...] }
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BD_PATH = os.path.join(DATA_DIR, "player_breakdowns.json")
OUT_PATH = os.path.join(DATA_DIR, "hot_streaks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    bd = (_load(BD_PATH).get("by_id") or {})
    batters_heat: List[Dict[str, Any]] = []
    pitchers_heat: List[Dict[str, Any]] = []
    for pid, p in bd.items():
        if not p.get("on_slate"):
            continue
        kind = p.get("kind")
        form = p.get("form") or {}
        l7 = form.get("last_7") or {}
        season = p.get("season") or {}
        if kind == "pitcher":
            r_k9 = (l7.get("k9") or 0)
            s_k9 = float(season.get("strikeoutsPer9Inn") or season.get("strikeOutsPer9Inn") or 0)
            r_era = (l7.get("era") or 0)
            s_era = float(season.get("era") or 0)
            # Heat = K9_uptick + ERA_drop. Need at least 1 recent start.
            if not l7.get("n_starts"):
                continue
            heat = (r_k9 - s_k9) + (s_era - r_era) * 0.5
            pitchers_heat.append({
                "player_id": pid, "name": p.get("name"), "team": p.get("team"),
                "n_starts_l7": l7.get("n_starts"),
                "recent_k9": r_k9, "season_k9": s_k9,
                "recent_era": r_era, "season_era": s_era,
                "heat": round(heat, 3),
                "tonight_matchup": (p.get("tonight") or {}).get("matchup"),
            })
        else:
            if not l7.get("n_games"):
                continue
            r_obp = l7.get("obp") or 0
            r_slg = l7.get("slg") or 0
            r_ops = r_obp + r_slg
            s_ops = float(season.get("ops") or 0)
            r_hr_g = l7.get("hr_per_game") or 0
            s_hr_g = (float(season.get("homeRuns") or 0) / float(season.get("gamesPlayed") or 1)) if season.get("gamesPlayed") else 0
            heat = (r_ops - s_ops) * 2 + (r_hr_g - s_hr_g) * 5
            batters_heat.append({
                "player_id": pid, "name": p.get("name"), "team": p.get("team"),
                "n_games_l7": l7.get("n_games"),
                "recent_ops": round(r_ops, 3), "season_ops": s_ops,
                "recent_hr_per_game": r_hr_g, "season_hr_per_game": round(s_hr_g, 3),
                "heat": round(heat, 3),
                "tonight_matchup": (p.get("tonight") or {}).get("matchup"),
                "lineup_order": (p.get("tonight") or {}).get("lineup_order"),
            })
    batters_heat.sort(key=lambda x: -x["heat"])
    pitchers_heat.sort(key=lambda x: -x["heat"])
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "hot_batters": batters_heat[:25],
        "cold_batters": batters_heat[-15:][::-1] if len(batters_heat) >= 15 else [],
        "hot_pitchers": pitchers_heat[:15],
        "cold_pitchers": pitchers_heat[-10:][::-1] if len(pitchers_heat) >= 10 else [],
        "n_batters_scored": len(batters_heat),
        "n_pitchers_scored": len(pitchers_heat),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Batters scored: {p['n_batters_scored']}")
    print(f"  Top 5 hot batters:")
    for b in p["hot_batters"][:5]:
        print(f"    {b['name']:25} heat={b['heat']:.2f}  L7 OPS {b['recent_ops']} vs season {b['season_ops']}")
    print(f"  Top 5 hot pitchers:")
    for b in p["hot_pitchers"][:5]:
        print(f"    {b['name']:25} heat={b['heat']:.2f}  L7 K/9 {b['recent_k9']} vs season {b['season_k9']}")
