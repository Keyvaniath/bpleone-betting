"""
EdgeStat -- Cross-sport top props leaderboard.

Aggregates the top INDIVIDUAL props across every sport by raw edge_pp.
Different from cross_sport_top_picks which is at the entity (player/
team) level - this is at the per-prop level.

Output: data/cross_sport_top_props_leaderboard.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_top_props_leaderboard.json")


# (sport, filename, rows_key, subject_field, market_label)
PROP_SOURCES = [
    ("MLB", "mlb_pitcher_strikeouts_props.json", "rows", "pitcher", "K_OVER/UNDER"),
    ("MLB", "mlb_pitcher_outs_props.json", "rows", "pitcher", "OUTS_OVER/UNDER"),
    ("MLB", "mlb_pitcher_quality_start_props.json", "rows", "pitcher", "QS_YES/NO"),
    ("MLB", "mlb_total_bases_props.json", "rows", "batter", "TB_OVER/UNDER"),
    ("MLB", "mlb_batter_rbi_props.json", "rows", "batter", "RBI_1PLUS"),
    ("MLB", "mlb_batter_2plus_hits_props.json", "rows", "batter", "2PLUS_HITS"),
    ("MLB", "mlb_to_hit_hr_yn.json", "rows", "batter", "HR_YES"),
    ("MLB", "mlb_doubles_props.json", "rows", "batter", "DOUBLE_YES"),
    ("MLB", "mlb_team_total_edge.json", "rows", "team", "TT_OVER/UNDER"),
    ("MLB", "mlb_game_total_alt_props.json", "rows", "matchup", "GAME_TOTAL"),
    ("NBA", "nba_player_points_props.json", "rows", "player", "PTS_OVER/UNDER"),
    ("NBA", "nba_player_assists_props.json", "rows", "player", "AST_OVER/UNDER"),
    ("NBA", "nba_player_rebounds_props.json", "rows", "player", "REB_OVER/UNDER"),
    ("NBA", "nba_player_threes_props.json", "rows", "player", "3PM_OVER/UNDER"),
    ("NBA", "nba_player_pra_props.json", "rows", "player", "PRA_OVER/UNDER"),
    ("NHL", "nhl_skater_sog_props.json", "rows", "player", "SOG_OVER/UNDER"),
    ("NHL", "nhl_skater_points_props.json", "rows", "player", "POINTS_OVER/UNDER"),
    ("NHL", "nhl_goalie_saves_props.json", "rows", "goalie", "SAVES_OVER/UNDER"),
    ("SOCCER", "soccer_total_goals_props.json", "rows", "match", "GOALS_OVER/UNDER"),
    ("SOCCER", "soccer_corners_props.json", "rows", "match", "CORNERS_OVER/UNDER"),
    ("TENNIS", "tennis_aces_props.json", "rows", "player", "ACES_OVER/UNDER"),
    ("UFC", "ufc_strikes_takedowns_props.json", "rows", "fighter", "STRIKES_OVER"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def run() -> Dict[str, Any]:
    all_props: List[Dict[str, Any]] = []

    for sport, fname, rows_key, subject_field, market_label in PROP_SOURCES:
        data = _load(os.path.join(DATA_DIR, fname))
        for r in (data.get(rows_key) or []):
            if not isinstance(r, dict): continue
            edge_pp = _safe(r.get("edge_pp") or r.get("edge"))
            if abs(edge_pp) < 0.04: continue  # require at least 4% edge
            edge_class = (r.get("edge_class") or "").upper()
            if edge_class in ("NONE", ""): continue

            all_props.append({
                "sport": sport,
                "market": market_label,
                "subject": r.get(subject_field) or "?",
                "team": r.get("team"),
                "matchup": r.get("matchup") or r.get("match") or r.get("fight"),
                "edge_pp": round(edge_pp * 100, 2),  # convert to percentage points
                "edge_class": edge_class,
                "line": r.get("line"),
                "model_p": r.get("model_p") or r.get("p"),
            })

    # Sort by absolute edge descending
    all_props.sort(key=lambda p: -abs(p["edge_pp"]))

    # By sport breakdown
    by_sport: Dict[str, int] = {}
    for p in all_props:
        by_sport[p["sport"]] = by_sport.get(p["sport"], 0) + 1

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total_props": len(all_props),
        "by_sport": by_sport,
        "method_note": "Top individual props across sports by absolute edge_pp. "
                       "Requires |edge| >= 4 percentage points. Sorted by abs edge.",
        "top_20": all_props[:20],
        "top_50_overall": all_props[:50],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[top-props] {o['n_total_props']} props with >=4% edge "
          f"by_sport={o['by_sport']} -> {OUT}")
