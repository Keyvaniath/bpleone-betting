"""
EdgeStat -- LOCKS OF THE DAY persistent prediction tracker.

Each pipeline run, captures the top 5 highest-confidence picks from
todays_top_plays.json and appends them to a permanent record. Later, when
outcomes settle (via outcomes.py / historical_*.json), the lock is marked
won/lost and ROI accumulated.

Storage shape:
  data/locks_history.json
  {
    "generated_at": "...",
    "total_locks": N,
    "n_settled": K,
    "n_pending": N-K,
    "wins": W, "losses": L,
    "hit_rate": W/(W+L),
    "net_units": total_units_won_or_lost,
    "roi_pct": net_units / total_risked,
    "by_sport": { "MLB": {wins,losses,hit_rate}, ... },
    "by_market_family": { "k_over": {...}, "1_plus_hit": {...} },
    "history": [
       { pick_id, date, sport, player_or_matchup, market, prob, fair_american,
         kelly_units, unit_size, source, settled (bool),
         result (won/lost/push/pending), actual, payout_units },
       ...
    ]
  }

Pick ID: sport|player_or_matchup|market_family|date
  This is deterministic so the same pick across the day's runs merges
  rather than duplicating. Only the FIRST observation of the day is kept
  (no chasing line moves).

Output: data/locks_history.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "locks_history.json")

N_LOCKS_PER_DAY = 5     # top 5 picks each day become "the locks"
MAX_HISTORY = 5000


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _normalize_market(market: str) -> str:
    """Collapse line-specific markets so HRR_under_3.5 and HRR_under_4.5
    appear as the SAME pick family for settlement matching."""
    if not market: return ""
    m = str(market)
    # Don't collapse here -- keep the specific line so we know what to settle
    return m


def _pick_id(sport, player_or_matchup, market, date_str):
    """Deterministic ID so re-runs merge same pick."""
    safe = lambda s: re.sub(r"[^a-zA-Z0-9_]", "_", str(s or "?"))[:40]
    return f"{safe(sport)}|{safe(player_or_matchup)}|{safe(market)}|{date_str}"


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _today_date_str() -> str:
    return dt.date.today().isoformat()


def _market_family(market: str) -> str:
    """Strip trailing line numbers for family-level rollup stats."""
    if not market: return "unknown"
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", str(market))
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m or "unknown"


def _build_rationale(c: Dict[str, Any]) -> str:
    """Generate a 1-line explanation of why the model likes this pick."""
    sport = c.get("sport") or ""
    pm = c.get("player_or_matchup") or ""
    market = (c.get("market") or "").lower()
    prob = c.get("prob") or 0
    edge = c.get("edge_pct") or 0
    src = (c.get("source") or "").lower()

    # Source-specific rationales (order matters: check specific patterns before generic over/under)
    if "ml_home" in market:
        return f"Model gives {pm.split(' @ ')[-1] if ' @ ' in pm else pm} the home win at {prob*100:.0f}% (+{edge:.0f}% edge vs market)."
    if "ml_away" in market:
        return f"Model favors the road team at {prob*100:.0f}% (+{edge:.0f}% edge); contrarian read on a perceived favorite at home."
    # PP player props -- check BEFORE generic over/under since they contain _under_/_over_
    if "pp_batter" in market:
        line_m = re.search(r"(\d+(?:\.\d+)?)", market)
        line = line_m.group(1) if line_m else "?"
        side = "UNDER" if "under" in market else "OVER"
        stat = "hits+runs+RBIs" if "hrr" in market else ("total bases" if "total_bases" in market else ("RBIs" if "rbis" in market else ("runs" if "runs" in market else "batter stat")))
        return f"{pm} PrizePicks {side} {line} {stat}: model {prob*100:.0f}% vs PP-implied break-even ~57% (per-leg fair odds -136)."
    # Game total over/under (must come AFTER pp_batter check)
    if "over_" in market or "under_" in market:
        side = "OVER" if "over_" in market else "UNDER"
        line_m = re.search(r"(\d+(?:\.\d+)?)", market)
        line = line_m.group(1) if line_m else "?"
        return f"Game total {side} {line} at {prob*100:.0f}% -- model projects total runs/goals significantly {'above' if side=='OVER' else 'below'} the market line."
    if "k_over" in market:
        line_m = re.search(r"(\d+(?:\.\d+)?)", market)
        line = line_m.group(1) if line_m else "?"
        if "form_regression" in src or "pitcher_form" in src:
            return f"{pm} K over {line}: reverted projection (40% recent / 60% season blend) yields {prob*100:.0f}% to clear."
        return f"{pm} K over {line}: pitcher matchup model projects {prob*100:.0f}% based on K/9 + opp OBP."
    if "er_under" in market:
        line_m = re.search(r"(\d+(?:\.\d+)?)", market)
        line = line_m.group(1) if line_m else "?"
        return f"{pm} ER under {line}: pitcher quality + opposing lineup quality yields {prob*100:.0f}% the start stays clean."
    if "1_plus_hit_vs_sp" in market:
        return f"{pm} 1+ hit: matchup-adjusted xwOBA + career-vs-pitcher splits push base form to {prob*100:.0f}%."
    if "1_plus_hr_vs_sp" in market:
        return f"{pm} 1+ HR: opposing pitcher FIP + batter pitch-arsenal xwOBA edge -> {prob*100:.0f}% HR shot."
    if "situational" in src:
        side = "home" if c.get("source", "").endswith("home") else "today's"   # crude
        return f"{pm}: {side} situational split (home/away + day/night) above season norm -> {prob*100:.0f}%."
    if "shutout" in market:
        return f"{pm}: opposing goalie projection + team shots-against -> {prob*100:.0f}% shutout."
    if "team_total" in market:
        line_m = re.search(r"(\d+(?:\.\d+)?)", market)
        line = line_m.group(1) if line_m else "?"
        side = "over" if "over" in market else "under"
        return f"Team-total {side} {line}: decomposed from model fair_total + p_home_win Poisson projection ({prob*100:.0f}%)."

    # Fallback
    return f"Model {prob*100:.0f}% with +{edge:.1f}% edge vs market fair price (source: {src or 'composite'})."


def _build_new_locks(top_plays: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pick top N from today's top plays board."""
    picks = (top_plays.get("top_25") or [])[:N_LOCKS_PER_DAY]
    date_str = _today_date_str()
    out = []
    for c in picks:
        sport = c.get("sport")
        pm = c.get("player_or_matchup")
        market = c.get("market")
        prob = c.get("prob")
        fair = c.get("fair_american")
        edge_pct = c.get("edge_pct")
        kelly_unit = c.get("unit_size_quarter_kelly")
        if not (sport and pm and market and prob): continue
        out.append({
            "pick_id": _pick_id(sport, pm, market, date_str),
            "date": date_str,
            "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
            "sport": sport,
            "player_or_matchup": pm,
            "team": c.get("team"),
            "market": market,
            "market_family": _market_family(market),
            "prob": prob,
            "fair_american": fair,
            "edge_pct": edge_pct,
            "kelly_fraction": c.get("kelly_fraction"),
            "unit_size_quarter_kelly": kelly_unit,
            "source": c.get("source"),
            "rationale": _build_rationale(c),
            "settled": False,
            "result": "pending",
            "actual": None,
            "payout_units": None,
            "settled_at": None,
        })
    return out


