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
import unicodedata
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    from market_taxonomy import canonical_market as _canonical_market
except Exception:  # taxonomy is optional; fall back to the generic family
    _canonical_market = None


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


def _norm_name(s) -> str:
    """Accent/case-insensitive player-name key. Feeds and generators disagree on
    accents (pick 'teoscar hernandez' vs gamelog 'Teoscar Hernandez' with a
    combining accent) -- every by_name build and lookup must go through this or
    the pick silently never matches and voids."""
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _pick_id(source, sport, player_or_matchup, market, date_str):
    return f"{_safe_id(source)}|{_safe_id(sport)}|{_safe_id(player_or_matchup)}|{_safe_id(market)}|{date_str}"


def _market_family(market):
    if not market: return "unknown"
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", str(market))
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m.lower() or "unknown"


def _canon_family(market):
    """Canonical (deduplicated) family for a recognized MLB prop, else the generic
    line-stripped family -- so the SAME bet under different names pools into one
    key (1_plus_hr / to_hit_hr_yes / pp_batter_home_runs -> mlb_hr_0.5_over),
    instead of fragmenting the learning signal across 3-4 families."""
    if _canonical_market is not None:
        try:
            c = _canonical_market(market)
            if c:
                return c
        except Exception:
            pass
    return _market_family(market)


def _american_to_decimal(a):
    if a is None or not isinstance(a, (int, float)): return None
    if a >= 0: return 1 + a / 100
    return 1 + 100 / abs(a)


def _calibrated_prob(raw, market):
    """Isotonic recalibration of a RAW model prob -> honest prob for `market`,
    keyed by the canonical market family (identity if the family has too little
    settled history).

    ADDITIVE BY CONTRACT: this never replaces p_predicted. The recalibration
    engine learns its transform from p_predicted -> outcome, so feeding it back
    its own calibrated output would make the model train on itself and collapse
    the transform toward the identity. p_calibrated is a derived view for honest
    display + a calibrated-reliability readout only; p_predicted stays raw so the
    learning loop keeps an untouched signal to calibrate against."""
    try:
        rv = float(raw)
    except (TypeError, ValueError):
        return None
    if not (0.0 < rv < 1.0):
        return None
    try:
        import recalibration as _rc
        return round(float(_rc.recalibrate(rv, market)), 4)
    except Exception:
        return None


# MLB book bleeds juice on heavy favorites (model overconfidence): skip MLB picks
# priced at/below this fair-odds floor. -150 = the threshold Brandon flagged and the
# data confirms (everything <=-150 is -EV on realized hit rate). Other sports +
# the MLB-PP player-prop book (which cashes its favorites) are untouched.
MLB_FAV_PRICE_FLOOR = -150


