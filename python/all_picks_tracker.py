"""
EdgeStat -- UNIFIED pick tracker for ALL surfaced picks.

Every pick the model surfaces (locks, whales, consensus, sharp, unders,
POD) goes into one append-only ledger. Each pick gets:
   permanent pick_id (deterministic: source|player|market|date)
   recorded probability + edge (raw + calibrated)
   source tag (which module surfaced it)
   settlement status + actual outcome
   payout in units (1u flat)

This is the TRAINING ground truth: every settled outcome feeds back
into per-source accuracy stats, calibration shrinkage, and module-
level reliability scores. Without this, the model can't learn.

Output: data/all_picks_ledger.json
   {
     totals, n_settled, n_pending,
     wins, losses, pushes, hit_rate, net_units, roi_pct,
     by_source: { source_name: {n, wins, losses, hit_rate, net_units} },
     by_market_family: { ... },
     by_sport: { ... },
     last_7_days: {...},
     picks: [ all picks with full details ]
   }
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "all_picks_ledger.json")
MAX_PICKS = 10000


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _today_date_str() -> str:
    return dt.date.today().isoformat()


def _safe_id(s):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(s or "?"))[:40]


def _pick_id(source, sport, player_or_matchup, market, date_str):
    return f"{_safe_id(source)}|{_safe_id(sport)}|{_safe_id(player_or_matchup)}|{_safe_id(market)}|{date_str}"


def _market_family(market):
    if not market: return "unknown"
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", str(market))
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m.lower() or "unknown"


def _american_to_decimal(a):
    if a is None or not isinstance(a, (int, float)): return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _collect_picks_from_sources() -> List[Dict[str, Any]]:
    """Pull picks from every surfacing module today and normalize."""
    date_str = _today_date_str()
    out = []

    # Today's Top Plays (top_25) -- the master board
    top = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    for p in (top.get("top_25") or []):
        out.append({
            "source": "top_25_board",
            "sport": p.get("sport"),
            "player_or_matchup": p.get("player_or_matchup"),
            "market": p.get("market"),
            "prob": p.get("prob"),
            "raw_prob": p.get("raw_prob"),
            "edge_pct": p.get("edge_pct"),
            "fair_american": p.get("fair_american"),
            "primary_source_module": p.get("source"),
        })

    # Whales
    whales = _load(os.path.join(DATA_DIR, "whale_picks.json"))
    for w in (whales.get("whales") or []):
        if w.get("tier") in ("WHALE", "STRONG"):
            out.append({
                "source": f"whale_{w.get('tier','?').lower()}",
                "sport": w.get("sport"),
                "player_or_matchup": w.get("player_or_matchup"),
                "market": w.get("market"),
                "prob": w.get("prob"),
                "edge_pct": w.get("edge_pct"),
                "fair_american": w.get("fair_american"),
                "tier": w.get("tier"),
                "confluence_score": w.get("confluence_score"),
            })

    # Consensus picks (multi-module agreement)
    consensus = _load(os.path.join(DATA_DIR, "consensus_picks.json"))
    for c in (consensus.get("top_15_hit_boost_consensus") or []):
        if c.get("tier") in ("ELITE", "STRONG"):
            out.append({
                "source": f"consensus_hit_{c.get('tier','?').lower()}",
                "sport": "MLB",
                "player_or_matchup": c.get("batter"),
                "market": "1_plus_hit",
                "prob": None,   # consensus doesn't have unified prob -- it's the agreement that matters
                "tier": c.get("tier"),
                "n_agreeing": c.get("n_agreeing"),
            })
    for c in (consensus.get("top_15_hr_boost_consensus") or []):
        if c.get("tier") in ("ELITE", "STRONG"):
            out.append({
                "source": f"consensus_hr_{c.get('tier','?').lower()}",
                "sport": "MLB",
                "player_or_matchup": c.get("batter"),
                "market": "1_plus_hr",
                "prob": None,
                "tier": c.get("tier"),
                "n_agreeing": c.get("n_agreeing"),
            })

    # Strong unders
    unders = _load(os.path.join(DATA_DIR, "mlb_unders_alerts.json"))
    for u in (unders.get("strong_unders") or []):
        market_total = u.get("market_total")
        out.append({
            "source": "mlb_under_alert",
            "sport": "MLB",
            "player_or_matchup": u.get("matchup"),
            "market": f"UNDER_{market_total}" if market_total else "UNDER",
            "prob": None,   # signal score, not prob
            "tier": u.get("tier"),
            "under_signal_score": u.get("under_signal_score"),
        })

    # Sharp action (positive signals only -- model + market agree)
    sharp = _load(os.path.join(DATA_DIR, "sharp_action_radar.json"))
    for s in (sharp.get("positive_signals") or []):
        if s.get("intensity") in ("STRONG", "ELITE"):
            out.append({
                "source": f"sharp_{s.get('intensity','?').lower()}",
                "sport": "MLB",
                "player_or_matchup": s.get("matchup"),
                "market": s.get("market"),
                "prob": s.get("model_prob"),
                "edge_pct": s.get("model_edge_pct"),
                "tier": s.get("intensity"),
                "shift_pp": s.get("shift_pp"),
            })

    # 5 daily locks
    locks_today = _load(os.path.join(DATA_DIR, "locks_history.json"))
    for L in (locks_today.get("todays_locks") or []):
        out.append({
            "source": "lock_of_day",
            "sport": L.get("sport"),
            "player_or_matchup": L.get("player_or_matchup"),
            "market": L.get("market"),
            "prob": L.get("prob"),
            "edge_pct": L.get("edge_pct"),
            "fair_american": L.get("fair_american"),
        })

    # POD
    pod = _load(os.path.join(DATA_DIR, "pod_pl.json"))
    if pod.get("todays_pod"):
        t = pod["todays_pod"]
        out.append({
            "source": "pod",
            "sport": "MLB",
            "player_or_matchup": t.get("matchup"),
            "market": t.get("label"),
            "prob": t.get("model_prob"),
            "edge_pct": t.get("raw_edge_pct"),
            "fair_american": t.get("market_price"),
        })

    # MLB pitcher Quality Start strong edges
    qs = _load(os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json"))
    for r in (qs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_qs_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB to-score-a-run yes/no strong edges
    run_yn = _load(os.path.join(DATA_DIR, "mlb_to_score_run_yn.json"))
    for r in (run_yn.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_run_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB to-record-a-hit yes/no strong edges
    hit_yn = _load(os.path.join(DATA_DIR, "mlb_to_record_hit_yn.json"))
    for r in (hit_yn.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_hit_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB first inning HR strong edges
    fhr = _load(os.path.join(DATA_DIR, "mlb_first_inning_hr_yn.json"))
    for r in (fhr.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_first_inning_hr_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB Innings 7-9 totals strong edges
    inn79 = _load(os.path.join(DATA_DIR, "mlb_innings_7_9_totals.json"))
    for r in (inn79.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_inn_7_9_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB Innings 4-6 totals strong edges
    inn46 = _load(os.path.join(DATA_DIR, "mlb_innings_4_6_totals.json"))
    for r in (inn46.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_inn_4_6_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB Innings 1-3 totals strong edges
    inn13 = _load(os.path.join(DATA_DIR, "mlb_innings_1_3_totals.json"))
    for r in (inn13.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_inn_1_3_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # F5 (First 5 innings) strong edges
    f5 = _load(os.path.join(DATA_DIR, "mlb_first5_market.json"))
    for r in (f5.get("strong_edges") or []):
        be = r.get("best_edge") or {}
        if be.get("model_p"):
            out.append({
                "source": "mlb_f5",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": (be.get("market") or "").lower(),
                "prob": be.get("model_p"),
                "fair_american": be.get("fair_odds"),
                "p_predicted": be.get("model_p"),  # for Brier
            })

    # UFC strikes/TDs strong edges
    ufc_st = _load(os.path.join(DATA_DIR, "ufc_strikes_takedowns_props.json"))
    for r in (ufc_st.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"ufc_{bm.get('market', '').lower()}",
                "sport": "UFC",
                "player_or_matchup": r.get("fighter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # F1 qualifying strong edges
    fq = _load(os.path.join(DATA_DIR, "f1_qualifying_predictor.json"))
    for r in (fq.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"f1_quali_{bm.get('market', '').lower()}",
                "sport": "F1",
                "player_or_matchup": r.get("driver"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": fq.get("circuit"),
            })

    # Golf top-N finish strong edges
    gtop = _load(os.path.join(DATA_DIR, "golf_top_finish_props.json"))
    for r in (gtop.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"golf_{bm.get('market', '').lower()}",
                "sport": "GOLF",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": gtop.get("tournament"),
            })

    # MLB team SB total strong edges
    tsb = _load(os.path.join(DATA_DIR, "mlb_team_sb_total_props.json"))
    for r in (tsb.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_team_sb_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": f"{r.get('team')} ({r.get('matchup')})",
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB first batter retired strong edges
    fbr = _load(os.path.join(DATA_DIR, "mlb_first_batter_retired_props.json"))
    for r in (fbr.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_first_batter_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB pitcher hits allowed strong edges
    ha = _load(os.path.join(DATA_DIR, "mlb_pitcher_hits_allowed_props.json"))
    for r in (ha.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_h_allowed_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB Pitcher ER props strong edges
    er = _load(os.path.join(DATA_DIR, "mlb_pitcher_er_props.json"))
    for r in (er.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_er_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # WNBA player points strong edges
    wnba_pts = _load(os.path.join(DATA_DIR, "wnba_player_pts_props.json"))
    for r in (wnba_pts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"wnba_pts_{bm.get('market', '').lower()}",
                "sport": "WNBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Soccer goalscorer props strong edges
    gs = _load(os.path.join(DATA_DIR, "soccer_goalscorer_props.json"))
    for r in (gs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_goalscorer_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Soccer cards (yellow + red) strong edges
    cards = _load(os.path.join(DATA_DIR, "soccer_cards_props.json"))
    for r in (cards.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_cards_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Soccer BTTS (Both Teams To Score) strong edges
    btts = _load(os.path.join(DATA_DIR, "soccer_btts_props.json"))
    for r in (btts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_btts_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Soccer corners props strong edges
    sc = _load(os.path.join(DATA_DIR, "soccer_corners_props.json"))
    for r in (sc.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_corners_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # WNBA team alt-totals strong edges
    wnba_alts = _load(os.path.join(DATA_DIR, "wnba_team_alts_props.json"))
    for r in (wnba_alts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"wnba_alts_{bm.get('market', '').lower()}",
                "sport": "WNBA",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # WNBA player REB/AST strong edges
    wnba_ra = _load(os.path.join(DATA_DIR, "wnba_player_reb_ast_props.json"))
    for r in (wnba_ra.get("strong_reb") or []) + (wnba_ra.get("strong_ast") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"wnba_{bm.get('market', '').lower()}",
                "sport": "WNBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA double-double strong edges
    nba_dd = _load(os.path.join(DATA_DIR, "nba_double_double_props.json"))
    for r in (nba_dd.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_dd_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA blocks/steals strong edges
    nba_bs = _load(os.path.join(DATA_DIR, "nba_player_blocks_steals_props.json"))
    for r in (nba_bs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA team alt-totals strong edges
    nba_alts = _load(os.path.join(DATA_DIR, "nba_team_alts_props.json"))
    for r in (nba_alts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_alts_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player 3-pointers strong edges
    nba_3pm = _load(os.path.join(DATA_DIR, "nba_player_threes_props.json"))
    for r in (nba_3pm.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_3pm_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # WNBA player 3-pointers strong edges
    wnba_3pm = _load(os.path.join(DATA_DIR, "wnba_player_threes_props.json"))
    for r in (wnba_3pm.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"wnba_3pm_{bm.get('market', '').lower()}",
                "sport": "WNBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player turnovers strong edges
    nba_tov = _load(os.path.join(DATA_DIR, "nba_player_turnovers_props.json"))
    for r in (nba_tov.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_tov_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB pitcher strikeouts strong edges
    mlb_pk = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    for r in (mlb_pk.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_pk_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL skater SOG strong edges
    nhl_sog = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    for r in (nhl_sog.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_sog_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player PRA combo strong edges
    nba_pra = _load(os.path.join(DATA_DIR, "nba_player_pra_props.json"))
    for r in (nba_pra.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_pra_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL skater points (G+A) strong edges
    nhl_pts = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))
    for r in (nhl_pts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_pts_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player FT attempts strong edges
    nba_fta = _load(os.path.join(DATA_DIR, "nba_player_ft_attempts_props.json"))
    for r in (nba_fta.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_fta_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Soccer total shots strong edges
    soc_shots = _load(os.path.join(DATA_DIR, "soccer_total_shots_props.json"))
    for r in (soc_shots.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_total_shots_{bm.get('market', '').lower()}",
                "sport": "SOCCER",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # WNBA player blocks+steals combo strong edges
    wnba_blkstl = _load(os.path.join(DATA_DIR, "wnba_player_blocks_steals_props.json"))
    for r in (wnba_blkstl.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"wnba_blkstl_{bm.get('market', '').lower()}",
                "sport": "WNBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA team total points strong edges
    nba_tt = _load(os.path.join(DATA_DIR, "nba_team_total_props.json"))
    for r in (nba_tt.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_tt_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": f"{r.get('team')} ({r.get('matchup')})",
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL goalie shutout strong edges
    nhl_so = _load(os.path.join(DATA_DIR, "nhl_goalie_shutout_props.json"))
    for r in (nhl_so.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_shutout_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("goalie"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Tennis match-win strong edges
    tennis_ml = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    for r in (tennis_ml.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"tennis_ml_{bm.get('market', '').lower()}",
                "sport": "TENNIS",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL first-goalscorer strong edges
    nhl_fgs = _load(os.path.join(DATA_DIR, "nhl_first_goalscorer_props.json"))
    for r in (nhl_fgs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_fgs_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Tennis total games strong edges
    tennis_tg = _load(os.path.join(DATA_DIR, "tennis_total_games_props.json"))
    for r in (tennis_tg.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"tennis_games_{bm.get('market', '').lower()}",
                "sport": "TENNIS",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Tennis set-score strong edges
    tennis_ss = _load(os.path.join(DATA_DIR, "tennis_set_score_props.json"))
    for r in (tennis_ss.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"tennis_sets_{bm.get('market', '').lower()}",
                "sport": "TENNIS",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB batter walks strong edges
    mlb_bw = _load(os.path.join(DATA_DIR, "mlb_batter_walks_props.json"))
    for r in (mlb_bw.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_bw_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB batter strikeout strong edges
    mlb_bk = _load(os.path.join(DATA_DIR, "mlb_batter_strikeout_props.json"))
    for r in (mlb_bk.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_bk_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB extra-innings strong edges
    mlb_xi = _load(os.path.join(DATA_DIR, "mlb_extra_innings_prop.json"))
    for r in (mlb_xi.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_extras_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL goalie wins strong edges
    nhl_gw = _load(os.path.join(DATA_DIR, "nhl_goalie_win_props.json"))
    for r in (nhl_gw.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_gwin_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("goalie"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL period totals strong edges
    nhl_pt = _load(os.path.join(DATA_DIR, "nhl_period_totals_props.json"))
    for r in (nhl_pt.get("strong_edges") or []):
        if r.get("p"):
            out.append({
                "source": f"nhl_period_{r.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("matchup"),
                "market": r.get("market"),
                "prob": r.get("p"),
                "fair_american": r.get("fair_odds"),
                "p_predicted": r.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL goalie saves strong edges
    gs = _load(os.path.join(DATA_DIR, "nhl_goalie_saves_props.json"))
    for r in (gs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_goalie_saves_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("goalie"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL anytime goal strong edges
    nhl_goal = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    for r in (nhl_goal.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL skater hits/blocks/PIM strong edges
    nhl_hb = _load(os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json"))
    for r in (nhl_hb.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_skater_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player rebounds strong edges
    nba_reb = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    for r in (nba_reb.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_reb_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player assists strong edges
    nba_ast = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    for r in (nba_ast.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_ast_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA player points strong edges
    nba_pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    for r in (nba_pts.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_pts_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Pitcher walks props strong edges
    walks = _load(os.path.join(DATA_DIR, "mlb_pitcher_walks_props.json"))
    for r in (walks.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_walks_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # Pitcher outs recorded strong edges
    outs_recs = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))
    for r in (outs_recs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_outs_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB Doubles/XBH props strong edges
    db = _load(os.path.join(DATA_DIR, "mlb_doubles_props.json"))
    for r in (db.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_xbh_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # HRR (Hits + Runs + RBI) strong 2+ and 3+ edges
    hrr = _load(os.path.join(DATA_DIR, "mlb_hrr_props.json"))
    for r in (hrr.get("strong_edges") or []):
        market = "3_plus_hrr" if "3_PLUS" in (r.get("edge_class") or "") else "2_plus_hrr"
        prob = r.get("p_3_plus") if market == "3_plus_hrr" else r.get("p_2_plus")
        out.append({
            "source": f"mlb_hrr_{market}",
            "sport": "MLB",
            "player_or_matchup": r.get("batter"),
            "market": market,
            "prob": prob,
            "fair_american": r.get("fair_odds_3_plus") if market == "3_plus_hrr" else r.get("fair_odds_2_plus"),
            "p_predicted": prob,
            "matchup": r.get("matchup"),
        })

    # Total Bases strong 2+ TB edges
    tb = _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json"))
    for r in (tb.get("strong_2plus_edges") or []):
        out.append({
            "source": "mlb_total_bases_2plus",
            "sport": "MLB",
            "player_or_matchup": r.get("batter"),
            "market": "2_plus_total_bases",
            "prob": r.get("p_2_plus"),
            "fair_american": r.get("fair_odds_2_plus"),
            "p_predicted": r.get("p_2_plus"),
            "matchup": r.get("matchup"),
        })

    # Steal props strong edges
    sp = _load(os.path.join(DATA_DIR, "mlb_steal_props.json"))
    for r in (sp.get("strong_edges") or []):
        out.append({
            "source": "mlb_steal_1plus",
            "sport": "MLB",
            "player_or_matchup": r.get("runner"),
            "market": "1_plus_steal",
            "prob": r.get("p_sb_1_plus"),
            "fair_american": r.get("fair_odds_1_plus_yes"),
            "p_predicted": r.get("p_sb_1_plus"),
            "matchup": r.get("matchup"),
        })

    # Reverse Line Movement (strong = book moved >=6pp against public favorite)
    rlm = _load(os.path.join(DATA_DIR, "reverse_line_movement.json"))
    for r in (rlm.get("strong_only") or []):
        out.append({
            "source": "rlm_strong",
            "sport": "MLB",
            "player_or_matchup": r.get("matchup"),
            "market": r.get("pick"),  # "HOME ML" or "AWAY ML"
            "prob": None,  # not a prob-based signal, sharp money following
            "fair_american": r.get("current_odds"),
            "rlm_strength": r.get("rlm_strength"),
            "line_delta_pp": r.get("line_delta_pp"),
        })

    # Stamp all picks with date + ID
    for p in out:
        p["date"] = date_str
        p["pick_id"] = _pick_id(p["source"], p.get("sport"), p.get("player_or_matchup"), p.get("market"), date_str)
        p["settled"] = False
        p["result"] = "pending"
        p["payout_units"] = None

    return out


def _settle_picks(history: List[Dict[str, Any]]) -> int:
    """Try to settle each unsettled pick. Returns count newly settled."""
    n_settled = 0
    # Index outcomes by sport+matchup+date
    historical_mlb = _load(os.path.join(DATA_DIR, "historical_mlb.json")).get("games") or []
    gamelogs = _load(os.path.join(DATA_DIR, "player_gamelogs.json"))
    bpid = gamelogs.get("by_player_id") or {}
    # Index gamelogs by lowercased player name
    by_name = {}
    for pid, prec in bpid.items():
        if isinstance(prec, dict):
            by_name[(prec.get("name") or "").lower()] = prec

    for p in history:
        if p.get("settled"): continue
        # 12-hour cool-off so we don't settle against same-name prior-day game
        try:
            rec_at = dt.datetime.fromisoformat(p.get("recorded_at") or "")
            if (dt.datetime.now() - rec_at).total_seconds() < 12 * 3600: continue
        except Exception:
            continue

        market = (p.get("market") or "").lower()
        result = None
        payout = None
        decimal_odds = _american_to_decimal(p.get("fair_american")) or 1.91

        # Game-level (ML, OVER, UNDER)
        if any(k in market for k in ("ml_home", "ml_away", "over_", "under_")) and "pp_" not in market:
            matchup = (p.get("player_or_matchup") or "").lower()
            for g in historical_mlb:
                g_date = (g.get("date") or "")[:10]
                if g_date != p.get("date"): continue
                g_mu = f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}".lower()
                if matchup not in g_mu and g_mu not in matchup: continue
                if g.get("home_score") is None: continue
                home_s = g.get("home_score") or 0
                away_s = g.get("away_score") or 0
                total = home_s + away_s
                if "over_" in market or "under_" in market:
                    try:
                        line = float(market.split("_")[-1])
                    except Exception:
                        break
                    is_over = "over_" in market
                    if total == line: result = "push"
                    elif (is_over and total > line) or (not is_over and total < line): result = "won"
                    else: result = "lost"
                elif "ml_home" in market:
                    result = "won" if home_s > away_s else "lost"
                elif "ml_away" in market:
                    result = "won" if away_s > home_s else "lost"
                break

        # Player props -- gamelog lookup
        elif any(k in market for k in ("1_plus_hit", "1_plus_hr", "1_plus_rbi", "1_plus_run",
                                        "2_plus_hits", "total_bases", "hrr", "pp_batter",
                                        "k_over", "er_under")):
            target = (p.get("player_or_matchup") or "").lower()
            line_m = re.search(r"(\d+(?:\.\d+)?)", market)
            line = float(line_m.group(1)) if line_m else None
            is_under = "under" in market
            prec = by_name.get(target)
            if prec and line is not None:
                for game in (prec.get("games") or []):
                    g_date = (game.get("date") or "")[:10]
                    if g_date != p.get("date"): continue
                    if game.get("pa") == 0 and game.get("min") in (None, 0): continue
                    stat = None
                    if "1_plus_hit" in market or "2_plus_hits" in market: stat = game.get("hits")
                    elif "total_bases" in market: stat = game.get("tb")
                    elif "hrr" in market: stat = (game.get("hits") or 0) + (game.get("runs") or 0) + (game.get("rbi") or 0)
                    elif "1_plus_hr" in market or market.startswith("hr"): stat = game.get("hr")
                    elif "1_plus_rbi" in market or "rbis" in market: stat = game.get("rbi")
                    elif "1_plus_run" in market or "runs" in market: stat = game.get("runs")
                    elif "k_over" in market: stat = game.get("k")
                    elif "er_under" in market: stat = game.get("er")
                    if stat is None: continue
                    if is_under:
                        if stat < line: result = "won"
                        elif stat == line: result = "push"
                        else: result = "lost"
                    else:
                        if stat > line: result = "won"
                        elif stat == line and "plus" in market: result = "won"
                        elif stat == line: result = "push"
                        else: result = "lost"
                    break

        if result:
            p["settled"] = True
            p["result"] = result
            p["settled_at"] = dt.datetime.now().isoformat(timespec="seconds")
            if result == "won":
                p["payout_units"] = round(decimal_odds - 1, 4)
            elif result == "lost":
                p["payout_units"] = -1.0
            else:
                p["payout_units"] = 0.0
            n_settled += 1

    return n_settled


def _bootstrap_from_locks_history(history, existing_ids) -> int:
    """Import all settled locks from locks_history.json into our unified
    ledger so we don't lose yesterday's W/L data."""
    n_imported = 0
    locks_doc = _load(os.path.join(DATA_DIR, "locks_history.json"))
    for L in (locks_doc.get("history") or []):
        if not L.get("settled"): continue
        sport = L.get("sport")
        pm = L.get("player_or_matchup")
        market = L.get("market")
        date = L.get("date")
        if not all([sport, pm, market, date]): continue
        pid = _pick_id("lock_of_day", sport, pm, market, date)
        if pid in existing_ids: continue
        history.append({
            "pick_id": pid,
            "source": "lock_of_day",
            "sport": sport,
            "player_or_matchup": pm,
            "market": market,
            "prob": L.get("prob"),
            "edge_pct": L.get("edge_pct"),
            "fair_american": L.get("fair_american"),
            "date": date,
            "recorded_at": L.get("recorded_at"),
            "settled": True,
            "result": L.get("result"),
            "payout_units": L.get("payout_units"),
            "settled_at": L.get("settled_at"),
            "_bootstrapped_from": "locks_history",
        })
        existing_ids.add(pid)
        n_imported += 1
    return n_imported


def run() -> Dict[str, Any]:
    state = _load(OUT)
    history = state.get("picks") or []
    existing_ids = {p.get("pick_id") for p in history}

    # Bootstrap: import yesterday's already-settled locks if we haven't yet
    n_bootstrapped = _bootstrap_from_locks_history(history, existing_ids)

    # Collect today's picks from every source
    today_picks = _collect_picks_from_sources()
    n_added = 0
    now_iso = dt.datetime.now().isoformat(timespec="seconds")
    for p in today_picks:
        if p["pick_id"] in existing_ids: continue
        p["recorded_at"] = now_iso
        history.append(p)
        existing_ids.add(p["pick_id"])
        n_added += 1

    # Settle anything pending
    n_newly_settled = _settle_picks(history)

    if len(history) > MAX_PICKS:
        history = history[-MAX_PICKS:]

    # Aggregate stats
    settled = [p for p in history if p.get("settled")]
    pending = [p for p in history if not p.get("settled")]
    wins = sum(1 for p in settled if p["result"] == "won")
    losses = sum(1 for p in settled if p["result"] == "lost")
    pushes = sum(1 for p in settled if p["result"] == "push")
    n_decided = wins + losses
    hit_rate = round(wins / n_decided, 4) if n_decided > 0 else None
    net_units = round(sum((p.get("payout_units") or 0) for p in settled), 3)
    n_risked = sum(1 for p in settled if p["result"] != "push")
    roi_pct = round(net_units / n_risked * 100, 2) if n_risked > 0 else None

    # Per-source breakdown
    by_source: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        s = p.get("source") or "?"
        b = by_source.setdefault(s, {"n": 0, "wins": 0, "losses": 0, "pushes": 0, "net_units": 0.0})
        b["n"] += 1
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for s, b in by_source.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None
        b["roi_pct"] = round(b["net_units"] / max(1, d) * 100, 2) if d > 0 else None

    # By market family
    by_mkt: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        m = _market_family(p.get("market"))
        b = by_mkt.setdefault(m, {"n": 0, "wins": 0, "losses": 0, "pushes": 0, "net_units": 0.0})
        b["n"] += 1
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for m, b in by_mkt.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # By sport
    by_sport: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        sp = p.get("sport") or "?"
        b = by_sport.setdefault(sp, {"n": 0, "wins": 0, "losses": 0, "pushes": 0, "net_units": 0.0})
        b["n"] += 1
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for sp, b in by_sport.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # Last 7 days
    today = dt.date.today()
    last_7 = []
    for p in settled:
        try:
            d = dt.date.fromisoformat(p.get("date") or "")
            if (today - d).days <= 7: last_7.append(p)
        except Exception: continue
    l7_w = sum(1 for p in last_7 if p["result"] == "won")
    l7_l = sum(1 for p in last_7 if p["result"] == "lost")
    l7_net = round(sum((p.get("payout_units") or 0) for p in last_7), 3)

    payload = {
        "generated_at": now_iso,
        "stake_assumption": "1u flat per pick",
        "total_picks": len(history),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": hit_rate,
        "net_units": net_units,
        "roi_pct": roi_pct,
        "n_added_this_run": n_added,
        "n_newly_settled_this_run": n_newly_settled,
        "n_bootstrapped_from_locks_history": n_bootstrapped,
        "by_source": by_source,
        "by_market_family": by_mkt,
        "by_sport": by_sport,
        "last_7_days": {
            "wins": l7_w, "losses": l7_l, "net_units": l7_net,
            "hit_rate": round(l7_w / max(1, l7_w + l7_l), 4) if (l7_w + l7_l) > 0 else None,
        },
        "picks": history,
        "note": ("Unified pick ledger -- records every pick the model "
                  "surfaces (top_25 board, whales, consensus, unders, "
                  "sharp action, locks, POD) and settles each against "
                  "actual outcomes. Per-source W-L feeds back into "
                  "calibration so the model learns which modules are "
                  "reliable. THIS is the training signal."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"All-picks ledger: {p['total_picks']} total picks ({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  This run: +{p['n_added_this_run']} new, +{p['n_newly_settled_this_run']} newly settled")
    if p['hit_rate'] is not None:
        print(f"  All: {p['wins']}-{p['losses']}-{p['pushes']} ({p['hit_rate']*100:.1f}%) | net {p['net_units']:+.2f}u | ROI {p['roi_pct']:+.1f}%")
    print(f"\n  Per-source:")
    for src, b in sorted(p['by_source'].items(), key=lambda kv: -kv[1]['n'])[:15]:
        hr = b.get('hit_rate')
        hr_s = f"{hr*100:.1f}%" if hr is not None else "—"
        print(f"    {src:28s}  n={b['n']:3d}  {b['wins']}-{b['losses']}  hit {hr_s:6s}  net {b['net_units']:+.2f}u")
