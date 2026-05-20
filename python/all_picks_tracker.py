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