def _try_settle_pick(pick: Dict[str, Any]) -> Optional[str]:
    """Try to settle a single pending pick. Returns 'won' / 'lost' / 'push'
    if settled, None if still pending."""
    if pick.get("settled"):
        return None
    market = (pick.get("market") or "").lower()
    # Player-prop markets settle via gamelog lookup
    if any(k in market for k in ("1_plus_hit", "1_plus_hr", "1_plus_rbi",
                                   "1_plus_run", "2_plus_hits", "k_over",
                                   "er_under", "total_bases", "hrr",
                                   "pp_batter", "pts_over", "reb_over",
                                   "ast_over", "3pm_over", "pra_over",
                                   "double_double", "triple_double")):
        return _settle_player_prop(pick)
    # Game-level markets (ML / total over/under) settle via historical_*.json
    return _settle_game_market(pick)


def _settle_game_market(pick: Dict[str, Any]) -> Optional[str]:
    sport = (pick.get("sport") or "").upper()
    date_s = pick.get("date")
    sport_to_file = {
        "MLB": "historical_games.json", "MLB-PP": "historical_games.json",
        "NBA": "historical_nba.json", "NHL": "historical_nhl.json",
        "WNBA": "historical_wnba.json", "MLS": "historical_mls.json",
        "EPL": "historical_epl.json", "UCL": "historical_ucl.json",
        "CWS": "historical_cws.json", "NCAAB": "historical_ncaab.json",
        "NCAAF": "historical_ncaaf.json", "NFL": "historical_nfl.json",
    }
    hist_file = sport_to_file.get(sport)
    if not hist_file: return None
    hist = _load(os.path.join(DATA_DIR, hist_file))
    games = hist.get("games") or []
    matchup = (pick.get("player_or_matchup") or "").lower()
    market = (pick.get("market") or "").lower()
    for g in games:
        g_date = (g.get("date") or "")[:10]
        g_mu = (g.get("matchup") or g.get("name") or "").lower()
        if g_date != date_s: continue
        if "ml_home" in market or "ml_away" in market:
            if matchup not in g_mu and g_mu not in matchup: continue
            if g.get("home_score") is None: continue
            winner_is_home = (g.get("home_score") or 0) > (g.get("away_score") or 0)
            if "ml_home" in market:
                return "won" if winner_is_home else "lost"
            return "lost" if winner_is_home else "won"
        if "over_" in market or "under_" in market:
            if matchup not in g_mu and g_mu not in matchup: continue
            try:
                line = float(re.search(r"(\d+(?:\.\d+)?)", market).group(1))
            except Exception:
                continue
            if g.get("home_score") is None: continue
            total = (g.get("home_score") or 0) + (g.get("away_score") or 0)
            if "over_" in market:
                return "won" if total > line else ("push" if total == line else "lost")
            return "won" if total < line else ("push" if total == line else "lost")
    return None


