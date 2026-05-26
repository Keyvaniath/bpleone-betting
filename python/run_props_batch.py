"""
EdgeStat -- batched prop-module runner.

Each prop module has ~250ms of Python startup overhead. With 60+ modules
running sequentially as `python xxx.py`, that's 15+ seconds of pure startup
per daily-pipeline run.

This batched runner imports all modules ONCE and calls each module.run()
in-process. Shares Python startup + JSON file caches across modules.

Failure isolation: any module that raises during import or run() is logged
and the batch continues. Mimics the `|| true` shell behavior in the YAML.

Reports per-module timing on stdout.

Usage:
  python run_props_batch.py            # run all default modules
  python run_props_batch.py module1 module2  # run subset

Output: data/run_props_batch_report.json
"""
from __future__ import annotations

import os
import sys
import json
import time
import traceback
import datetime as dt
from typing import Any, Dict, List


HERE = os.path.dirname(__file__)
DATA_DIR = os.path.join(HERE, "..", "data")
REPORT = os.path.join(DATA_DIR, "run_props_batch_report.json")

# Pure-projection modules that:
#   - export run() function
#   - take no required args
#   - read JSON from DATA_DIR and write JSON to DATA_DIR
#   - do not need network access (no os.environ secrets)
DEFAULT_MODULES = [
    # MLB batter props
    "mlb_doubles_props",
    "mlb_hrr_props",
    "mlb_total_bases_props",
    "mlb_to_record_hit_yn",
    "mlb_to_score_run_yn",
    "mlb_first_inning_hr_yn",
    "mlb_team_first_inning_run",
    "mlb_team_first_3_innings_runs",
    "mlb_first_team_to_score",
    "mlb_game_first_inning_hit_yn",
    "mlb_total_HRs_game",
    "mlb_to_hit_hr_yn",
    "mlb_first_batter_retired_props",
    "mlb_batter_walks_props",
    "mlb_batter_rbi_props",
    "mlb_batter_2plus_hits_props",
    "mlb_batter_3plus_tb_props",
    "mlb_batter_strikeout_props",
    # MLB pitcher props
    "mlb_pitcher_walks_props",
    "mlb_pitcher_2plus_walks_yn",
    "mlb_total_walks_game",
    "mlb_total_K_game",
    "mlb_pitcher_k_minus_bb",
    "mlb_pitcher_outs_props",
    "mlb_pitcher_6plus_IP_yn",
    "mlb_pitcher_pitches_into_6th",
    "mlb_pitcher_er_props",
    "mlb_pitcher_blowup_alert",
    "mlb_pitcher_hits_allowed_props",
    "mlb_pitcher_allows_hr_yn",
    "mlb_pitcher_quality_start_props",
    "mlb_pitcher_strikeouts_props",
    "mlb_pitcher_9plus_K_alt",
    "mlb_pitcher_rest_advantage",
    "mlb_pitcher_win_props",
    "mlb_pitcher_1st_inning_er",
    "mlb_pitcher_1st_inning_k",
    "mlb_run_line_props",
    "mlb_hbp_props",
    # MLB context features (run BEFORE other props so they can consume)
    "mlb_lineup_quality_index",
    "mlb_bullpen_fatigue_index",
    "mlb_starter_pitch_count_alerts",
    "mlb_pitcher_form_tracker",
    "mlb_park_weather_hr_index",
    "mlb_weather_advisory",
    "mlb_platoon_matrix",
    "mlb_closer_availability_tracker",
    "mlb_closer_to_record_save",
    # MLB game props
    "mlb_first5_market",
    # MLB deep composites (depend on lineup_quality + per-pitcher props above)
    # Note: must run AFTER mlb_pitcher_strikeouts_props etc, but those are below
    # so we duplicate here LAST (idempotent re-run picks up fresh data)
    "mlb_steal_props",
    "mlb_team_sb_total_props",
    "mlb_innings_1_3_totals",
    "mlb_innings_4_6_totals",
    "mlb_innings_7_9_totals",
    "mlb_extra_innings_prop",
    # NBA player props
    "nba_player_points_props",
    "nba_player_30plus_pts_alt",
    "nba_player_assists_props",
    "nba_player_assists_alt_props",
    "nba_player_rebounds_props",
    "nba_player_rebounds_alt_props",
    "nba_player_threes_props",
    "nba_player_threes_alt_props",
    "nba_player_blocks_steals_props",
    "nba_player_blocks_alt",
    "nba_double_double_props",
    "nba_player_turnovers_props",
    "nba_player_turnovers_alt",
    "nba_player_pra_props",
    "nba_player_pr_combo_props",
    "nba_player_pa_combo_props",
    "nba_player_ra_combo_props",
    "nba_player_ft_attempts_props",
    "nba_triple_double_props",
    "nba_player_minutes_props",
    # NBA team props
    "nba_team_alts_props",
    "nba_pace_adjusted",
    "nba_team_total_props",
    "nba_team_total_edge",
    "nba_race_to_points",
    "nba_game_total_alts",
    "nba_half_total_props",
    # WNBA props
    "wnba_player_pts_props",
    "wnba_player_20plus_pts_alt",
    "wnba_player_reb_ast_props",
    "wnba_player_threes_props",
    "wnba_player_blocks_steals_props",
    "wnba_player_double_double",
    "wnba_team_alts_props",
    # NHL props
    "nhl_skater_hits_blocks_props",
    "nhl_skater_3plus_hits",
    "nhl_skater_4plus_hits",
    "nhl_skater_blocks_alt",
    "nhl_period_totals_props",
    "nhl_goalie_saves_props",
    "nhl_goalie_30plus_saves",
    "nhl_game_total_saves",
    "nhl_game_total_sog",
    "nhl_anytime_goal_props",
    "nhl_skater_sog_props",
    "nhl_skater_3plus_sog",
    "nhl_skater_4plus_sog",
    "nhl_skater_6plus_sog",
    "nhl_skater_points_props",
    "nhl_skater_2plus_points",
    "nhl_skater_2plus_goals",
    "nhl_goalie_shutout_props",
    "nhl_first_goalscorer_props",
    "nhl_goalie_win_props",
    "nhl_goalie_fatigue_index",
    "nhl_puck_line_props",
    "nhl_team_total_edge",
    "nhl_team_4plus_goals",
    # Soccer props
    "soccer_corners_props",
    "soccer_btts_props",
    "soccer_total_goals_props",
    "soccer_first_to_score_props",
    "soccer_team_score_1h",
    "soccer_clean_sheet_props",
    "soccer_goalscorer_props",
    "soccer_goalscorer_2plus",
    "soccer_cards_props",
    "soccer_total_shots_props",
    "soccer_player_shots_props",
    # Tennis props
    "tennis_match_win_props",
    "tennis_total_games_props",
    "tennis_set_score_props",
    "tennis_aces_props",
    "tennis_double_faults_props",
    "tennis_breaks_of_serve",
    "tennis_1st_set_winner",
    # Golf props (top-finish, etc.)
    "golf_top_finish_props",
    "golf_leaderboard_probability",
    "golf_round_score_props",
    # UFC props
    "ufc_strikes_takedowns_props",
    "ufc_rounds_over_under_props",
    "ufc_first_round_finish",
    # F1 props
    "f1_qualifying_predictor",
    "f1_podium_finish_props",
    # Pitcher edge composite (consumes lineup_quality + K/outs/QS props above)
    "mlb_pitcher_edge_composite",
    "mlb_pitcher_recent_vs_lineup_quality",
    # Team total edge synthesizer (consumes lineup_quality + pitcher_edge above)
    "mlb_team_total_edge",
    "mlb_team_5plus_runs",
    "mlb_race_to_3_runs",
    "mlb_game_total_alt_props",
    "mlb_game_run_diff_props",
    "mlb_ml_edge_synthesizer",
    "mlb_inning_probability_matrix",
    # MLB stack builder (consumes lineup_quality + park + pitcher_edge + hot_streaks)
    "mlb_stack_builder",
    # Today's alerts (consumes ALL MLB context features above)
    "mlb_todays_alerts_synthesizer",
    "mlb_today_lean_consensus",
    # Top-edge aggregators (consume per-prop module outputs)
    "mlb_today_top_pitcher_props",
    "mlb_today_top_batter_props",
    "mlb_perfect_storm_alerts",
    "mlb_today_game_grid",
    "mlb_today_master_brief",
    # Cross-sport alpha scanner (runs AFTER all per-sport props above)
    "cross_sport_alpha_scanner",
    "mlb_today_whales",
    "mlb_today_locks",
    "mlb_top_3_picks_synthesizer",
    # Confluence + aggregation (must run AFTER all per-sport props above)
    "confluence_top_5",
    # book_vs_model_team runs FIRST so alpha_pick can pull from its output
    "book_vs_model_team",
    "alpha_pick_of_day",
    "fade_picks",
    # top_calibrated_edges depends on book_vs_model_team + todays_top_plays
    "top_calibrated_edges",
    # bet_slate consolidates POD + ALPHA + BOOK + PARLAY into single JSON
    "bet_slate",
    # markdown export consumes bet_slate.json
    "slate_markdown_export",
    # sport coverage runs last after all other outputs are written
    "sport_coverage",
    # Data-integrity audit (runs LAST so it scans the freshly-written outputs)
    "data_integrity_audit",
    "data_freshness_audit",
    "global_pick_counts_widget",
]


