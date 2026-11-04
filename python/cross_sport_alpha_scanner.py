"""
EdgeStat -- Cross-sport alpha scanner.

Scans ALL prop modules across all sports and surfaces:
  1. PURE_ALPHA  - picks where model edge > 10% AND raw probability falls in
                   the "value zone" (avoids -700 favorites and +500 longshots)
  2. CORRELATED_DOUBLE  - same-game correlated picks (e.g. starter K_OVER +
                          opp_TT_UNDER) where one signal validates the other
  3. CONFLUENCE_TRIPLE  - three or more independent signals on same player
                          (e.g. HR_YES + TB_OVER + 2_HITS_YES)

This is the "spider that crawls every prop output" to surface the
HIGHEST-ROI plays of the slate.

Output: data/cross_sport_alpha_scanner.json
"""
from __future__ import annotations

import os
import json
import glob
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "cross_sport_alpha_scanner.json")


# Modules to crawl + the row-list key + identifier fields
# (filename, list_key, player_or_team_field, market_key)
PROP_FILES = [
    # MLB batter
    ("mlb_batter_2plus_hits_props.json",  "top_25_by_p_2plus", "batter", "HITS_2PLUS"),
    ("mlb_batter_rbi_props.json",          "top_25_by_p_rbi",  "batter", "RBI_1PLUS"),
    ("mlb_to_hit_hr_yn.json",              "top_25_by_p_hr",   "batter", "HR_YES"),
    ("mlb_total_bases_props.json",         "top_25_by_xTB",    "batter", "TB"),
    ("mlb_batter_3plus_tb_props.json",     "top_25_by_p_tb3",  "batter", "TB_3PLUS"),
    ("mlb_doubles_props.json",             "rows",             "batter", "XBH"),
    ("mlb_to_record_hit_yn.json",          "top_25_by_p_hit",  "batter", "HIT_1PLUS"),
    ("mlb_to_score_run_yn.json",           "top_25_by_p_scores", "batter", "RUN_SCORE"),
    ("mlb_hrr_props.json",                 "top_25_by_xHRR",   "batter", "HRR"),
    # MLB pitcher
    ("mlb_pitcher_strikeouts_props.json",  "rows",             "pitcher", "K"),
    ("mlb_pitcher_outs_props.json",        "rows",             "pitcher", "OUTS"),
    ("mlb_pitcher_quality_start_props.json","top_25_by_p_qs",  "pitcher", "QS"),
    ("mlb_pitcher_1st_inning_er.json",     "rows",             "pitcher", "1ST_INN_ER"),
    # NBA
    ("nba_player_points_props.json",       "rows",             "player",  "PTS"),
    ("nba_player_assists_props.json",      "rows",             "player",  "AST"),
    ("nba_player_rebounds_props.json",     "rows",             "player",  "REB"),
    ("nba_player_threes_props.json",       "rows",             "player",  "THREES"),
    ("nba_player_pra_props.json",          "rows",             "player",  "PRA"),
    ("nba_player_pr_combo_props.json",     "top_15_by_pr",     "player",  "PR_COMBO"),
    ("nba_player_pa_combo_props.json",     "top_15_by_pa",     "player",  "PA_COMBO"),
    # NHL
    ("nhl_anytime_goal_props.json",        "rows",             "player",  "GOAL"),
    ("nhl_skater_sog_props.json",          "rows",             "player",  "SOG"),
    ("nhl_skater_points_props.json",       "rows",             "player",  "PTS"),
    ("nhl_skater_2plus_points.json",       "top_25_by_p_2plus","player",  "PTS_2PLUS"),
    ("nhl_skater_2plus_goals.json",        "top_15_by_p_2plus","player",  "GOAL_2PLUS"),
    # WNBA
    ("wnba_player_pts_props.json",         "rows",             "player",  "PTS"),
    ("wnba_player_double_double.json",     "rows",             "player",  "DD"),
    # Soccer
    ("soccer_goalscorer_props.json",       "rows",             "player",  "GOAL"),
    # Tennis
    ("tennis_match_win_props.json",        "rows",             "player",  "MATCH_WIN"),
    ("tennis_aces_props.json",             "rows",             "player",  "ACES"),
    # UFC
    ("ufc_strikes_takedowns_props.json",   "rows",             "fighter", "STRIKES_TKD"),
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


PROJECTION_LABEL = "unvalidated model projection — no sportsbook price, not a recommendation"


def _is_fallback(row: Dict[str, Any]) -> bool:
    """(2026-11-03) A row whose stat source is "fallback" was projected from the
    hard-coded 2024-25 PLAYER_DB (stale averages AND teams), not real data."""
    return any(k.endswith("_source") and str(v).lower() == "fallback" for k, v in row.items())


def _identify_pick(row: Dict[str, Any]) -> Dict[str, Any]:
    """Extract a normalized projection descriptor from a prop row.

    (2026-11-03) No "alpha"/"STRONG" label and no edge: the modules' "STRONG =
    10%+ edge vs -120 book" compares the model to an ASSUMED -120 price. No
    sportsbook prop price exists in the free feeds, so edge is None."""
    best = row.get("best_market") or {}
    if not best:
        return {}
    return {
        "p": _safe(best.get("p")),
        "market": best.get("market"),
        "edge": None,
        "book_price": None,
        "label": PROJECTION_LABEL,
    }


def run() -> Dict[str, Any]:
    pure_alpha: List[Dict[str, Any]] = []      # (2026-11-03) = projections; key kept for consumers
    by_player: Dict[str, List[Dict[str, Any]]] = {}
    n_fallback = 0

    for filename, list_key, ident_field, market_label in PROP_FILES:
        d = _load(os.path.join(DATA_DIR, filename))
        rows = d.get(list_key) or d.get("rows") or d.get("strong_edges") or []
        if not isinstance(rows, list): continue
        for r in rows:
            if not isinstance(r, dict): continue
            ident = (r.get(ident_field) or r.get("name") or r.get("player")
                     or r.get("batter") or r.get("pitcher") or "").strip()
            if not ident: continue
            if _is_fallback(r):                      # (2026-11-03) hard-coded 2024-25 table
                n_fallback += 1
                continue
            pick = _identify_pick(r)
            if not pick: continue
            if not pick.get("p") or not pick.get("market"): continue

            # Value zone gate: keep picks with p between 25% and 80% (avoid extreme heavies/longshots)
            p_val = pick["p"]
            if p_val < 0.25 or p_val > 0.80:
                continue

            pick_entry = {
                "player": ident,
                "matchup": r.get("matchup") or "",
                "game_date": r.get("game_date") or r.get("date"),
                "source_module": filename.replace(".json", ""),
                "market_label": market_label,
                **pick,
            }
            pure_alpha.append(pick_entry)
            by_player.setdefault(ident.lower(), []).append(pick_entry)

    # Find correlated doubles (same game, 2+ STRONG picks on related markets)
    correlated_doubles: List[Dict[str, Any]] = []
    by_matchup: Dict[str, List[Dict[str, Any]]] = {}
    for pick in pure_alpha:
        m = pick.get("matchup") or ""
        if m: by_matchup.setdefault(m, []).append(pick)

    for matchup, picks in by_matchup.items():
        # Only flag if 2+ STRONG picks on a single matchup
        if len(picks) >= 2:
            correlated_doubles.append({
                "matchup": matchup,
                "n_picks": len(picks),
                "picks": picks,
            })

    # Find confluence triples (same player, 3+ STRONG markets)
    confluence_triples: List[Dict[str, Any]] = []
    for player, picks in by_player.items():
        if len(picks) >= 3:
            confluence_triples.append({
                "player": picks[0]["player"],
                "n_signals": len(picks),
                "matchup": picks[0].get("matchup"),
                "signals": picks,
            })

    # Sort by signal count
    correlated_doubles.sort(key=lambda r: -r["n_picks"])
    confluence_triples.sort(key=lambda r: -r["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pure_alpha_picks": len(pure_alpha),
        "n_correlated_matchups": len(correlated_doubles),
        "n_confluence_triples": len(confluence_triples),
        "n_excluded_fallback": n_fallback,
        "status": "unvalidated_model_projection",
        "label": PROJECTION_LABEL,
        "method_note": f"(2026-11-03) Crawls {len(PROP_FILES)} prop output files; keeps each row's best "
                       "model market with p in [25%, 80%]. UNVALIDATED MODEL PROJECTIONS: no sportsbook "
                       "price exists for these props, so there is no edge (the modules' 'STRONG = 10%+ vs "
                       "-120' compared to an assumed price and is not used). Rows projected from the "
                       "hard-coded 2024-25 table (source 'fallback') are excluded. correlated_doubles = "
                       "2+ projections in one game; confluence_triples = 3+ projections on one player "
                       "(same model, not independent agreement).",
        "top_25_pure_alpha": pure_alpha[:25],
        "correlated_doubles": correlated_doubles[:15],
        "confluence_triples": confluence_triples[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[xs-alpha] {o['n_pure_alpha_picks']} projections ({o['n_excluded_fallback']} fallback excluded), "
          f"{o['n_correlated_matchups']} correlated matchups, "
          f"{o['n_confluence_triples']} confluence triples -> {OUT}")