def _settle_player_prop(pick: Dict[str, Any]) -> Optional[str]:
    """Settle a player-prop lock by reading actual stats from player_gamelogs.json."""
    gamelogs = _load(os.path.join(DATA_DIR, "player_gamelogs.json"))
    bpid = gamelogs.get("by_player_id") or {}
    target_name = (pick.get("player_or_matchup") or "").lower()
    market = (pick.get("market") or "").lower()
    date_s = pick.get("date")

    # Parse line from market name (e.g. "1_plus_hit" -> line=0.5; "PP_..._under_3.5" -> 3.5)
    line_match = re.search(r"(\d+(?:\.\d+)?)", market)
    line = float(line_match.group(1)) if line_match else None
    is_under = "under" in market or "_no" in market
    is_over = "over" in market or ("plus" in market and not is_under)

    # Find player's actual game stats for the date
    for pid, prec in bpid.items():
        if not isinstance(prec, dict): continue
        if (prec.get("name") or "").lower() != target_name: continue
        games = prec.get("games") or []
        for g in games:
            g_date = (g.get("date") or "")[:10]
            if g_date != date_s: continue
            # Map market stat -> game field
            stat_val = None
            if "1_plus_hit" in market or "2_plus_hits" in market or "total_bases" in market:
                stat_val = g.get("hits") if "hit" in market else g.get("tb")
            elif "1_plus_hr" in market or "hrr" in market and "hr" in market:
                # HRR = Hits+Runs+RBIs (PrizePicks combo)
                if "hrr" in market:
                    stat_val = (g.get("hits") or 0) + (g.get("runs") or 0) + (g.get("rbi") or 0)
                else:
                    stat_val = g.get("hr")
            elif "1_plus_rbi" in market or "rbis" in market:
                stat_val = g.get("rbi")
            elif "1_plus_run" in market or "runs" in market:
                stat_val = g.get("runs")
            elif "k_over" in market or "_k_" in market:
                stat_val = g.get("k")
            elif "er_under" in market:
                stat_val = g.get("er")
            elif "pts_over" in market:
                stat_val = g.get("pts")
            elif "reb_over" in market:
                stat_val = g.get("reb")
            elif "ast_over" in market:
                stat_val = g.get("ast")
            if stat_val is None or line is None: continue
            # Game-level "no data" check: if all stats are 0 and pa=0, game probably not played
            if g.get("pa") == 0 and g.get("min") in (None, 0):
                continue
            if is_under:
                if stat_val < line: return "won"
                if stat_val == line: return "push"
                return "lost"
            else:
                # over / plus
                if stat_val > line: return "won"
                if stat_val == line and "plus" in market: return "won"   # "1+ hit" wins on exactly 1
                if stat_val == line: return "push"
                return "lost"
    return None


