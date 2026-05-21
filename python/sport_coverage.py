"""
EdgeStat -- sport coverage summary.

Single-purpose aggregator: for each sport tonight, count
  - games on schedule
  - prop modules that produced rows
  - total strong_edges

Gives Brandon a quick "where's the action tonight?" view.

Output: data/sport_coverage.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "sport_coverage.json")

# (sport_label, [list of prop output JSONs to aggregate])
SPORT_MAP = [
    ("MLB", [
        "mlb_first5_market.json",
        "mlb_innings_1_3_totals.json",
        "mlb_innings_4_6_totals.json",
        "mlb_innings_7_9_totals.json",
        "mlb_extra_innings_prop.json",
        "mlb_run_line_props.json",
        "mlb_pitcher_strikeouts_props.json",
        "mlb_pitcher_outs_props.json",
        "mlb_pitcher_walks_props.json",
        "mlb_pitcher_er_props.json",
        "mlb_pitcher_hits_allowed_props.json",
        "mlb_pitcher_quality_start_props.json",
        "mlb_pitcher_win_props.json",
        "mlb_pitcher_rest_advantage.json",
        "mlb_to_record_hit_yn.json",
        "mlb_to_hit_hr_yn.json",
        "mlb_doubles_props.json",
        "mlb_hrr_props.json",
        "mlb_total_bases_props.json",
        "mlb_to_score_run_yn.json",
        "mlb_first_inning_hr_yn.json",
        "mlb_first_batter_retired_props.json",
        "mlb_batter_walks_props.json",
        "mlb_batter_strikeout_props.json",
        "mlb_hbp_props.json",
        "mlb_steal_props.json",
        "mlb_team_sb_total_props.json",
    ]),
    ("NBA", [
        "nba_player_points_props.json",
        "nba_player_threes_props.json",
        "nba_player_rebounds_props.json",
        "nba_player_assists_props.json",
        "nba_player_pra_props.json",
        "nba_player_turnovers_props.json",
        "nba_player_ft_attempts_props.json",
        "nba_player_blocks_steals_props.json",
        "nba_double_double_props.json",
        "nba_triple_double_props.json",
        "nba_team_alts_props.json",
        "nba_team_total_props.json",
        "nba_pace_adjusted.json",
    ]),
    ("WNBA", [
        "wnba_player_pts_props.json",
        "wnba_player_reb_ast_props.json",
        "wnba_player_threes_props.json",
        "wnba_player_blocks_steals_props.json",
        "wnba_team_alts_props.json",
    ]),
    ("NHL", [
        "nhl_anytime_goal_props.json",
        "nhl_first_goalscorer_props.json",
        "nhl_skater_sog_props.json",
        "nhl_skater_points_props.json",
        "nhl_skater_hits_blocks_props.json",
        "nhl_goalie_saves_props.json",
        "nhl_goalie_shutout_props.json",
        "nhl_goalie_win_props.json",
        "nhl_period_totals_props.json",
        "nhl_puck_line_props.json",
    ]),
    ("SOCCER", [
        "soccer_corners_props.json",
        "soccer_btts_props.json",
        "soccer_goalscorer_props.json",
        "soccer_cards_props.json",
        "soccer_total_shots_props.json",
    ]),
    ("TENNIS", [
        "tennis_match_win_props.json",
        "tennis_total_games_props.json",
        "tennis_set_score_props.json",
        "tennis_aces_props.json",
    ]),
    ("GOLF", [
        "golf_top_finish_props.json",
    ]),
    ("UFC", [
        "ufc_strikes_takedowns_props.json",
    ]),
    ("F1", [
        "f1_qualifying_predictor.json",
    ]),
]

# Sport state file with games count
SPORT_STATE = {
    "MLB":    "matchups.json",
    "NBA":    "nba_state.json",
    "WNBA":   "wnba_state.json",
    "NHL":    "nhl_state.json",
    "SOCCER": "soccer_state.json",
    "TENNIS": "tennis_state.json",
    "GOLF":   "golf_state.json",
    "UFC":    None,
    "F1":     None,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _count_strong_in(d) -> int:
    """Count strong_edges entries in any of the expected output keys."""
    for k in ("strong_edges", "strong_2plus_edges", "strong_3plus_edges"):
        if isinstance(d.get(k), list):
            return len(d[k])
    return 0


def _count_rows(d) -> int:
    """Count total projection rows from any of the expected keys."""
    for k in ("rows", "top_25_by_p_hit", "top_25_by_p_hr", "top_25_by_xTB",
              "top_25_by_xXBH", "top_25_by_p_scores", "top_25_by_xHRR",
              "all_edges", "ml_edges"):
        if isinstance(d.get(k), list):
            return len(d[k])
    # Single-entry summary modules
    for k in ("n_batters", "n_pitchers", "n_players_projected", "n_games",
              "n_matches", "n_team_projections", "n_goalies"):
        if d.get(k) is not None:
            return int(d[k])
    return 0


def run() -> Dict[str, Any]:
    sports = []
    total_games = 0
    total_strong = 0

    for sport, files in SPORT_MAP:
        state_file = SPORT_STATE.get(sport)
        n_games = 0
        if state_file:
            state = _load(os.path.join(DATA_DIR, state_file))
            games = state.get("games") or state.get("events") or state.get("matches") or []
            n_games = len(games) if isinstance(games, list) else 0

        n_modules = 0
        n_modules_active = 0
        n_total_rows = 0
        n_strong = 0

        for fname in files:
            n_modules += 1
            d = _load(os.path.join(DATA_DIR, fname))
            if not d: continue
            rows = _count_rows(d)
            strong = _count_strong_in(d)
            if rows > 0 or strong > 0:
                n_modules_active += 1
            n_total_rows += rows
            n_strong += strong

        sports.append({
            "sport": sport,
            "n_games_today": n_games,
            "n_prop_modules": n_modules,
            "n_modules_active_tonight": n_modules_active,
            "n_total_projections": n_total_rows,
            "n_strong_edges": n_strong,
        })
        total_games += n_games
        total_strong += n_strong

    sports.sort(key=lambda s: -s["n_strong_edges"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "totals": {
            "n_games_all_sports": total_games,
            "n_strong_edges_all_sports": total_strong,
        },
        "sports": sports,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[sport-coverage] {o['totals']['n_games_all_sports']} games, "
          f"{o['totals']['n_strong_edges_all_sports']} strong edges across sports -> {OUT}")
    for s in o['sports']:
        print(f"  {s['sport']:6s}: {s['n_games_today']:3d} games · "
              f"{s['n_modules_active_tonight']:2d}/{s['n_prop_modules']:2d} modules · "
              f"{s['n_total_projections']:4d} projections · {s['n_strong_edges']:3d} strong")