def _is_mlb_juice_favorite(p: Dict[str, Any]) -> bool:
    if (p.get("sport") or "").upper() != "MLB":
        return False
    try:
        fa = float(p.get("fair_american"))
    except (TypeError, ValueError):
        return False
    return fa <= MLB_FAV_PRICE_FLOOR


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
                "projection": r.get("expected_runs"),
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

    # UFC first-round-finish (gradeable: settle vs the fight's ending round). The
    # strikes/TD props above need a fighter-stats feed we don't have; this one
    # needs only the round the fight ended, which the result feed provides.
    ufc_r1 = _load(os.path.join(DATA_DIR, "ufc_first_round_finish.json"))
    for r in (ufc_r1.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        fa, fb = r.get("fighter_a"), r.get("fighter_b")
        if bm.get("p") and fa and fb:
            out.append({
                "source": f"ufc_r1_{bm.get('market', '').lower()}",
                "sport": "UFC",
                "player_or_matchup": f"{fa} vs {fb}",
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": f"{fa} vs {fb}",
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
                # Date the pick to the GP so it survives to qualifying instead of
                # voiding mid-week, and settles against that weekend's grid.
                "game_date": fq.get("event_date"),
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
                "projection": r.get("expected_h"),
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
                "projection": r.get("projected_pts"),
                "sport": "WNBA",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
                "game_date": r.get("game_date"),
            })

    # NFL player props (model-conviction): pass/rush/rec yds, receptions, anytime
    # TD. Source keyed by stat_type so learning pools across lines; market carries
    # the line for _grade_nfl_pick. Empty off-season; live Week 1.
    nfl_props = _load(os.path.join(DATA_DIR, "nfl_player_props.json"))
    for r in (nfl_props.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nfl_{r.get('stat_type', 'prop')}",
                "sport": "NFL",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
                # Date the pick to its kickoff so it settles vs that day's box
                # score (NFL games are days out, not same-day like MLB props).
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),  # dedup + settle vs the match
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
                "game_date": r.get("game_date"),  # dedup + settle vs the match
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
                "game_date": r.get("game_date"),  # dedup + settle vs the match
            })

    # Soccer total goals over/under (the most-bet soccer market) -> settles via the
    # soccer grader's total-goals branch.
    soc_tot = _load(os.path.join(DATA_DIR, "soccer_total_goals_props.json"))
    for r in (soc_tot.get("strong_edges") or []):
        bm = (r.get("edges_found") or [{}])[0]
        if bm.get("p"):
            out.append({
                "source": f"soccer_total_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
                "game_date": r.get("game_date"),
            })

    # Soccer clean sheet (a side concedes 0) -> settles via the soccer grader.
    soc_cs = _load(os.path.join(DATA_DIR, "soccer_clean_sheet_props.json"))
    for r in (soc_cs.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"soccer_clean_sheet_{bm.get('market', '').lower()}",
                "sport": (r.get("league") or "SOCCER").upper(),
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
            })

    # MLB pitcher strikeouts strong edges
    mlb_pk = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    for r in (mlb_pk.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_pk_{bm.get('market', '').lower()}",
                "projection": r.get("expected_k"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "projection": r.get("expected_walks"),
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
                "projection": r.get("expected_k"),
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

    # Tennis player aces strong edges
    tennis_aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))
    for r in (tennis_aces.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"tennis_aces_{bm.get('market', '').lower()}",
                "sport": "TENNIS",
                "player_or_matchup": r.get("player"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB HBP strong edges
    mlb_hbp = _load(os.path.join(DATA_DIR, "mlb_hbp_props.json"))
    for r in (mlb_hbp.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_hbp_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NHL puck line strong edges
    nhl_pl = _load(os.path.join(DATA_DIR, "nhl_puck_line_props.json"))
    for r in (nhl_pl.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nhl_pl_{bm.get('market', '').lower()}",
                "sport": "NHL",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB run line strong edges
    mlb_rl = _load(os.path.join(DATA_DIR, "mlb_run_line_props.json"))
    for r in (mlb_rl.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_rl_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB pitcher-to-win strong edges
    mlb_pw = _load(os.path.join(DATA_DIR, "mlb_pitcher_win_props.json"))
    for r in (mlb_pw.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_pwin_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("pitcher"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # MLB to-hit-HR yes strong edges
    mlb_hr_yn = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    for r in (mlb_hr_yn.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"mlb_hr_yn_{bm.get('market', '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("batter"),
                "market": bm.get("market"),
                "prob": bm.get("p"),
                "fair_american": bm.get("fair_odds"),
                "p_predicted": bm.get("p"),
                "matchup": r.get("matchup"),
            })

    # NBA triple-double strong edges
    nba_td = _load(os.path.join(DATA_DIR, "nba_triple_double_props.json"))
    for r in (nba_td.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        if bm.get("p"):
            out.append({
                "source": f"nba_td_{bm.get('market', '').lower()}",
                "sport": "NBA",
                "player_or_matchup": r.get("player"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
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
                "game_date": r.get("game_date"),
            })

    # NBA combo markets (points+assists / points+rebounds / rebounds+assists) ->
    # settle via the basketball grader's _pts_ast / _pts_reb / _reb_ast sentinels.
    for jf, src in (("nba_player_pa_combo_props.json", "nba_pa"),
                    ("nba_player_pr_combo_props.json", "nba_pr"),
                    ("nba_player_ra_combo_props.json", "nba_ra")):
        combo = _load(os.path.join(DATA_DIR, jf))
        for r in (combo.get("strong_edges") or []):
            bm = r.get("best_market") or {}
            if bm.get("p"):
                out.append({
                    "source": f"{src}_{bm.get('market', '').lower()}",
                    "sport": "NBA",
                    "player_or_matchup": r.get("player"),
                    "market": bm.get("market"),
                    "prob": bm.get("p"),
                    "fair_american": bm.get("fair_odds"),
                    "p_predicted": bm.get("p"),
                    "matchup": r.get("matchup"),
                    "game_date": r.get("game_date"),
                })

    # MLB firehose: dormant batter generators (2+ hits / 3+ TB / 1+ RBI) -> settle
    # via the batter grader (the N+ markets now map to hits/tb/rbi lines).
    for jf, src in (("mlb_batter_2plus_hits_props.json", "mlb_2plus_hits"),
                    ("mlb_batter_3plus_tb_props.json", "mlb_3plus_tb"),
                    ("mlb_batter_rbi_props.json", "mlb_rbi_1plus")):
        bp = _load(os.path.join(DATA_DIR, jf))
        for r in (bp.get("strong_edges") or []):
            bm = r.get("best_market") or {}
            if bm.get("p") and (r.get("batter") or r.get("player")):
                out.append({
                    "source": f"{src}_{bm.get('market', '').lower()}",
                    "sport": "MLB",
                    "player_or_matchup": r.get("batter") or r.get("player"),
                    "market": bm.get("market"),
                    "prob": bm.get("p"),
                    "fair_american": bm.get("fair_odds"),
                    "p_predicted": bm.get("p"),
                    "matchup": r.get("matchup"),
                })

    # MLB firehose: alternate game totals -> normalize GAME_TOTAL_OVER_x to the
    # game-line over_x the MLB grader settles against total runs.
    gt = _load(os.path.join(DATA_DIR, "mlb_game_total_alt_props.json"))
    for r in (gt.get("strong_edges") or []):
        bm = r.get("best_market") or {}
        gmm = re.search(r"(over|under)_(\d+(?:\.\d+)?)", (bm.get("market") or "").lower())
        if bm.get("p") and gmm:
            out.append({
                "source": f"mlb_game_total_{(bm.get('market') or '').lower()}",
                "sport": "MLB",
                "player_or_matchup": r.get("matchup"),
                "market": f"{gmm.group(1)}_{gmm.group(2)}",
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
                "projection": r.get("expected_xbh"),
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
            "projection": r.get("expected_hrr"),
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
            "projection": r.get("expected_tb"),
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

    # World Cup 3-way model picks -- the WC desk feeds the learning loop. These
    # are seeded-band model probs (experimental firehose: tracked to train, not
    # featured); families learn fast at 73 group matches in 18 days. Markets use
    # the soccer grader's vocab (HOME_ML/AWAY_ML, OVER_x/UNDER_x, BTTS_YES).
    wcc = _load(os.path.join(DATA_DIR, "worldcup_cards.json"))
    for c in (wcc.get("cards") or []):
        mu = c.get("matchup")
        if not mu:
            continue
        sides = []
        if (c.get("p_home") or 0) >= 0.50:
            sides.append(("HOME_ML", c["p_home"], c.get("fair_home")))
        if (c.get("p_away") or 0) >= 0.50:
            sides.append(("AWAY_ML", c["p_away"], c.get("fair_away")))
        if (c.get("p_over_2_5") or 0) >= 0.55:
            sides.append(("OVER_2.5", c["p_over_2_5"], None))
        if (1 - (c.get("p_over_2_5") or 1)) >= 0.58:
            sides.append(("UNDER_2.5", round(1 - c["p_over_2_5"], 4), None))
        if (c.get("p_btts") or 0) >= 0.56:
            sides.append(("BTTS_YES", c["p_btts"], None))
        for mkt, p, fair in sides:
            out.append({
                "source": f"wc_model_{mkt.lower()}",
                "sport": "WORLDCUP",
                "player_or_matchup": mu,
                "market": mkt,
                "prob": round(float(p), 4),
                "fair_american": fair,
                "p_predicted": round(float(p), 4),
                "matchup": mu,
                "game_date": c.get("date"),
            })

    # MLB favorite-juice gate. The MLB game book is empirically OVERCONFIDENT on
    # heavy favorites: settled picks priced <= -150 realize well under their implied
    # win rate (the <=-200 bucket implies 66.7% but hits ~60% -> -19.8% ROI, ~-547u;
    # the -150..-200 bucket -> -10.6%). Together that is the bulk of the MLB book's
    # losses. Stop placing them. Scoped to sport "MLB" so the profitable MLB-PP
    # player-prop book (heavy favorites that DO cash, +42% ROI) is untouched.
    out = [p for p in out if not _is_mlb_juice_favorite(p)]

    # Stamp all picks with date + ID. A pick may carry its own game_date (e.g. NFL
    # props for a game a few days out) -- settle against THAT date's box score, not
    # the record date. Same prop + same game -> stable pick_id -> deduped, not
    # re-added every day it's generated ahead of kickoff.
    for p in out:
        game_date = p.pop("game_date", None)
        p["date"] = game_date or date_str
        p["pick_id"] = _pick_id(p["source"], p.get("sport"), p.get("player_or_matchup"), p.get("market"), p["date"])
        p["settled"] = False
        p["result"] = "pending"
        p["payout_units"] = None

    return out


def _batter_stat_and_threshold(market: str):
    """Map a batter-prop market name -> (gamelog stat field, OVER/UNDER line).

    Uses .5 lines so there are no integer-tie pushes. '1+' style yes/no markets
    become 'over 0.5'; '2+' becomes 'over 1.5'; explicit alt lines keep their
    number. Returns (None, None) for anything we can't confidently grade from
    the box-score fields we actually have (hits/hr/runs/rbi/k/bb/tb) -- e.g.
    extra-base-hit counts (no 2B/3B field) stay un-graded rather than guessed.
    """
    m = (market or "").lower()
    num = re.search(r"(\d+(?:\.\d+)?)", m)
    nval = float(num.group(1)) if num else None
    # "N+"-style alt markets: TB_3PLUS -> tb over 2.5, HITS_2PLUS -> hits over 1.5.
    plus = re.search(r"(\d+)\s*plus", m)
    if plus:
        ln = float(plus.group(1)) - 0.5
        if "tb" in m or "total_base" in m: return ("tb", ln)
        if "hit" in m: return ("hits", ln)
        if "rbi" in m: return ("rbi", ln)
        if "hr" in m or "home_run" in m: return ("hr", ln)
        if "run" in m: return ("runs", ln)
    if "total_base" in m:
        return ("tb", nval if nval is not None else 1.5)
    if "xbh" in m or "extra_base" in m:
        # XBH = 2B + 3B + HR; gradeable now that gamelogs store doubles/triples.
        # NB: the shared `plus` regex misses underscored names ("1_plus_xbh"), so
        # parse N+ here -- otherwise the line reads 1.0 and a 1-XBH night grades
        # as a LOSS on a 1+ bet (caught + auto-corrected on the backfill pass).
        xp = re.search(r"(\d+)[_\s]*plus", m)
        if xp:
            return ("xbh", float(xp.group(1)) - 0.5)
        return ("xbh", nval if nval is not None else 0.5)
    if "hrr" in m:
        return ("hrr", nval if nval is not None else 2.5)
    if "2_plus_hits" in m:
        return ("hits", 1.5)
    if ("to_record_hit" in m) or ("1_plus_hit" in m) or m == "hits":
        return ("hits", 0.5)
    if ("to_hit_hr" in m) or ("1_plus_hr" in m) or m.startswith("hr_") or m == "hr":
        return ("hr", 0.5)
    if ("to_score_run" in m) or ("1_plus_run" in m):
        return ("runs", 0.5)
    if ("1_plus_rbi" in m) or m.startswith("rbi"):
        return ("rbi", 0.5)
    if "walk" in m or "_bb_" in m or m.startswith("bb"):
        return ("bb", 0.5)
    if ("strikeout" in m) or ("k_1plus" in m) or ("_k_" in m):
        return ("k", 0.5)
    return (None, None)


def _grade_batter_prop(market: str, pick: Dict[str, Any], by_name: Dict[str, Any]) -> Optional[str]:
    """Grade a batter box-score prop against player_gamelogs. Returns
    'won'/'lost'/None. Conservative: returns None (leave pending) whenever the
    player, date, or stat can't be matched -- never fabricates a result."""
    field, line = _batter_stat_and_threshold(market)
    if field is None or line is None:
        return None
    prec = by_name.get(_norm_name(pick.get("player_or_matchup")))
    if not prec:
        return None
    m = (market or "").lower()
    # NO / UNDER side bets the player stays UNDER the line.
    is_under = ("under" in m) or m.endswith("_no") or ("_no_" in m)
    for game in (prec.get("games") or []):
        if (game.get("date") or "")[:10] != pick.get("date"):
            continue
        if not game.get("pa"):          # 0 / missing PA -> didn't bat; don't guess
            continue
        if field == "hrr":
            stat = (game.get("hits") or 0) + (game.get("runs") or 0) + (game.get("rbi") or 0)
        elif field == "xbh":
            # Requires the gamelog row to carry 2B/3B (older rows don't -- those
            # stay ungraded rather than guessed from hits alone).
            if game.get("doubles") is None and game.get("triples") is None:
                continue
            stat = (game.get("doubles") or 0) + (game.get("triples") or 0) + (game.get("hr") or 0)
        else:
            stat = game.get(field)
        if stat is None:
            continue
        over_wins = stat > line
        side = "UNDER/NO" if is_under else "OVER/YES"
        # Record the real box-score number that settled this pick so it is
        # independently verifiable (cross-check against any box score).
        pick["outcome"] = {
            "stat": field,
            "actual": stat,
            "line": line,
            "side": side,
            "verify": (f"{pick.get('player_or_matchup')} — {field} = {stat} "
                       f"(line {line}, bet {side}) on {pick.get('date')}"),
        }
        if is_under:
            return "won" if not over_wins else "lost"
        return "won" if over_wins else "lost"
    return None


# ---------------------------------------------------------------------------
# WNBA grading -- the first non-MLB sport wired into settlement, so its picks
# stop voiding unsettled and start feeding the learning loop the way MLB does.
# Player props grade vs wnba_player_gamelogs.json (real box scores); team alt-
# totals vs wnba_historical.json (real finals). Both set a verifiable `outcome`.
# Stat fields are basketball-generic, so NBA plugs into the same graders.
# ---------------------------------------------------------------------------
def _bball_stat(market: str):
    """Parse a basketball market -> (stat, line, side). stat is a gamelog field
    (pts/reb/ast/fg3m/stl/blk/to), a combo sentinel (_blk_stl/_pra/_reb_ast/_dd),
    or a team-total sentinel (_home_total/_away_total)."""
    m = (market or "").lower()
    side = "under" if "under" in m else ("over" if "over" in m else None)
    # The LINE is the number after over/under (e.g. 3pm_under_3.5 -> 3.5). Never
    # the first digit, or "3PM"/"blk_stl" would be mis-read as the line.
    mnum = re.search(r"(?:over|under)_(\d+(?:\.\d+)?)", m)
    if mnum:
        line = float(mnum.group(1))
    else:
        nums = re.findall(r"\d+(?:\.\d+)?", m)
        line = float(nums[-1]) if nums else None
    if "home_total" in m: stat = "_home_total"
    elif "away_total" in m: stat = "_away_total"
    elif "3pm" in m or "fg3" in m or "three" in m: stat = "fg3m"
    elif ("blk" in m and "stl" in m) or "blkstl" in m: stat = "_blk_stl"
    elif "pra" in m: stat = "_pra"
    elif ("reb" in m and "ast" in m): stat = "_reb_ast"
    elif "double_double" in m or "_dd_" in m or m.endswith("_dd"): stat = "_dd"
    elif m.startswith("pa_") or "points_assists" in m: stat = "_pts_ast"
    elif m.startswith("pr_") or "points_rebounds" in m: stat = "_pts_reb"
    elif m.startswith("ra_") or "rebounds_assists" in m: stat = "_reb_ast"
    elif "pts" in m or "point" in m: stat = "pts"
    elif "reb" in m: stat = "reb"
    elif "ast" in m: stat = "ast"
    elif "stl" in m or "steal" in m: stat = "stl"
    elif "blk" in m or "block" in m: stat = "blk"
    elif "tov" in m or re.search(r"(^|_)to(_|$)", m): stat = "to"
    else: stat = None
    return stat, line, side


def _bball_value(stat: str, game: Dict[str, Any]):
    if stat == "_blk_stl":
        if game.get("blk") is None and game.get("stl") is None: return None
        return (game.get("blk") or 0) + (game.get("stl") or 0)
    if stat == "_pra":
        if all(game.get(k) is None for k in ("pts", "reb", "ast")): return None
        return (game.get("pts") or 0) + (game.get("reb") or 0) + (game.get("ast") or 0)
    if stat == "_reb_ast":
        if all(game.get(k) is None for k in ("reb", "ast")): return None
        return (game.get("reb") or 0) + (game.get("ast") or 0)
    if stat == "_pts_ast":
        if all(game.get(k) is None for k in ("pts", "ast")): return None
        return (game.get("pts") or 0) + (game.get("ast") or 0)
    if stat == "_pts_reb":
        if all(game.get(k) is None for k in ("pts", "reb")): return None
        return (game.get("pts") or 0) + (game.get("reb") or 0)
    if stat == "_dd":
        cats = [game.get(k) or 0 for k in ("pts", "reb", "ast", "stl", "blk")]
        return 1.0 if sum(1 for c in cats if c >= 10) >= 2 else 0.0
    return game.get(stat)


def _grade_wnba_prop(pick: Dict[str, Any], by_name: Dict[str, Any]) -> Optional[str]:
    stat, line, side = _bball_stat(pick.get("market"))
    if stat is None or line is None or side is None or stat in ("_home_total", "_away_total"):
        return None
    prec = by_name.get(_norm_name(pick.get("player_or_matchup")))
    if not prec:
        return None
    for game in (prec.get("games") or []):
        if (game.get("date") or "")[:10] != pick.get("date"):
            continue
        val = _bball_value(stat, game)
        if val is None:
            continue
        over_wins = val > line
        won = (not over_wins) if side == "under" else over_wins
        label = stat.lstrip("_")
        pick["outcome"] = {
            "stat": label, "actual": val, "line": line, "side": side.upper(),
            "verify": (f"{pick.get('player_or_matchup')} — {label} = {val} "
                       f"(line {line}, bet {side}) on {pick.get('date')}"),
        }
        return "won" if won else "lost"
    return None


# The model's team vocab and ESPN's box-score vocab disagree on several WNBA
# abbreviations (model CONN/GOL/GSV/WAS vs ESPN CON/GS/WSH). Without this bridge
# every team-total pick for those teams silently failed to match its final and
# voided -- 14 of the 45 pending WNBA picks on 2026-06-10. Both vocabularies
# normalize onto ESPN's form before comparison.
_BBALL_AB_NORM = {"CONN": "CON", "GOL": "GS", "GSV": "GS", "WAS": "WSH", "LAS": "LA"}


def _norm_bball_matchup(s: str) -> str:
    parts = [t.strip().upper() for t in (s or "").split("@")]
    return " @ ".join(_BBALL_AB_NORM.get(t, t) for t in parts).lower()


def _grade_wnba_team_total(pick: Dict[str, Any], games: List[Dict[str, Any]]) -> Optional[str]:
    stat, line, side = _bball_stat(pick.get("market"))
    if stat not in ("_home_total", "_away_total") or line is None or side is None:
        return None
    matchup = _norm_bball_matchup(pick.get("player_or_matchup") or "")
    for g in games:
        if (g.get("date") or "")[:10] != pick.get("date"):
            continue
        g_mu = _norm_bball_matchup(f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}")
        if matchup != g_mu and matchup not in g_mu and g_mu not in matchup:
            continue
        score = g.get("home_score") if stat == "_home_total" else g.get("away_score")
        if score is None:
            continue
        over_wins = score > line
        won = (not over_wins) if side == "under" else over_wins
        which = "home" if stat == "_home_total" else "away"
        pick["outcome"] = {
            "final_score": f"{g.get('away_abbrev')} {g.get('away_score')} @ {g.get('home_abbrev')} {g.get('home_score')}",
            "team_total": score, "line": line, "side": side.upper(),
            "verify": (f"{g.get('away_abbrev')} @ {g.get('home_abbrev')}: {which} scored {score} "
                       f"(line {line}, bet {side}) on {pick.get('date')}"),
        }
        return "won" if won else "lost"
    return None


def _grade_wnba_pick(pick: Dict[str, Any], by_name: Dict[str, Any],
                     games: List[Dict[str, Any]]) -> Optional[str]:
    # Basketball-generic: also used for NBA (sport == "NBA") with NBA gamelogs.
    r = _grade_wnba_team_total(pick, games)
    return r if r is not None else _grade_wnba_prop(pick, by_name)


# ---------------------------------------------------------------------------
# NFL / football grading (built ahead of Week 1; validated vs the 2025 season).
# Player props grade vs nfl_player_gamelogs.json (pass/rush/rec yds, TDs, recs,
# anytime-TD = rush_td + rec_td); team totals + game lines vs nfl_historical.json.
# Dispatched by sport == "NFL", same shape as WNBA/NBA.
# ---------------------------------------------------------------------------
def _fb_stat(source: str, market: str):
    """Parse a football market (+ source as hint) -> (stat, line, side). stat is
    a gamelog field (pass_yds/pass_cmp/pass_td/pass_int/rush_yds/rush_att/rush_td/
    rec/rec_yds/rec_td/longest_reception/longest_rush/anytime_td) or a team-total
    sentinel (_home_total/_away_total)."""
    s = ((source or "") + " " + (market or "")).lower()
    if "under" in s: side = "under"
    elif "over" in s: side = "over"
    elif re.search(r"(^|[_ ])no([_ ]|$)", s): side = "under"
    elif "yes" in s: side = "over"
    else: side = None
    # anytime touchdown is a yes/no on the 0.5 line.
    if ("anytime_td" in s or "anytime_touchdown" in s or "to_score_td" in s
            or "td_scorer" in s or "anytime_scorer" in s):
        return "anytime_td", 0.5, (side or "over")
    if "home_total" in s: stat = "_home_total"
    elif "away_total" in s: stat = "_away_total"
    elif "longest_rec" in s or "longest_reception" in s: stat = "longest_reception"
    elif "longest_rush" in s or "longest_carry" in s: stat = "longest_rush"
    elif "pass_yd" in s or "passing_yard" in s: stat = "pass_yds"
    elif "rush_yd" in s or "rushing_yard" in s: stat = "rush_yds"
    elif "rec_yd" in s or "receiving_yard" in s: stat = "rec_yds"
    elif "pass_td" in s or "passing_td" in s: stat = "pass_td"
    elif "interception" in s or "pass_int" in s: stat = "pass_int"
    elif "rush_att" in s or "carries" in s or "rushing_attempt" in s: stat = "rush_att"
    elif "completion" in s or "pass_cmp" in s: stat = "pass_cmp"
    elif "reception" in s or "catches" in s or re.search(r"(^|[_ ])rec([_ ]|$)", s): stat = "rec"
    else: stat = None
    mnum = re.search(r"(?:over|under)_(\d+(?:\.\d+)?)", s)
    if mnum:
        line = float(mnum.group(1))
    else:
        nums = re.findall(r"\d+(?:\.\d+)?", s)
        line = float(nums[-1]) if nums else None
    return stat, line, side


def _grade_nfl_pick(pick: Dict[str, Any], by_name: Dict[str, Any],
                    games: List[Dict[str, Any]]) -> Optional[str]:
    m = (pick.get("market") or "").lower()
    matchup = (pick.get("player_or_matchup") or "").strip().lower()
    # Full-game moneyline / total -> grade vs the final score. A bare "over_X" is
    # only a game total when the subject is a game ("@" in the matchup); a player
    # prop whose stat lives in the source falls through to _fb_stat below.
    if ("ml_home" in m or "ml_away" in m
            or ("@" in matchup and re.fullmatch(r"(over|under)_\d+(?:\.\d+)?", m) is not None)):
        for g in games:
            if (g.get("date") or "")[:10] != pick.get("date"): continue
            g_mu = f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}".lower()
            if matchup not in g_mu and g_mu not in matchup: continue
            if g.get("home_score") is None: continue
            hs = g.get("home_score") or 0; aws = g.get("away_score") or 0; total = hs + aws
            if "over_" in m or "under_" in m:
                try: line = float(m.split("_")[-1])
                except Exception: return None
                if total == line: result = "push"
                elif (("over_" in m) == (total > line)): result = "won"
                else: result = "lost"
            elif "ml_home" in m: result = "won" if hs > aws else "lost"
            else: result = "won" if aws > hs else "lost"
            pick["outcome"] = {"final_score": f"{g.get('away_abbrev')} {aws} @ {g.get('home_abbrev')} {hs}",
                               "total_points": total,
                               "verify": f"{g.get('away_abbrev')} @ {g.get('home_abbrev')}: final {aws}-{hs} (total {total}) on {pick.get('date')}"}
            return result
        return None

    stat, line, side = _fb_stat(pick.get("source"), pick.get("market"))
    if stat is None or line is None or side is None:
        return None
    # Team totals -> vs the team's final score.
    if stat in ("_home_total", "_away_total"):
        for g in games:
            if (g.get("date") or "")[:10] != pick.get("date"): continue
            g_mu = f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}".lower()
            if matchup not in g_mu and g_mu not in matchup: continue
            score = g.get("home_score") if stat == "_home_total" else g.get("away_score")
            if score is None: continue
            over_wins = score > line
            won = (not over_wins) if side == "under" else over_wins
            which = "home" if stat == "_home_total" else "away"
            pick["outcome"] = {"final_score": f"{g.get('away_abbrev')} {g.get('away_score')} @ {g.get('home_abbrev')} {g.get('home_score')}",
                               "team_total": score, "line": line, "side": side.upper(),
                               "verify": f"{g.get('away_abbrev')} @ {g.get('home_abbrev')}: {which} scored {score} (line {line}, bet {side}) on {pick.get('date')}"}
            return "won" if won else "lost"
        return None
    # Player prop -> vs the box-score line.
    prec = by_name.get(matchup)
    if not prec:
        return None
    for game in (prec.get("games") or []):
        if (game.get("date") or "")[:10] != pick.get("date"): continue
        val = game.get(stat)
        if val is None: continue
        over_wins = val > line
        won = (not over_wins) if side == "under" else over_wins
        pick["outcome"] = {"stat": stat, "actual": val, "line": line, "side": side.upper(),
                           "verify": f"{pick.get('player_or_matchup')} — {stat} = {val} (line {line}, bet {side}) on {pick.get('date')}"}
        return "won" if won else "lost"
    return None


# ---- Individual / match sports: golf, tennis, UFC (simple-outcome graders) ----
def _last(name: str) -> str:
    """Last token of a name, lowercased -- for fuzzy match across name variants."""
    toks = (name or "").strip().lower().replace(".", "").split()
    return toks[-1] if toks else ""


def _names_match(a: str, b: str) -> bool:
    """True if two player names refer to the same person (full eq or last-name eq)."""
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return _last(a) == _last(b) and len(_last(a)) >= 3


def _grade_golf_pick(pick: Dict[str, Any], tournaments: List[Dict[str, Any]]) -> Optional[str]:
    """TOP_N / MAKE_CUT / MISS_CUT / WIN vs a tie-aware finish position."""
    market = (pick.get("market") or "").lower()
    player = (pick.get("player_or_matchup") or "").strip().lower()
    tname = (pick.get("matchup") or "").strip().lower()
    pdate = pick.get("date") or ""
    if not player:
        return None
    # Find the tournament: name match first, then date-window containing the player.
    cand = None
    for t in tournaments:
        tn = (t.get("name") or "").lower()
        if tname and (tname == tn or tname in tn or tn in tname):
            cand = t
            break
    if cand is None:
        for t in tournaments:
            sd, ed = t.get("start_date") or "", t.get("end_date") or t.get("start_date") or ""
            if sd and ed and sd <= pdate <= ed and player in (t.get("results") or {}):
                cand = t
                break
    if cand is None:
        return None
    res = (cand.get("results") or {}).get(player)
    if not res:  # try fuzzy (last-name) match within the tournament field
        res = next((v for v in (cand.get("results") or {}).values()
                    if _names_match(player, v.get("player", ""))), None)
    if not res:
        return None
    pos, made = res.get("position"), res.get("made_cut")
    if "make_cut" in market or "made_cut" in market:
        won = bool(made)
    elif "miss_cut" in market or "missed_cut" in market:
        won = not made
    elif market in ("win", "winner", "outright") or "outright" in market:
        won = made and pos == 1
    else:
        mm = re.search(r"top[_ ]?(\d+)", market)
        if not mm:
            return None
        won = bool(made) and pos <= int(mm.group(1))
    disp = f"T{pos}" if made else "MC"
    pick["outcome"] = {"tournament": cand.get("name"), "finish": disp, "to_par": res.get("to_par"),
                       "market": pick.get("market"),
                       "verify": f"{res.get('player')} finished {disp} ({res.get('to_par')}) at "
                                 f"{cand.get('name')} — {pick.get('market')}"}
    return "won" if won else "lost"


def _grade_tennis_pick(pick: Dict[str, Any], matches: List[Dict[str, Any]]) -> Optional[str]:
    """ML_PLAYER1/2 (match winner) or TOTAL_GAMES_OVER/UNDER_X vs the match result."""
    market = (pick.get("market") or "").upper()
    mu = (pick.get("player_or_matchup") or pick.get("matchup") or "")
    parts = re.split(r"\s+vs\.?\s+", mu, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    p1, p2 = parts[0].strip(), parts[1].strip()
    match = None
    for m in matches:
        n1, n2 = m.get("p1", ""), m.get("p2", "")
        if ((_names_match(p1, n1) and _names_match(p2, n2)) or
                (_names_match(p1, n2) and _names_match(p2, n1))):
            match = m
            break
    if match is None:
        return None
    winner = match.get("winner") or ""
    if market.startswith("ML_PLAYER1") or market == "ML_P1":
        won = _names_match(p1, match.get("winner_name") or winner)
    elif market.startswith("ML_PLAYER2") or market == "ML_P2":
        won = _names_match(p2, match.get("winner_name") or winner)
    elif "TOTAL_GAMES" in market:
        mm = re.search(r"(\d+(?:\.\d+)?)", market)
        if not mm:
            return None
        line, tot = float(mm.group(1)), match.get("total_games")
        if tot is None:
            return None
        won = (tot > line) if "OVER" in market else (tot < line)
    else:
        return None
    pick["outcome"] = {"match": f"{match.get('p1')} vs {match.get('p2')}",
                       "winner": match.get("winner_name"), "sets": match.get("sets"),
                       "total_games": match.get("total_games"), "market": pick.get("market"),
                       "verify": f"{match.get('winner_name')} won {match.get('sets')} "
                                 f"({match.get('total_games')} games) — {pick.get('market')}"}
    return "won" if won else "lost"


def _grade_ufc_pick(pick: Dict[str, Any], fights: List[Dict[str, Any]]) -> Optional[str]:
    """Reliable-from-scoreboard markets only: fight winner (ML) + first-round
    finish (ended in round 1). Strike/TD-count props need a fighter-stats feed
    (not in the scoreboard) -> left unsettled rather than mis-graded."""
    market = (pick.get("market") or "").upper()
    subj = (pick.get("player_or_matchup") or "")
    mu = (pick.get("matchup") or "")
    # Locate the fight (by either fighter name appearing, from subj or matchup).
    fight = None
    for f in fights:
        f1, f2 = f.get("f1", ""), f.get("f2", "")
        hay = f"{subj} {mu}"
        if (_names_match(subj, f1) or _names_match(subj, f2)
                or (_last(f1) and _last(f1) in hay.lower())
                or (_last(f2) and _last(f2) in hay.lower())):
            fight = f
            break
    if fight is None:
        return None
    rnd = fight.get("round")
    winner = fight.get("winner_name") or ""
    if "R1_FINISH" in market or "FIRST_ROUND_FINISH" in market or "ROUND_1_FINISH" in market:
        is_yes = "NO" not in market
        r1 = (rnd == 1)
        won = r1 if is_yes else (not r1)
    elif "ML" in market or market in ("WIN", "WINNER", "MONEYLINE"):
        won = _names_match(subj, winner)
    else:
        return None  # strikes/TD/method/rounds props: no reliable feed -> skip
    pick["outcome"] = {"fight": f"{fight.get('f1')} vs {fight.get('f2')}", "winner": winner,
                       "ended_round": rnd, "market": pick.get("market"),
                       "verify": f"{winner} def. opponent (ended R{rnd}) — {pick.get('market')}"}
    return "won" if won else "lost"


def _grade_f1_pick(pick: Dict[str, Any], events: List[Dict[str, Any]]) -> Optional[str]:
    """POLE / TOP_N (qualifying grid) or PODIUM / WIN (race finish) vs a driver's
    finishing position. The qualifying predictor leaves matchup='Unknown', so the
    pick is matched to its Grand Prix by date (the session falls a few days after
    the prediction is recorded)."""
    market = (pick.get("market") or "").upper()
    source = (pick.get("source") or "").lower()
    driver = (pick.get("player_or_matchup") or "").strip().lower()
    pdate = pick.get("date") or ""
    if not driver or not pdate:
        return None
    is_race = ("podium" in source or "race" in source or "win" in source
               or market in ("PODIUM", "WIN", "WINNER"))
    sess_key, date_key = ("race", "race_date") if is_race else ("qual", "qual_date")

    def _lookup(ev):
        results = ev.get(sess_key) or {}
        return results.get(driver) or next(
            (v for v in results.values() if _names_match(driver, v.get("driver", ""))), None)

    # Match the GP whose session date is nearest to (and not well before) the pick.
    cand, res, best = None, None, 99
    for ev in events:
        rel = ev.get(date_key) or ev.get("event_date") or ""
        if not rel:
            continue
        try:
            delta = (dt.date.fromisoformat(rel) - dt.date.fromisoformat(pdate)).days
        except Exception:
            continue
        if -2 <= delta <= 7 and abs(delta) < best:
            r = _lookup(ev)
            if r:
                cand, res, best = ev, r, abs(delta)
    if cand is None or not res:
        return None
    pos = res["position"]
    if "POLE" in market or market in ("WIN", "WINNER"):
        won = pos == 1
    elif "PODIUM" in market:
        won = pos <= 3
    else:
        mm = re.search(r"top[_ ]?(\d+)", market.lower())
        if not mm:
            return None
        won = pos <= int(mm.group(1))
    sess = "race" if is_race else "qualifying"
    pick["outcome"] = {"event": cand.get("name"), "session": sess, "position": pos,
                       "market": pick.get("market"),
                       "verify": f"{res.get('driver')} {sess} P{pos} at {cand.get('name')} — {pick.get('market')}"}
    return "won" if won else "lost"


_TEAM_DROP = {"fc", "sc", "afc", "cf", "club", "de", "the", "city", "town", "united"}


def _team_tokens(s: str):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return set(t for t in s.split() if len(t) > 1)


def _team_match(a: str, b: str) -> bool:
    """Same club across naming variants, without collapsing Man United vs Man City.
    Both names are ESPN-sourced so usually identical; allow subset + >=2 shared
    distinctive tokens (drops generic suffixes like 'United'/'City' that alone
    must not decide a match)."""
    ta, tb = _team_tokens(a), _team_tokens(b)
    if not ta or not tb:
        return False
    if ta == tb or ta <= tb or tb <= ta:
        return True
    if len(ta & tb) >= 2:
        return True
    distinct = (ta & tb) - _TEAM_DROP   # a shared *distinctive* token (not 'city'/'united')
    return len(distinct) >= 1 and (ta <= tb or tb <= ta or len(ta ^ tb) <= 1)


def _find_soccer_match(away: str, home: str, pdate: str, matches: List[Dict[str, Any]]):
    """Match a pick's game to a result by team names + a forward date window
    (soccer picks are recorded a few days before kickoff)."""
    best = None
    for m in matches:
        try:
            delta = (dt.date.fromisoformat(m.get("date") or "") - dt.date.fromisoformat(pdate)).days
        except Exception:
            continue
        if not (-2 <= delta <= 6):
            continue
        if ((_team_match(away, m.get("away", "")) and _team_match(home, m.get("home", ""))) or
                (_team_match(away, m.get("home", "")) and _team_match(home, m.get("away", "")))):
            if best is None or abs(delta) < best[0]:
                best = (abs(delta), m)
    return best[1] if best else None


def _grade_soccer_pick(pick: Dict[str, Any], matches: List[Dict[str, Any]]) -> Optional[str]:
    """BTTS, total cards, anytime goalscorer, match result/totals vs a real result."""
    market = (pick.get("market") or "").upper()
    source = (pick.get("source") or "").lower()
    subj = (pick.get("player_or_matchup") or "")
    mu = (pick.get("matchup") or "")
    pdate = pick.get("date") or ""
    # The game string is whichever field is "Away @ Home"; the other (for a
    # goalscorer prop) is the player.
    game = mu if "@" in mu else subj
    parts = re.split(r"\s+@\s+|\s+vs\.?\s+", game, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    away, home = parts[0].strip(), parts[1].strip()
    m = _find_soccer_match(away, home, pdate, matches)
    if not m:
        return None
    hs, aws, cards = m["home_score"], m["away_score"], m["total_cards"]
    detail = f"{m['away']} {aws}-{hs} {m['home']}"
    if "BTTS" in market or "btts" in source:
        both = hs > 0 and aws > 0
        won = both if ("NO" not in market) else (not both)
        verify = f"{detail}: both scored = {both}"
    elif "CARD" in market or "cards" in source:
        mm = re.search(r"(\d+(?:\.\d+)?)", market)
        if not mm:
            return None
        line = float(mm.group(1))
        won = (cards < line) if "UNDER" in market else (cards > line)
        verify = f"{detail}: {cards} cards (line {line})"
    elif "ANYTIME_GOAL" in market or "goalscorer" in source or "scorer" in source:
        scored = any(_names_match(subj, s) for s in (m.get("scorers") or []))
        won = scored  # ANYTIME_GOAL is a YES bet
        verify = f"{detail}: {subj} {'scored' if scored else 'did not score'}"
    elif "CLEAN_SHEET" in market:
        side_home = market.startswith("HOME")
        kept = (aws == 0) if side_home else (hs == 0)   # that side conceded zero
        won = kept if ("NO" not in market) else (not kept)
        verify = f"{detail}: {'home' if side_home else 'away'} clean sheet = {kept}"
    elif "ml_home" in source or market in ("HOME", "HOME_ML"):
        won = hs > aws
        verify = f"{detail}: home {'won' if won else 'did not win'}"
    elif "ml_away" in source or market in ("AWAY", "AWAY_ML"):
        won = aws > hs
        verify = f"{detail}: away {'won' if won else 'did not win'}"
    elif re.search(r"(over|under)_(\d+(?:\.\d+)?)", market.lower()):
        mm = re.search(r"(over|under)_(\d+(?:\.\d+)?)", market.lower())
        line = float(mm.group(2))
        won = (m["total_goals"] > line) if mm.group(1) == "over" else (m["total_goals"] < line)
        verify = f"{detail}: {m['total_goals']} goals (line {line})"
    else:
        return None
    pick["outcome"] = {"final_score": detail, "total_cards": cards, "total_goals": m["total_goals"],
                       "scorers": m.get("scorers"), "market": pick.get("market"),
                       "verify": f"{verify} — {pick.get('market')}"}
    return "won" if won else "lost"


def _nhl_stat(source: str, market: str) -> Optional[str]:
    s = ((source or "") + " " + (market or "")).lower()
    if "hits" in s or "hit_" in s or "_hits" in s: return "hits"
    if "block" in s: return "blocks"
    if "shots" in s or "sog" in s: return "shots"
    if "assist" in s: return "assists"
    if "point" in s: return "points"
    if "goal" in s and "goalie" not in s: return "goals"
    return None


def _find_nhl_game(matchup: str, pdate: str, games: List[Dict[str, Any]]):
    parts = re.split(r"\s+@\s+|\s+vs\.?\s+", matchup or "", maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None
    away, home = parts[0].strip(), parts[1].strip()
    for g in games:
        try:
            if abs((dt.date.fromisoformat((g.get("date") or "")[:10]) - dt.date.fromisoformat(pdate)).days) > 2:
                continue
        except Exception:
            continue
        ga, gh = g.get("away_abbrev", ""), g.get("home_abbrev", "")
        ga_nm, gh_nm = g.get("away_name", ""), g.get("home_name", "")
        # NHL pick matchups use full team names; the game carries both the full
        # name and the abbrev -- match on either.
        away_ok = (_team_match(away, ga_nm) or _team_match(away, ga)
                   or (_last(away) and _last(away) in (ga_nm or "").lower())
                   or (ga and ga.lower() in away.lower()))
        home_ok = (_team_match(home, gh_nm) or _team_match(home, gh)
                   or (_last(home) and _last(home) in (gh_nm or "").lower())
                   or (gh and gh.lower() in home.lower()))
        if away_ok and home_ok:
            return g
    return None


def _grade_nhl_pick(pick: Dict[str, Any], by_name: Dict[str, Any],
                    games: List[Dict[str, Any]]) -> Optional[str]:
    """Skater hits/blocks props + puck line vs real box scores. Period-3 totals
    have no reliable ESPN period feed -> left unsettled rather than mis-graded."""
    market = (pick.get("market") or "").upper()
    source = (pick.get("source") or "").lower()
    subj = (pick.get("player_or_matchup") or "").strip()
    pdate = pick.get("date") or ""

    # Period-3 total: no period-scoring feed available -> skip.
    if "p3" in source or "period" in source or re.match(r"P\dG?_", market):
        return None

    # Puck line (game spread): {AWAY,HOME}_PLUS_X / _pl_ source.
    m = re.search(r"(AWAY|HOME)_PLUS_(\d+(?:\.\d+)?)", market)
    if m or "_pl_" in source:
        g = _find_nhl_game(subj, pdate, games)
        if not g or g.get("home_score") is None:
            return None
        side = "home" if (m and m.group(1) == "HOME") or "home" in source else "away"
        line = float(m.group(2)) if m else 1.5
        diff = (g["home_score"] - g["away_score"]) if side == "home" else (g["away_score"] - g["home_score"])
        won = diff > -line   # covers the +line spread (loses by < line, or wins)
        pick["outcome"] = {"final_score": f"{g.get('away_abbrev')} {g['away_score']} @ {g.get('home_abbrev')} {g['home_score']}",
                           "side": side, "line": line, "market": pick.get("market"),
                           "verify": f"{g.get('away_abbrev')} {g['away_score']} @ {g.get('home_abbrev')} {g['home_score']}: {side} {'+' if line>=0 else ''}{line} — {pick.get('market')}"}
        return "won" if won else "lost"

    # Skater prop (hits / blocks / shots / points / goals / assists).
    stat = _nhl_stat(source, market)
    mnum = re.search(r"(?:over|under)_(\d+(?:\.\d+)?)", (source + " " + market).lower())
    if stat is None or not mnum:
        return None
    line = float(mnum.group(1))
    side = "under" if "under" in (source + market).lower() else "over"
    prec = by_name.get(_norm_name(subj))
    if not prec:
        return None
    for game in (prec.get("games") or []):
        try:
            if abs((dt.date.fromisoformat((game.get("date") or "")[:10]) - dt.date.fromisoformat(pdate)).days) > 2:
                continue
        except Exception:
            continue
        val = game.get(stat)
        if val is None:
            continue
        over_wins = val > line
        won = (not over_wins) if side == "under" else over_wins
        pick["outcome"] = {"stat": stat, "actual": val, "line": line, "side": side.upper(),
                           "verify": f"{subj} — {stat} = {val} (line {line}, bet {side}) on {game.get('date')}"}
        return "won" if won else "lost"
    return None


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
            by_name[_norm_name(prec.get("name"))] = prec
    # Non-MLB real outcomes (box scores + finals) so each sport's picks settle +
    # feed the learning loop instead of voiding. WNBA is live now; NBA + NFL are
    # wired ahead of their seasons (gamelog files appear when those sports run).
    wnba_by_name = {_norm_name(k): v for k, v in (_load(os.path.join(DATA_DIR, "wnba_player_gamelogs.json")).get("by_name") or {}).items()}
    wnba_games = _load(os.path.join(DATA_DIR, "wnba_historical.json")).get("games") or []
    nba_by_name = {_norm_name(k): v for k, v in (_load(os.path.join(DATA_DIR, "nba_player_gamelogs.json")).get("by_name") or {}).items()}
    nba_games = _load(os.path.join(DATA_DIR, "nba_historical.json")).get("games") or []
    nfl_by_name = {_norm_name(k): v for k, v in (_load(os.path.join(DATA_DIR, "nfl_player_gamelogs.json")).get("by_name") or {}).items()}
    nfl_games = _load(os.path.join(DATA_DIR, "nfl_historical.json")).get("games") or []
    nhl_by_name = {_norm_name(k): v for k, v in (_load(os.path.join(DATA_DIR, "nhl_player_gamelogs.json")).get("by_name") or {}).items()}
    nhl_games = _load(os.path.join(DATA_DIR, "nhl_historical.json")).get("games") or []
    # Individual / match sports (golf finish, tennis match result, UFC fight result)
    # so those picks settle on simple outcomes instead of voiding.
    golf_tournaments = _load(os.path.join(DATA_DIR, "golf_results.json")).get("tournaments") or []
    tennis_matches = _load(os.path.join(DATA_DIR, "tennis_results.json")).get("matches") or []
    ufc_fights = _load(os.path.join(DATA_DIR, "ufc_results.json")).get("fights") or []
    f1_events = _load(os.path.join(DATA_DIR, "f1_results.json")).get("events") or []
    soccer_matches = _load(os.path.join(DATA_DIR, "soccer_results.json")).get("matches") or []

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
        decimal_odds = _american_to_decimal(p.get("fair_american")) or 1.91

        sport = (p.get("sport") or "").upper()
        if sport == "WNBA":
            result = _grade_wnba_pick(p, wnba_by_name, wnba_games)
        elif sport == "NBA":
            result = _grade_wnba_pick(p, nba_by_name, nba_games)   # same basketball grader
        elif sport == "NFL":
            result = _grade_nfl_pick(p, nfl_by_name, nfl_games)
        elif sport == "NHL":
            result = _grade_nhl_pick(p, nhl_by_name, nhl_games)
        elif sport == "GOLF":
            result = _grade_golf_pick(p, golf_tournaments)
        elif sport == "TENNIS":
            result = _grade_tennis_pick(p, tennis_matches)
        elif sport == "UFC":
            result = _grade_ufc_pick(p, ufc_fights)
        elif sport == "F1":
            result = _grade_f1_pick(p, f1_events)
        elif sport in ("EPL", "MLS", "UCL", "UEL", "SOCCER", "LALIGA", "SERIEA",
                       "BUNDESLIGA", "LIGUE1", "WORLDCUP", "FIFA.WORLD"):
            result = _grade_soccer_pick(p, soccer_matches)
        else:
            # MLB / default (unchanged). Game-level: FULL-GAME moneyline or FULL-GAME
            # total ONLY. Props like team_sb_under_0.5 / inning totals contain
            # "under_"/"over_" but are NOT full-game totals; a true game total is
            # exactly "over_X"/"under_X" with nothing else.
            is_game_line = (("ml_home" in market) or ("ml_away" in market)
                            or re.fullmatch(r"(over|under)_\d+(?:\.\d+)?", market) is not None)
            if is_game_line:
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
                    # Record the real final score that settled it (verifiable).
                    away_ab = g.get("away_abbrev", ""); home_ab = g.get("home_abbrev", "")
                    p["outcome"] = {
                        "final_score": f"{away_ab} {away_s} @ {home_ab} {home_s}",
                        "total_runs": total,
                        "verify": (f"{away_ab} @ {home_ab}: final {away_s}-{home_s} "
                                   f"(total {total} runs) on {p.get('date')}"),
                    }
                    break
            else:
                result = _grade_batter_prop(market, p, by_name)

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


VOID_AFTER_DAYS = 4


def _void_stale_pending(history: List[Dict[str, Any]]) -> int:
    """Mark long-pending picks that can never settle as VOID (not settled).

    A pick whose game date is more than VOID_AFTER_DAYS in the past and is still
    unsettled has no reachable outcome (other-sport picks with no box-score feed,
    or data-retention gaps). Carrying it as 'pending' forever is dishonest and
    makes the ledger un-self-cleaning. Voided picks are excluded from pending and
    are NOT counted in settled / W-L / ROI (the `voided` flag is separate from
    `settled`, so no settled-stat logic changes). MLB props settle within ~2 days
    via gamelogs, so a 4-day cutoff only catches the genuinely un-gradeable.
    """
    today = dt.date.today()
    n = 0
    for p in history:
        if p.get("settled") or p.get("voided"):
            continue
        try:
            gd = dt.date.fromisoformat((p.get("date") or "")[:10])
        except Exception:
            continue
        if (today - gd).days > VOID_AFTER_DAYS:
            p["voided"] = True
            p["voided_at"] = dt.datetime.now().isoformat(timespec="seconds")
            p["voided_reason"] = f"unsettleable: no outcome feed within {VOID_AFTER_DAYS} days"
            n += 1
    return n


def _reconcile_settled_voids(history: List[Dict[str, Any]]) -> int:
    """Clear a stale void from any pick that is now settled with a real outcome.

    A pick can be voided at the 4-day mark (no feed yet) and THEN settled in a
    later run once the feed arrives -- most often when a new sport's grader ships
    after its picks had already aged out (this happened in bulk for WNBA/NBA/golf
    when their adapters landed). Such a pick ends up flagged BOTH settled and
    voided, so it is double-counted (in W-L/ROI and in the void tally) and the
    by-sport record looks empty. The real outcome wins -- drop the void.
    """
    n = 0
    for p in history:
        if p.get("settled") and p.get("voided"):
            # A duplicate-wager void is INTENTIONAL on a settled pick (the same
            # event was counted more than once; the extra copies are voided by
            # _collapse_duplicate_wagers). Never resurrect those.
            if str(p.get("voided_reason") or "").startswith("duplicate wager"):
                continue
            p["voided"] = False
            p.pop("voided_reason", None)
            p.pop("voided_at", None)
            n += 1
    return n


def _correct_misrouted_grades(history: List[Dict[str, Any]]) -> int:
    """One-time correction: un-settle + void picks mis-graded by the old
    over-broad game-level routing. Props that contain over_/under_ (team SB,
    inning totals, first-5 totals) were graded against the FULL-game run total
    and almost always recorded 'lost' -- fabricated losses. We have no feed to
    grade them correctly, so the honest result is void (removed from W/L/ROI).
    Idempotent: once voided they are skipped."""
    n = 0
    for p in history:
        if not p.get("settled") or p.get("voided"):
            continue
        # SCOPE GUARD (2026-06-10): this correction exists for the legacy MLB
        # game-line mis-route ONLY. It used to fire on ANY settled market
        # containing over_/under_ -- which is every basketball/hockey/soccer
        # prop -- so each newly-graded WNBA pick was un-settled and voided the
        # moment it settled (the silent killer behind WNBA's 0-settled, 250-void
        # ledger). A pick graded by its own sport's prop/total grader stamps a
        # verifiable outcome (stat/actual or team_total); only the wrong-path
        # game-line grade lacks one. Never touch those, and never touch non-MLB.
        if (p.get("sport") or "").upper() != "MLB":
            continue
        out = p.get("outcome") or {}
        if any(k in out for k in ("stat", "actual", "team_total")):
            continue
        m = (p.get("market") or "").lower()
        routed_gl = (any(k in m for k in ("ml_home", "ml_away", "over_", "under_"))
                     and "pp_" not in m)
        true_gl = (("ml_home" in m) or ("ml_away" in m)
                   or re.fullmatch(r"(over|under)_\d+(?:\.\d+)?", m) is not None)
        if routed_gl and not true_gl:
            p["settled"] = False
            p["result"] = "pending"
            p["payout_units"] = None
            p.pop("settled_at", None)
            p["voided"] = True
            p["voided_at"] = dt.datetime.now().isoformat(timespec="seconds")
            p["voided_reason"] = "mis-graded prop (was scored as a full-game total); voided"
            n += 1
    return n


def _recompute_result(p: Dict[str, Any], historical_mlb, by_name) -> Optional[str]:
    """Re-grade a pick against the CURRENT box-score feeds. Returns
    'won'/'lost'/'push', or None when it can't be confidently graded. Side
    effect: sets/refreshes p['outcome'] with the verifiable detail so the record
    stays auditable. This is the single grading authority shared by the backfill
    and re-settlement passes, so the two never disagree."""
    market = (p.get("market") or "").lower()
    is_game_line = (("ml_home" in market) or ("ml_away" in market)
                    or re.fullmatch(r"(over|under)_\d+(?:\.\d+)?", market) is not None)
    if is_game_line:
        matchup = (p.get("player_or_matchup") or "").lower()
        for g in historical_mlb:
            if (g.get("date") or "")[:10] != p.get("date"): continue
            g_mu = f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}".lower()
            if matchup not in g_mu and g_mu not in matchup: continue
            if g.get("home_score") is None: continue
            home_s = g.get("home_score") or 0; away_s = g.get("away_score") or 0
            total = home_s + away_s
            a_ab = g.get("away_abbrev", ""); h_ab = g.get("home_abbrev", "")
            p["outcome"] = {"final_score": f"{a_ab} {away_s} @ {h_ab} {home_s}",
                            "total_runs": total,
                            "verify": f"{a_ab} @ {h_ab}: final {away_s}-{home_s} (total {total}) on {p.get('date')}"}
            if "over_" in market or "under_" in market:
                try: ln = float(market.split("_")[-1])
                except Exception: return None
                return "push" if total == ln else ("won" if (("over_" in market) == (total > ln)) else "lost")
            if "ml_home" in market:
                return "won" if home_s > away_s else "lost"
            if "ml_away" in market:
                return "won" if away_s > home_s else "lost"
            return None
        return None
    return _grade_batter_prop(market, p, by_name)  # sets p["outcome"]


def _attach_outcomes(history: List[Dict[str, Any]]) -> int:
    """Backfill the verifiable box-score outcome onto already-settled picks that
    don't have one yet, so the EXISTING track record is auditable (not just new
    picks). Adds the 'outcome' detail + a provisional 'outcome.check'. It does
    NOT flip results -- the authoritative agree/re-settle pass is
    _resettle_on_revision (runs immediately after)."""
    historical_mlb = _load(os.path.join(DATA_DIR, "historical_mlb.json")).get("games") or []
    gamelogs = _load(os.path.join(DATA_DIR, "player_gamelogs.json")).get("by_player_id") or {}
    by_name = {_norm_name(prec.get("name")): prec
               for prec in gamelogs.values() if isinstance(prec, dict)}
    n = 0
    for p in history:
        if not p.get("settled") or p.get("outcome"):
            continue
        recomputed = _recompute_result(p, historical_mlb, by_name)
        if p.get("outcome"):
            n += 1
            rec = p.get("result")
            if recomputed and recomputed != rec:
                p["outcome"]["check"] = f"recorded {rec}; current box score -> {recomputed} (stat revised after settle)"
            else:
                p["outcome"]["check"] = "verified"
    return n


def _regrade_strict(p: Dict[str, Any], historical_mlb, by_name) -> Optional[str]:
    """Conservative re-grade used ONLY by the re-settle pass. Returns
    'won'/'lost'/'push' only when the CURRENT data gives a single unambiguous
    answer; returns None when ambiguous so we never flip a pick we can't pin to
    one game. The key guard is doubleheaders: a pick like 'CHW @ SF ML_AWAY' or
    'PHI @ SD UNDER_7' can match two games with opposite results on the same date
    -- those must never be auto-flipped (we can't know which game it was). Sets
    p['outcome'] only when it resolves unambiguously."""
    market = (p.get("market") or "").lower()
    is_game_line = (("ml_home" in market) or ("ml_away" in market)
                    or re.fullmatch(r"(over|under)_\d+(?:\.\d+)?", market) is not None)
    if is_game_line:
        matchup = (p.get("player_or_matchup") or "").lower()
        matches = []
        for g in historical_mlb:
            if (g.get("date") or "")[:10] != p.get("date"): continue
            g_mu = f"{g.get('away_abbrev','')} @ {g.get('home_abbrev','')}".lower()
            if matchup not in g_mu and g_mu not in matchup: continue
            if g.get("home_score") is None: continue
            matches.append(g)
        if not matches:
            return None
        graded = []
        for g in matches:
            home_s = g.get("home_score") or 0; away_s = g.get("away_score") or 0
            total = home_s + away_s
            if "over_" in market or "under_" in market:
                try: ln = float(market.split("_")[-1])
                except Exception: return None
                r = "push" if total == ln else ("won" if (("over_" in market) == (total > ln)) else "lost")
            elif "ml_home" in market:
                r = "won" if home_s > away_s else "lost"
            elif "ml_away" in market:
                r = "won" if away_s > home_s else "lost"
            else:
                return None
            graded.append((r, g))
        if len({r for r, _ in graded}) != 1:
            return None                      # doubleheader / conflicting -> don't flip
        g = graded[0][1]
        home_s = g.get("home_score") or 0; away_s = g.get("away_score") or 0
        total = home_s + away_s
        a_ab = g.get("away_abbrev", ""); h_ab = g.get("home_abbrev", "")
        p["outcome"] = {"final_score": f"{a_ab} {away_s} @ {h_ab} {home_s}",
                        "total_runs": total,
                        "verify": f"{a_ab} @ {h_ab}: final {away_s}-{home_s} (total {total}) on {p.get('date')}"}
        return graded[0][0]
    # Prop: require exactly one gradeable game that date (no doubleheader split).
    prec = by_name.get(_norm_name(p.get("player_or_matchup")))
    if not prec:
        return None
    same_day = [gm for gm in (prec.get("games") or [])
                if (gm.get("date") or "")[:10] == p.get("date") and gm.get("pa")]
    if len(same_day) != 1:
        return None
    return _grade_batter_prop(market, p, by_name)  # sets p["outcome"]


def _resettle_on_revision(history: List[Dict[str, Any]]) -> int:
    """Re-grade every settled pick for a DEFINITIVELY-FINAL game against the
    current box score and correct any whose recorded result no longer matches.
    MLB revises hits/RBI/runs for a day or two after a game; without this pass the
    ledger keeps counting outcomes the current box score contradicts (the ~3% of
    grades flagged 'revised'). This makes net_units / hit_rate / ROI reflect the
    truth: we never carry a result the box score disagrees with. It updates
    result + payout_units, appends an audit entry to resettle_log, and refreshes
    outcome.check. Only games strictly before today are touched, so an in-progress
    or mid-revision feed can never cause churn. Returns the number flipped."""
    historical_mlb = _load(os.path.join(DATA_DIR, "historical_mlb.json")).get("games") or []
    gamelogs = _load(os.path.join(DATA_DIR, "player_gamelogs.json")).get("by_player_id") or {}
    by_name = {_norm_name(prec.get("name")): prec
               for prec in gamelogs.values() if isinstance(prec, dict)}
    today = dt.date.today()
    n_flip = 0
    for p in history:
        if not p.get("settled") or p.get("voided"):
            continue
        try:
            gd = dt.date.fromisoformat((p.get("date") or "")[:10])
        except Exception:
            continue
        if gd >= today:                      # only definitively-final games
            continue
        recomputed = _regrade_strict(p, historical_mlb, by_name)  # ambiguous -> None
        if not recomputed or not isinstance(p.get("outcome"), dict):
            continue
        prev = p.get("result")
        if recomputed == prev:
            p["outcome"]["check"] = "verified"
            continue
        # Current box score disagrees with what we recorded -> re-settle to truth.
        decimal_odds = _american_to_decimal(p.get("fair_american")) or 1.91
        p["result"] = recomputed
        p["payout_units"] = (round(decimal_odds - 1, 4) if recomputed == "won"
                             else (-1.0 if recomputed == "lost" else 0.0))
        p.setdefault("resettle_log", []).append({
            "at": dt.datetime.now().isoformat(timespec="seconds"),
            "from": prev, "to": recomputed,
            "reason": "stat revised after settlement; re-graded vs current box score",
        })
        p["outcome"]["check"] = f"verified (re-settled from {prev} after stat revision)"
        n_flip += 1
    return n_flip


def _wager_key(p) -> tuple:
    """A pick's WAGER identity -- what bet this is, independent of which board
    surfaced it or which day it was snapshotted. One wager = one position."""
    return (_safe_id(p.get("sport")), _safe_id(p.get("player_or_matchup")),
            _safe_id(p.get("market")))


def _collapse_duplicate_wagers(history) -> int:
    """One wager must count ONCE in the public record. Two historical leak paths
    violated that (caught by the 2026-07-11 site audit):

      1. EVENT RE-ADDS: pick_id includes the snapshot date, so a FUTURE event that
         sits on a board for days (a UFC fight, a golf outright, a tennis match)
         re-entered daily as a "new" pick -- then every copy settled against the
         same result. fight_r1_finish_yes showed 182 settled "picks" that were 26
         distinct fights (one fight counted 13x), injecting ~+244u of phantom
         profit that inflated the durable-book / curated headlines and even the
         calibration fit.
      2. TWIN BOARDS: the same wager recorded the same day by two sources
         (top_25_board AND lock_of_day) -> different pick_id -> both settled
         (~+105u double-counted on MLB props).

    Collapse: group SETTLED non-void picks by (wager identity + identical outcome
    payload) -- byte-identical outcomes mean the same physical result, so this
    can never merge two genuinely different games. Keep the FIRST copy (earliest
    settled_at/recorded_at); VOID the extras (audit trail preserved -- rows stay,
    flagged) so every downstream consumer recomputes honestly. Also collapses
    PENDING dups of the same wager (keep earliest). Idempotent."""
    n = 0
    # settled dups: same wager + same outcome payload
    groups: Dict[tuple, List[Dict[str, Any]]] = {}
    for p in history:
        if not p.get("settled") or p.get("voided") or not p.get("outcome"):
            continue
        k = _wager_key(p) + (json.dumps(p["outcome"], sort_keys=True, default=str),)
        groups.setdefault(k, []).append(p)
    for k, g in groups.items():
        if len(g) < 2:
            continue
        g.sort(key=lambda x: (x.get("settled_at") or "", x.get("recorded_at") or "", x.get("date") or ""))
        for extra in g[1:]:
            extra["voided"] = True
            extra["voided_at"] = dt.datetime.now().isoformat(timespec="seconds")
            extra["voided_reason"] = ("duplicate wager: same event/bet recorded more than once "
                                      "(event re-add or twin board); collapsed to the first copy")
            n += 1
    # pending dups: same wager awaiting settlement more than once
    pend: Dict[tuple, List[Dict[str, Any]]] = {}
    for p in history:
        if p.get("settled") or p.get("voided"):
            continue
        pend.setdefault(_wager_key(p), []).append(p)
    for k, g in pend.items():
        if len(g) < 2:
            continue
        g.sort(key=lambda x: (x.get("recorded_at") or "", x.get("date") or ""))
        for extra in g[1:]:
            extra["voided"] = True
            extra["voided_at"] = dt.datetime.now().isoformat(timespec="seconds")
            extra["voided_reason"] = "duplicate wager: same bet already pending; collapsed to the first copy"
            n += 1
    return n


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

    # ADD-GUARD (one wager = one position): skip a pick whose WAGER is already on
    # the book. (a) Same wager PENDING -- blocks a future event (UFC fight, golf
    # outright, tennis match) re-entering daily while it sits on a board, and a
    # twin board re-recording the same bet the same day. (b) Same wager SETTLED
    # within 14 days, for one-off EVENT sports only -- a stale board can't re-add
    # a fight that already happened. Daily sports (MLB etc.) are exempt from (b):
    # the same player+market tomorrow is a genuinely new game.
    _EVENT_SPORTS = {"ufc", "golf", "tennis", "cs", "boxing", "f1"}
    _cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
    _open_by_key: Dict[tuple, Dict[str, Any]] = {}
    for _p in history:
        if not _p.get("settled") and not _p.get("voided"):
            _open_by_key.setdefault(_wager_key(_p), _p)
    _open_wagers = set(_open_by_key)
    _recent_event_wagers = {
        _wager_key(p) for p in history
        if p.get("settled") and not p.get("voided")
        and _safe_id(p.get("sport")) in _EVENT_SPORTS
        and str(p.get("settled_at") or "")[:10] >= _cutoff
    }
    n_dup_blocked = 0
    for p in today_picks:
        if p["pick_id"] in existing_ids: continue
        wk = _wager_key(p)
        if wk in _open_wagers or wk in _recent_event_wagers:
            n_dup_blocked += 1
            # ATTRIBUTION: one wager = one position, but the record must still know
            # every board that OFFERED the wager while it was open. Without this,
            # whichever feed runs first keeps sole credit -- post-guard, the curated
            # book silently drained to game-lines-only exactly this way (the boards'
            # prop copies were skipped because an experimental feed recorded the
            # same wager minutes earlier). Stamp the kept OPEN copy; never touch
            # settled picks (a wager that settled before a board re-offered it was
            # genuinely not on that board while actionable).
            kept = _open_by_key.get(wk)
            src = p.get("source")
            if kept is not None and src and src != kept.get("source"):
                also = kept.setdefault("also_sources", [])
                if src not in also:
                    also.append(src)
            continue
        p["recorded_at"] = now_iso
        history.append(p)
        existing_ids.add(p["pick_id"])
        _open_wagers.add(wk)
        _open_by_key.setdefault(wk, p)
        n_added += 1

    # Backfill newly-carried fields onto PENDING picks collected before a
    # collector learned to stamp them (the dedup above skips re-collection, so
    # without this an upgrade only reaches tomorrow's picks). Never touches
    # settled picks or overwrites an existing value.
    today_by_id = {p["pick_id"]: p for p in today_picks}
    for p in history:
        if p.get("settled") or p.get("voided"):
            continue
        fresh = today_by_id.get(p.get("pick_id"))
        if fresh and fresh.get("projection") is not None and p.get("projection") is None:
            p["projection"] = fresh["projection"]

    # Settle anything pending
    n_newly_settled = _settle_picks(history)

    # A real outcome supersedes a prior stale void (e.g. picks voided before their
    # sport's grader shipped, then settled once it did). Run before the void sweep
    # + stats so nothing is counted as both settled and void.
    n_reconciled = _reconcile_settled_voids(history)

    # One wager = one position: void duplicate copies of the same settled event /
    # same pending bet (see _collapse_duplicate_wagers). Runs every cycle; the
    # first run is the big historical correction (~781 duplicate settled picks,
    # ~+335u of phantom profit, found by the 2026-07-11 audit).
    n_dups_collapsed = _collapse_duplicate_wagers(history)

    # Void picks that can never settle (no outcome feed, > VOID_AFTER_DAYS old)
    # so 'pending' stays honest and the ledger self-cleans.
    n_voided_this_run = _void_stale_pending(history)

    # Correct picks that were mis-graded as full-game totals (fabricated losses).
    n_corrected = _correct_misrouted_grades(history)

    # Backfill verifiable box-score outcomes onto settled picks (auditable record).
    n_outcomes = _attach_outcomes(history)

    # Re-settle any settled pick whose CURRENT box score now disagrees with the
    # recorded result (MLB stat revisions) so net_units / hit_rate / ROI reflect
    # the truth -- we never carry an outcome the box score contradicts.
    n_resettled = _resettle_on_revision(history)

    if len(history) > MAX_PICKS:
        # Evict SIGNAL-FREE entries first -- never settled history while any exist.
        # The old tail-cut (history[-MAX_PICKS:]) chopped the OLDEST entries, which
        # are settled track record, while thousands of voided picks survived --
        # settled count was eroding ~170/day at the cap (caught 2026-07-06 when
        # n_settled fell 6526 -> 6357 with 2,840 voided hogging the window).
        # Priority: (1) voided picks, oldest first (excluded from every stat);
        # (2) stale pendings >14d old that will never grade (dead events);
        # (3) only then the original oldest-first tail cut, as last resort.
        overflow = len(history) - MAX_PICKS
        stale_cutoff = (dt.date.today() - dt.timedelta(days=14)).isoformat()
        voided_idx = [i for i, p in enumerate(history) if p.get("voided")]
        stale_pend_idx = [i for i, p in enumerate(history)
                          if not p.get("voided") and not p.get("settled")
                          and (p.get("date") or "9999") < stale_cutoff]
        drop = set(voided_idx[:overflow])
        if len(drop) < overflow:
            drop |= set(stale_pend_idx[:overflow - len(drop)])
        if drop:
            history = [p for i, p in enumerate(history) if i not in drop]
        if len(history) > MAX_PICKS:
            history = history[-MAX_PICKS:]

    # Honest prob at the SOURCE: stamp each pick's calibrated probability ADDITIVELY
    # from its raw p_predicted (which stays untouched -- see _calibrated_prob). Done
    # over all of history each run so the field always reflects the current best
    # transform (it sharpens as more outcomes settle). Picks with no usable raw prob
    # (pure signal-score sources: consensus, unders, sharp-money-following) get no
    # stamp. This is the ledger half of "make the model honest upstream".
    n_calibrated = 0
    for p in history:
        cal = _calibrated_prob(p.get("p_predicted") if p.get("p_predicted") is not None
                               else p.get("prob"), p.get("market"))
        if cal is not None:
            p["p_calibrated"] = cal
            n_calibrated += 1

    # Aggregate stats (void is neither settled nor pending -- excluded from both).
    # NOTE the voided check: since the duplicate-wager collapse, a pick can be BOTH
    # settled and voided (a dup copy of an already-counted wager) -- those must not
    # count in the record, or the summary re-inflates by exactly the phantom units
    # the collapse removed.
    settled = [p for p in history if p.get("settled") and not p.get("voided")]
    pending = [p for p in history if not p.get("settled") and not p.get("voided")]
    n_void = sum(1 for p in history if p.get("voided"))
    wins = sum(1 for p in settled if p["result"] == "won")
    losses = sum(1 for p in settled if p["result"] == "lost")
    pushes = sum(1 for p in settled if p["result"] == "push")
    n_decided = wins + losses
    hit_rate = round(wins / n_decided, 4) if n_decided > 0 else None
    net_units = round(sum((p.get("payout_units") or 0) for p in settled), 3)
    n_risked = sum(1 for p in settled if p["result"] != "push")
    roi_pct = round(net_units / n_risked * 100, 2) if n_risked > 0 else None

    # ---- CURATED ("Alpha") rollup: the featured/recommended plays only, to
    #      compare against the full all-signals firehose above. This is the
    #      honest "what you'd actually bet" record. Experimental prop feeds are
    #      tracked to train the model but are NOT recommended plays.
    _CURATED_PREFIXES = ("lock_of_day", "top_25_board", "whale_", "consensus_hit",
                         "sharp_", "mlb_under_alert", "pod")

    def _is_curated(src):
        s = src or ""
        return any(s == pre or s.startswith(pre) for pre in _CURATED_PREFIXES)

    def _is_curated_pick(p):
        # A wager counts as curated if the copy the guard kept came from a curated
        # source OR if a curated board offered the same wager while it was open
        # (also_sources, stamped by the ADD-GUARD). One row either way -- attribution
        # only, never a double count.
        if _is_curated(p.get("source")):
            return True
        return any(_is_curated(s) for s in (p.get("also_sources") or ()))

    cur = [p for p in settled if _is_curated_pick(p)]
    c_wins = sum(1 for p in cur if p["result"] == "won")
    c_losses = sum(1 for p in cur if p["result"] == "lost")
    c_pushes = sum(1 for p in cur if p["result"] == "push")
    c_dec = c_wins + c_losses
    c_net = round(sum((p.get("payout_units") or 0) for p in cur), 3)
    c_risked = sum(1 for p in cur if p["result"] != "push")
    curated = {
        "n_settled": len(cur),
        "wins": c_wins, "losses": c_losses, "pushes": c_pushes,
        "hit_rate": round(c_wins / c_dec, 4) if c_dec else None,
        "net_units": c_net,
        "roi_pct": round(c_net / c_risked * 100, 2) if c_risked else None,
        "sources": sorted({p.get("source") for p in cur}),
        "definition": ("Featured/recommended plays only -- Lock of the Day, Top 25, "
                       "Whale, Sharp, Consensus (hit), Under Alerts, POD. Excludes the "
                       "experimental prop feeds, which are tracked to train the model, "
                       "not bet."),
    }

    # RECENT FORM (trailing 30 days by pick date): the all-time number alone
    # invites "did we get worse?" confusion whenever its average drifts a point
    # -- surface the recent window beside it so drift always has context.
    _cut30 = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    cur30 = [p for p in cur if (p.get("date") or "") >= _cut30]
    c30_w = sum(1 for p in cur30 if p["result"] == "won")
    c30_l = sum(1 for p in cur30 if p["result"] == "lost")
    c30_net = round(sum((p.get("payout_units") or 0) for p in cur30), 3)
    c30_risked = sum(1 for p in cur30 if p["result"] != "push")
    curated["last_30"] = {
        "wins": c30_w, "losses": c30_l,
        "net_units": c30_net,
        "roi_pct": round(c30_net / c30_risked * 100, 2) if c30_risked else None,
        "hit_rate": round(c30_w / (c30_w + c30_l), 4) if (c30_w + c30_l) else None,
    }

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

    # By CANONICAL family -- same as by_market_family but with duplicate-named
    # bets POOLED (mlb_hr_0.5_over collects 1_plus_hr + to_hit_hr_yes + ...), so
    # the learning loop weights on all the evidence for a bet, not 3 fragments.
    # by_market_family is kept alongside for back-compat / stat continuity.
    by_canon: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        cm = _canon_family(p.get("market"))
        b = by_canon.setdefault(cm, {"n": 0, "wins": 0, "losses": 0, "pushes": 0, "net_units": 0.0})
        b["n"] += 1
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for cm, b in by_canon.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # By sport -- over ALL picks (not just settled) so coverage gaps surface: a
    # sport with many picks but 0 settled has no outcome feed wired yet. Carries
    # pending + void counts and ROI alongside the W-L record.
    by_sport: Dict[str, Dict[str, Any]] = {}
    for p in history:
        sp = (p.get("sport") or "?").upper()
        b = by_sport.setdefault(sp, {"n": 0, "settled": 0, "wins": 0, "losses": 0,
                                     "pushes": 0, "pending": 0, "void": 0, "net_units": 0.0,
                                     "_src": set()})
        b["n"] += 1
        b["_src"].add((p.get("source") or "?").split("_over_")[0].split("_under_")[0])
        if p.get("voided"):
            b["void"] += 1
        elif p.get("settled"):
            b["settled"] += 1
            if p["result"] == "won": b["wins"] += 1
            elif p["result"] == "lost": b["losses"] += 1
            elif p["result"] == "push": b["pushes"] += 1
            b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
        else:
            b["pending"] += 1
    for sp, b in by_sport.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None
        b["roi_pct"] = round(b["net_units"] / d * 100, 2) if d > 0 else None
        b["markets"] = len(b.pop("_src"))   # distinct market types graded for this sport

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

    # Calibrated-reliability readout: does the honest (recalibrated) prob track the
    # settled outcomes better than the raw model prob? Both scored against the SAME
    # outcomes; p_predicted is the raw input, p_calibrated the stamped honest prob.
    # IN-SAMPLE (the transform is fit on this same ledger) -- the held-out 70/30
    # validation lives in recalibration_map.json. Surfaced so the track-record page
    # can show the model is honest at the source, not just at display.
    calibrated_reliability = None
    try:
        import calibration as _cal
        r_raw, r_cal, r_y = [], [], []
        for p in settled:
            if p.get("result") not in ("won", "lost"):
                continue
            raw = p.get("p_predicted") if p.get("p_predicted") is not None else p.get("prob")
            try:
                rv = float(raw)
            except (TypeError, ValueError):
                continue
            if not (0.0 < rv < 1.0):
                continue
            cv = p.get("p_calibrated")
            r_raw.append(rv)
            r_cal.append(float(cv) if cv is not None else rv)
            r_y.append(1 if p["result"] == "won" else 0)
        if len(r_y) >= 50:
            calibrated_reliability = {
                "n": len(r_y),
                "ece_raw": round(_cal.expected_calibration_error(r_raw, r_y, 10), 4),
                "ece_calibrated": round(_cal.expected_calibration_error(r_cal, r_y, 10), 4),
                "brier_raw": round(_cal.brier_score(r_raw, r_y), 5),
                "brier_calibrated": round(_cal.brier_score(r_cal, r_y), 5),
                "note": ("In-sample over the settled ledger (the isotonic transform is fit on "
                         "these same outcomes); held-out 70/30 validation is in "
                         "recalibration_map.json. p_predicted = raw model prob (kept untouched "
                         "for the learning loop); p_calibrated = honest prob stamped per pick. "
                         "Lower ECE/Brier on the calibrated column = the displayed % is truer."),
            }
    except Exception:
        calibrated_reliability = None

    payload = {
        "generated_at": now_iso,
        "stake_assumption": "1u flat per pick",
        "total_picks": len(history),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_void": n_void,
        "wins": wins, "losses": losses, "pushes": pushes,
        "hit_rate": hit_rate,
        "net_units": net_units,
        "roi_pct": roi_pct,
        "n_calibrated_picks": n_calibrated,
        "calibrated_reliability": calibrated_reliability,
        "curated": curated,
        "n_added_this_run": n_added,
        "n_newly_settled_this_run": n_newly_settled,
        "n_resettled_this_run": n_resettled,
        "n_voided_this_run": n_voided_this_run,
        "n_duplicates_collapsed_this_run": n_dups_collapsed,
        "n_duplicate_adds_blocked_this_run": n_dup_blocked,
        "n_reconciled_settled_voids": n_reconciled,
        "n_bootstrapped_from_locks_history": n_bootstrapped,
        "by_source": by_source,
        "by_market_family": by_mkt,
        "by_canonical": by_canon,
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
    # TRIPWIRE (defense-in-depth): the settled count only ever GROWS (picks settle, never
    # un-settle), so a large DROP means the prior ledger failed to load (corruption / parse
    # error) and we're about to reset from scratch -- which wiped 6,500 settled picks once
    # (2026-06-29). Compare against an independent high-water sidecar that survives a
    # corrupted ledger, and refuse to overwrite the good files with a catastrophic shrink.
    # Count only non-void settled (duplicate-collapsed copies are settled+voided
    # and don't belong in the record; the 50% threshold absorbs the one-time step
    # down from the collapse itself).
    new_settled = sum(1 for p in history if p.get("settled") and not p.get("voided"))
    _hw_path = os.path.join(DATA_DIR, "ledger_highwater.json")
    try:
        _hw = int((json.load(open(_hw_path, encoding="utf-8")) or {}).get("max_settled", 0))
    except Exception:
        _hw = 0
    if _hw > 200 and new_settled < _hw * 0.5:
        print(f"[all_picks_tracker] ABORT WRITE: settled would drop {_hw} (high-water) -> "
              f"{new_settled} (>50%); corrupted/empty load suspected. Existing ledger + "
              f"summary left UNTOUCHED for recovery.")
        return payload
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    # Compact summary (all rollups, minus the multi-MB picks array) so the public
    # track-record page renders by-sport / by-source without pulling the full ledger.
    summary = {k: v for k, v in payload.items() if k != "picks"}
    with open(os.path.join(DATA_DIR, "ledger_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    try:  # advance the high-water mark only after a healthy write
        with open(_hw_path, "w", encoding="utf-8") as f:
            json.dump({"max_settled": max(_hw, new_settled)}, f)
    except Exception:
        pass
    return payload


if __name__ == "__main__":
    p = run()
    print(f"All-picks ledger: {p['total_picks']} total picks ({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  This run: +{p['n_added_this_run']} new, +{p['n_newly_settled_this_run']} newly settled, "
          f"{p.get('n_resettled_this_run', 0)} re-settled (stat revisions corrected)")
    if p['hit_rate'] is not None:
        print(f"  All: {p['wins']}-{p['losses']}-{p['pushes']} ({p['hit_rate']*100:.1f}%) | net {p['net_units']:+.2f}u | ROI {p['roi_pct']:+.1f}%")
    print(f"  Calibrated prob stamped on {p.get('n_calibrated_picks', 0)} picks (additive; p_predicted kept raw)")
    cr = p.get("calibrated_reliability")
    if cr:
        print(f"  Reliability (n={cr['n']}): ECE raw {cr['ece_raw']} -> calibrated {cr['ece_calibrated']} | "
              f"Brier {cr['brier_raw']} -> {cr['brier_calibrated']}  (in-sample)")
    print(f"\n  Per-source:")
    for src, b in sorted(p['by_source'].items(), key=lambda kv: -kv[1]['n'])[:15]:
        hr = b.get('hit_rate')
        hr_s = f"{hr*100:.1f}%" if hr is not None else "—"
        print(f"    {src:28s}  n={b['n']:3d}  {b['wins']}-{b['losses']}  hit {hr_s:6s}  net {b['net_units']:+.2f}u")