def run() -> Dict[str, Any]:
    top_plays = _load(os.path.join(DATA_DIR, "todays_top_plays.json"))
    existing = _load(OUT)
    history: List[Dict[str, Any]] = existing.get("history") or []

    # Build set of existing pick_ids
    existing_ids = {p.get("pick_id") for p in history}

    # Add today's top N as new locks (skip duplicates from same day)
    new_locks = _build_new_locks(top_plays)
    n_added = 0
    for lk in new_locks:
        if lk["pick_id"] not in existing_ids:
            history.append(lk)
            existing_ids.add(lk["pick_id"])
            n_added += 1

    # Always regenerate rationales (derivative content; latest logic always applies)
    for pick in history:
        pick["rationale"] = _build_rationale(pick)

    # Attempt to settle any pending entries
    n_newly_settled = 0
    for pick in history:
        if pick.get("settled"): continue
        result = _try_settle_pick(pick)
        if result:
            pick["settled"] = True
            pick["result"] = result
            pick["settled_at"] = dt.datetime.now().isoformat(timespec="seconds")
            # Compute payout units
            decimal_odds = _american_to_decimal(pick.get("fair_american"))
            stake = pick.get("unit_size_quarter_kelly") or 0.02
            if result == "won" and decimal_odds:
                pick["payout_units"] = round(stake * (decimal_odds - 1), 4)
            elif result == "lost":
                pick["payout_units"] = round(-stake, 4)
            else:   # push
                pick["payout_units"] = 0.0
            n_newly_settled += 1

    # Cap history
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # Aggregate stats
    settled = [p for p in history if p.get("settled")]
    pending = [p for p in history if not p.get("settled")]
    wins = sum(1 for p in settled if p["result"] == "won")
    losses = sum(1 for p in settled if p["result"] == "lost")
    pushes = sum(1 for p in settled if p["result"] == "push")
    n_decided = wins + losses
    hit_rate = round(wins / n_decided, 4) if n_decided else None
    net_units = round(sum((p.get("payout_units") or 0) for p in settled), 3)
    total_risked = round(sum((p.get("unit_size_quarter_kelly") or 0)
                              for p in settled if p["result"] != "push"), 3)
    roi_pct = round(net_units / total_risked * 100, 2) if total_risked > 0 else None

    # Per-sport breakdown
    by_sport: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        sp = p.get("sport") or "?"
        b = by_sport.setdefault(sp, {"wins": 0, "losses": 0, "pushes": 0, "net_units": 0})
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for sp, b in by_sport.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # Per-market-family breakdown
    by_family: Dict[str, Dict[str, Any]] = {}
    for p in settled:
        fam = p.get("market_family") or "?"
        b = by_family.setdefault(fam, {"wins": 0, "losses": 0, "pushes": 0, "net_units": 0})
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for fam, b in by_family.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # Last 7-day rolling
    today = dt.date.today()
    last_7 = [p for p in settled
              if (today - dt.date.fromisoformat(p["date"])).days <= 7]
    l7_wins = sum(1 for p in last_7 if p["result"] == "won")
    l7_losses = sum(1 for p in last_7 if p["result"] == "lost")
    l7_net = round(sum((p.get("payout_units") or 0) for p in last_7), 3)

    # Today's locks (the new ones just recorded for today)
    todays_locks = [p for p in history if p["date"] == _today_date_str()]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_locks_per_day": N_LOCKS_PER_DAY,
        "total_locks": len(history),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_added_this_run": n_added,
        "n_newly_settled_this_run": n_newly_settled,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "net_units": net_units,
        "total_risked_units": total_risked,
        "roi_pct": roi_pct,
        "last_7_days": {
            "wins": l7_wins,
            "losses": l7_losses,
            "net_units": l7_net,
            "hit_rate": round(l7_wins / max(1, l7_wins + l7_losses), 4) if (l7_wins + l7_losses) > 0 else None,
        },
        "by_sport": by_sport,
        "by_market_family": by_family,
        "todays_locks": todays_locks,
        "history": history,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Locks of the Day: {p['total_locks']} total ({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  This run: +{p['n_added_this_run']} new, +{p['n_newly_settled_this_run']} newly settled")
    if p["hit_rate"] is not None:
        print(f"  All-time: {p['wins']}-{p['losses']}-{p['pushes']} ({p['hit_rate']*100:.1f}%) | net {p['net_units']:+.2f}u | ROI {p['roi_pct']:+.1f}%")
    if p["last_7_days"]["hit_rate"] is not None:
        l7 = p["last_7_days"]
        print(f"  Last 7d: {l7['wins']}-{l7['losses']} ({l7['hit_rate']*100:.1f}%) | net {l7['net_units']:+.2f}u")
    print(f"\nToday's locks ({len(p['todays_locks'])}):")
    for lk in p["todays_locks"]:
        st = "PENDING" if not lk["settled"] else lk["result"].upper()
        print(f"  [{st:7s}] {lk['sport']:7s} {(lk['player_or_matchup'] or '?')[:25]:25s} "
              f"{(lk['market'] or '?')[:25]:25s} p={lk['prob']*100:.0f}% "
              f"edge=+{lk.get('edge_pct',0):.1f}% qK={lk.get('unit_size_quarter_kelly',0):.3f}u")
