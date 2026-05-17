"""
EdgeStat -- pipeline freshness audit.

THE source-of-truth check that every JSON artifact the front-end consumes
is (a) present, (b) non-empty, and (c) recent. Writes a comprehensive
report to data/pipeline_audit.json. Run this LAST in the daily pipeline
so it captures the final state.

If the report shows any RED items, the pipeline has a real problem and
the front-end will silently degrade.

Output: data/pipeline_audit.json
  {
    "generated_at": "...",
    "overall": "green" | "yellow" | "red",
    "n_green": 42, "n_yellow": 3, "n_red": 0,
    "artifacts": [
      { name, path, exists, size_bytes, age_minutes, status,
        expected_cadence_mins, finding }
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "pipeline_audit.json")


# Every artifact we surface on the front-end, with its expected refresh
# cadence in minutes. (-1 = no expected cadence, just track existence.)
ARTIFACTS: List[Dict[str, Any]] = [
    # Core slate (daily 3x)
    {"name": "today.json",                "cadence_mins":  8*60},
    {"name": "matchups.json",             "cadence_mins":  8*60},
    {"name": "props.json",                "cadence_mins":  8*60},
    {"name": "pickem.json",               "cadence_mins":  8*60},
    {"name": "parlays.json",              "cadence_mins":  8*60},
    {"name": "sgps.json",                 "cadence_mins":  8*60},
    # Calibration loop
    {"name": "calibration_live.json",     "cadence_mins":  8*60},
    {"name": "model_confidence.json",     "cadence_mins":  8*60},
    {"name": "track_record.json",         "cadence_mins": 24*60},
    {"name": "residuals.json",            "cadence_mins":  8*60},
    {"name": "anomalies.json",            "cadence_mins":  8*60},
    {"name": "drift.json",                "cadence_mins":  8*60},
    {"name": "walk_forward.json",         "cadence_mins":  8*60},
    {"name": "perf_trend.json",           "cadence_mins":  8*60},
    {"name": "player_bias.json",          "cadence_mins":  8*60},
    # Player intel
    {"name": "player_gamelogs.json",      "cadence_mins": 24*60},
    {"name": "player_breakdowns.json",    "cadence_mins": 24*60},
    {"name": "rationales.json",           "cadence_mins":  8*60},
    # Best-bet aggregators
    {"name": "best_bets.json",            "cadence_mins":  8*60},
    {"name": "portfolio.json",            "cadence_mins":  8*60},
    {"name": "bankroll_sim.json",         "cadence_mins":  8*60},
    {"name": "sharpe_rankings.json",      "cadence_mins":  8*60},
    # Slate context
    {"name": "slate_confidence.json",     "cadence_mins":  8*60},
    {"name": "pitcher_fatigue.json",      "cadence_mins":  8*60},
    {"name": "weather_conditional.json",  "cadence_mins":  8*60},
    {"name": "bullpen_alert.json",        "cadence_mins":  8*60},
    {"name": "bullpen_workload.json",     "cadence_mins": 24*60},
    {"name": "hot_streaks.json",          "cadence_mins":  8*60},
    {"name": "cross_book_arb.json",       "cadence_mins":  8*60},
    {"name": "velocity_decay.json",       "cadence_mins": 24*60},
    {"name": "line_timing.json",          "cadence_mins":  8*60},
    {"name": "lineup_churn.json",         "cadence_mins":  15},
    # NRFI / F5 / RL
    {"name": "nrfi.json",                 "cadence_mins":  8*60},
    {"name": "first_five.json",           "cadence_mins":  8*60},
    {"name": "run_line.json",             "cadence_mins":  8*60},
    {"name": "best_matchups.json",        "cadence_mins":  8*60},
    {"name": "team_form.json",            "cadence_mins": 24*60},
    {"name": "pitch_matchup.json",        "cadence_mins":  8*60},
    {"name": "lineup_quality.json",       "cadence_mins":  8*60},
    {"name": "injuries_live.json",        "cadence_mins":  8*60},
    {"name": "travel.json",               "cadence_mins":  8*60},
    {"name": "pythagorean.json",          "cadence_mins": 24*60},
    {"name": "transactions.json",         "cadence_mins": 24*60},
    {"name": "batter_form.json",          "cadence_mins":  8*60},
    {"name": "research_depth.json",       "cadence_mins":  8*60},
    {"name": "series_context.json",       "cadence_mins":  8*60},
    {"name": "pitcher_rest.json",         "cadence_mins":  8*60},
    {"name": "top_plays.json",            "cadence_mins":  8*60},
    {"name": "clv_log.json",              "cadence_mins":  15},
    {"name": "clv_per_bet.json",          "cadence_mins": 24*60},
    {"name": "dow_pl.json",               "cadence_mins": 24*60},
    {"name": "daily_summary.md",          "cadence_mins":  8*60},
    {"name": "picks_today.csv",           "cadence_mins":  8*60},
    # Live (every 10 min)
    {"name": "live_state.json",           "cadence_mins":  20},
    {"name": "live_clv.json",             "cadence_mins":  20},
    {"name": "live_edges.json",           "cadence_mins":  20},
    {"name": "live_props.json",           "cadence_mins":  20},
    {"name": "k_pace.json",               "cadence_mins":  20, "optional": True},
    # Golf desk (ESPN PGA Tour scoreboard + Monte Carlo win/H2H/makecut/POT)
    {"name": "golf_state.json",           "cadence_mins":  8*60},
    {"name": "golf_props.json",           "cadence_mins":  8*60},
    {"name": "golf_h2h.json",             "cadence_mins":  8*60},
    {"name": "golf_makecut.json",         "cadence_mins":  8*60},
    {"name": "golf_bestbet.json",         "cadence_mins":  8*60},
    {"name": "golf_pot_history.json",     "cadence_mins":  8*60},
    {"name": "golf_alerts.json",          "cadence_mins":  8*60, "optional": True},
    {"name": "golf_parlays.json",         "cadence_mins":  8*60},
    # Play-of-Day rolling history (snapshot + settle each cron)
    {"name": "pod_history.json",          "cadence_mins":  8*60},
    # NBA + NHL scoreboards (real, ESPN-driven, runs every 8h daily + every 10min live)
    {"name": "nba_state.json",            "cadence_mins":  8*60},
    {"name": "nhl_state.json",            "cadence_mins":  8*60},
    # KBO (Korean Baseball) full stack
    {"name": "kbo_state.json",            "cadence_mins":  8*60},
    {"name": "kbo_props.json",            "cadence_mins":  8*60},
    {"name": "kbo_elo.json",              "cadence_mins":  8*60},
    {"name": "kbo_bestbet.json",          "cadence_mins":  8*60},
    {"name": "kbo_pot_history.json",      "cadence_mins":  8*60},
    # League of Legends esports full stack
    {"name": "lol_state.json",            "cadence_mins":  8*60},
    {"name": "lol_props.json",            "cadence_mins":  8*60},
    {"name": "lol_elo.json",              "cadence_mins":  8*60},
    {"name": "lol_bestbet.json",          "cadence_mins":  8*60},
    {"name": "lol_pot_history.json",      "cadence_mins":  8*60},
    # Counter-Strike (CS2) full stack
    {"name": "cs_state.json",             "cadence_mins":  8*60},
    {"name": "cs_props.json",             "cadence_mins":  8*60},
    {"name": "cs_elo.json",               "cadence_mins":  8*60},
    {"name": "cs_bestbet.json",           "cadence_mins":  8*60},
    {"name": "cs_pot_history.json",       "cadence_mins":  8*60},
    # Self-learning calibration across LoL + CS + KBO
    {"name": "esports_calibration.json",  "cadence_mins":  8*60},
    # Multi-sport top picks aggregator + LoL parlays + CS map handicap
    {"name": "multi_sport_top.json",      "cadence_mins":  8*60},
    {"name": "multi_sport_pot_rollup.json","cadence_mins":  8*60},
    {"name": "lol_parlays.json",          "cadence_mins":  8*60},
    {"name": "cs_maphandicap.json",       "cadence_mins":  8*60},
    {"name": "kbo_pitcher_adj.json",      "cadence_mins":  8*60},
    {"name": "esports_alerts.json",       "cadence_mins":  8*60, "optional": True},
    # Per-sport player detail + projections + prop fair odds
    {"name": "lol_players.json",          "cadence_mins":  8*60},
    {"name": "lol_player_props.json",     "cadence_mins":  8*60},
    {"name": "cs_players.json",           "cadence_mins":  8*60},
    {"name": "cs_player_props.json",      "cadence_mins":  8*60},
    {"name": "kbo_players.json",          "cadence_mins":  8*60},
    {"name": "kbo_player_props.json",     "cadence_mins":  8*60},
    # Cross-sport player POT (scans all 3 sport prop boards)
    {"name": "player_pot.json",           "cadence_mins":  8*60},
    {"name": "player_pot_history.json",   "cadence_mins":  8*60},
    # Extended ESPN sport coverage (10 new sports)
    {"name": "wnba_state.json",           "cadence_mins":  8*60},
    {"name": "mls_state.json",            "cadence_mins":  8*60},
    {"name": "epl_state.json",            "cadence_mins":  8*60},
    {"name": "ucl_state.json",            "cadence_mins":  8*60, "optional": True},
    {"name": "nfl_state.json",            "cadence_mins":  8*60},
    {"name": "ncaaf_state.json",          "cadence_mins":  8*60},
    {"name": "ncaab_state.json",          "cadence_mins":  8*60, "optional": True},
    {"name": "cws_state.json",            "cadence_mins":  8*60},
    {"name": "f1_state.json",             "cadence_mins": 24*60, "optional": True},
    {"name": "ufc_state.json",            "cadence_mins": 24*60, "optional": True},
    # Advanced features
    {"name": "dfs_optimizer.json",        "cadence_mins":  8*60},
    {"name": "picks_export.json",         "cadence_mins":  8*60},
    {"name": "picks_export.csv",          "cadence_mins":  8*60},
    # Optional / stubs (placeholder, real nfl_state above)
    # Loop tracking (from PR #38/#39 -- present only after those merge)
    {"name": "config_snapshot.json",      "cadence_mins":  8*60, "optional": True},
    {"name": "config_history.json",       "cadence_mins":  8*60, "optional": True},
    {"name": "training_feedback.json",    "cadence_mins":  8*60, "optional": True},
    {"name": "training_progress.json",    "cadence_mins":  8*60, "optional": True},
    {"name": "param_recommendations.json","cadence_mins":  8*60, "optional": True},
    {"name": "override_effects.json",     "cadence_mins":  8*60, "optional": True},
    {"name": "recommendation_trust.json", "cadence_mins":  8*60, "optional": True},
    {"name": "learning_curves.json",      "cadence_mins":  8*60, "optional": True},
    {"name": "context_calibration.json",  "cadence_mins":  8*60, "optional": True},
    {"name": "loop_value.json",           "cadence_mins":  8*60, "optional": True},
]


def _classify(path: str, cadence_min: int, optional: bool) -> Dict[str, Any]:
    """Inspect one file. Returns status + finding."""
    if not os.path.exists(path):
        if optional:
            return {"exists": False, "size_bytes": 0, "age_minutes": None,
                    "status": "yellow",
                    "finding": "OPTIONAL: file not present (feature may be on unmerged PR)"}
        return {"exists": False, "size_bytes": 0, "age_minutes": None,
                "status": "red",
                "finding": "MISSING: file does not exist (pipeline step never ran or failed)"}
    size = os.path.getsize(path)
    if size == 0:
        return {"exists": True, "size_bytes": 0, "age_minutes": 0,
                "status": "red",
                "finding": "EMPTY: file exists but 0 bytes"}
    if size < 50:
        return {"exists": True, "size_bytes": size, "age_minutes": 0,
                "status": "yellow",
                "finding": f"TINY: only {size} bytes — likely empty dict / no data this slate"}
    mtime = os.path.getmtime(path)
    age_min = round((dt.datetime.now().timestamp() - mtime) / 60)
    # Status:
    #   green if age < 2 * cadence_min
    #   yellow if 2-4 * cadence_min
    #   red if > 4 * cadence_min
    if age_min < cadence_min * 2:
        return {"exists": True, "size_bytes": size, "age_minutes": age_min,
                "status": "green", "finding": "fresh"}
    if age_min < cadence_min * 4:
        return {"exists": True, "size_bytes": size, "age_minutes": age_min,
                "status": "yellow",
                "finding": f"STALE: last refreshed {age_min} min ago (expected every {cadence_min} min)"}
    return {"exists": True, "size_bytes": size, "age_minutes": age_min,
            "status": "red",
            "finding": f"VERY STALE: last refreshed {age_min} min ago (expected every {cadence_min} min)"}


def run() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    counts = {"green": 0, "yellow": 0, "red": 0}
    for art in ARTIFACTS:
        name = art["name"]
        cadence = art["cadence_mins"]
        optional = art.get("optional", False)
        path = os.path.join(DATA_DIR, name)
        info = _classify(path, cadence, optional)
        counts[info["status"]] += 1
        rows.append({"name": name, "path": f"data/{name}",
                      "expected_cadence_mins": cadence,
                      "optional": optional, **info})
    # Sort: red first, then yellow, then green (within each, by age desc)
    status_order = {"red": 0, "yellow": 1, "green": 2}
    rows.sort(key=lambda r: (status_order[r["status"]], -(r["age_minutes"] or 0)))

    if counts["red"] > 0:
        overall = "red"
    elif counts["yellow"] > 5:
        overall = "yellow"
    elif counts["yellow"] > 0:
        overall = "yellow"
    else:
        overall = "green"

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "n_green": counts["green"],
        "n_yellow": counts["yellow"],
        "n_red": counts["red"],
        "total_tracked": len(rows),
        "artifacts": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Overall: {p['overall'].upper()}")
    print(f"  green={p['n_green']}  yellow={p['n_yellow']}  red={p['n_red']}")
    if p["n_red"] > 0 or p["n_yellow"] > 0:
        print("  Problems:")
        for r in p["artifacts"]:
            if r["status"] in ("red", "yellow"):
                opt = " (optional)" if r.get("optional") else ""
                print(f"    [{r['status'].upper():6}] {r['name']:30}{opt} -- {r['finding']}")