def main(modules: List[str]) -> Dict[str, Any]:
    # Ensure DATA_DIR exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # Allow imports from this directory (in case we're called from a parent dir)
    if HERE not in sys.path:
        sys.path.insert(0, HERE)

    results: List[Dict[str, Any]] = []
    total_start = time.time()

    for name in modules:
        entry = {"module": name, "status": "pending", "elapsed_ms": None, "error": None}
        t0 = time.time()
        try:
            # Import (cached after first time across the process)
            mod = __import__(name)
            # Call run() if defined
            if hasattr(mod, "run"):
                mod.run()
                entry["status"] = "ok"
            else:
                entry["status"] = "no_run_function"
        except Exception as e:
            entry["status"] = "error"
            entry["error"] = f"{type(e).__name__}: {e}"
            # Print short traceback to stderr so CI logs preserve it
            print(f"[batch] ERROR in {name}: {e}", file=sys.stderr)
            traceback.print_exc(limit=3, file=sys.stderr)
        finally:
            entry["elapsed_ms"] = int((time.time() - t0) * 1000)
            results.append(entry)
            print(f"[batch] {entry['status']:5s} {entry['elapsed_ms']:5d}ms  {name}")

    total_ms = int((time.time() - total_start) * 1000)
    ok = sum(1 for r in results if r["status"] == "ok")
    err = sum(1 for r in results if r["status"] == "error")
    noop = sum(1 for r in results if r["status"] == "no_run_function")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "total_modules": len(results),
        "ok": ok,
        "errors": err,
        "no_run_function": noop,
        "total_elapsed_ms": total_ms,
        "results": results,
    }
    try:
        with open(REPORT, "w") as f:
            json.dump(out, f, indent=2)
    except Exception as e:
        print(f"[batch] WARN: failed to write report: {e}", file=sys.stderr)

    print(f"\n[batch] {ok} ok / {err} errors / {noop} no-run in {total_ms}ms total")
    return out


if __name__ == "__main__":
    modules = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_MODULES
    main(modules)
