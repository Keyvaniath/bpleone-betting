"""
EdgeStat -- live in-game status tracker for today's locks.

While games are in progress, monitors each pending lock from
locks_history.json (today's only) and projects the CURRENT probability
of cashing given live game state.

For game-level markets (ML / OVER / UNDER):
  - Read live score + inning from today.json / nba_state / nhl_state
  - For ML: blend pregame model with current score differential
  - For OVER/UNDER: extrapolate current total run-rate vs remaining time

For player-prop markets:
  - Lookup current player live stats (if available)
  - Compute progress vs line (e.g. "1+ hit" with 0 hits in 2 ABs after 4 innings = ON_TRACK)

Status taxonomy:
  WON       Mathematically clinched (can't lose)
  LOST      Already failed (line broken)
  ON_TRACK  Live state above pregame projection
  AT_RISK   Live state below pregame projection
  PENDING   No live state available yet (pregame)

Output: data/live_locks_status.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "live_locks_status.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _today_date_str() -> str:
    return dt.date.today().isoformat()


def _project_ml_status(lock: Dict[str, Any], game: Dict[str, Any], market: str) -> Dict[str, Any]:
    """Status for ML_HOME / ML_AWAY market given live game state."""
    home_score = game.get("home_score") or 0
    away_score = game.get("away_score") or 0
    state = game.get("state") or game.get("status") or ""
    is_final = state in ("post", "final", "Full Time", "Final") or "complete" in str(state).lower()

    side = "HOME" if "ml_home" in market.lower() else "AWAY"
    if is_final:
        winner_is_home = home_score > away_score
        return {"status": "WON" if (side == "HOME") == winner_is_home else "LOST",
                 "live_note": f"Final: {away_score}-{home_score}"}

    # Compute current lead vs side
    if side == "HOME":
        lead = home_score - away_score
    else:
        lead = away_score - home_score

    inning = game.get("inning") or game.get("period")
    if lead >= 5 and inning and (isinstance(inning, int) and inning >= 7):
        return {"status": "ON_TRACK", "live_note": f"Up by {lead} at I{inning}"}
    elif lead >= 1:
        return {"status": "ON_TRACK", "live_note": f"Lead by {lead}"}
    elif lead == 0:
        return {"status": "PENDING", "live_note": f"Tied {home_score}-{home_score}"}
    else:
        return {"status": "AT_RISK", "live_note": f"Down by {-lead}"}


def _project_total_status(lock: Dict[str, Any], game: Dict[str, Any], market: str) -> Dict[str, Any]:
    """Status for OVER_X / UNDER_X total market given live game state."""
    home_score = game.get("home_score") or 0
    away_score = game.get("away_score") or 0
    total = home_score + away_score
    state = game.get("state") or game.get("status") or ""
    is_final = state in ("post", "final", "Full Time", "Final") or "complete" in str(state).lower()

    line_m = re.search(r"(\d+(?:\.\d+)?)", market)
    if not line_m: return {"status": "PENDING", "live_note": "Could not parse line"}
    line = float(line_m.group(1))
    is_over = "over" in market.lower()

    if is_final:
        if is_over:
            if total > line: return {"status": "WON", "live_note": f"Final {total} > {line}"}
            if total == line: return {"status": "PUSH", "live_note": f"Push {total}"}
            return {"status": "LOST", "live_note": f"Final {total} < {line}"}
        else:
            if total < line: return {"status": "WON", "live_note": f"Final {total} < {line}"}
            if total == line: return {"status": "PUSH", "live_note": f"Push {total}"}
            return {"status": "LOST", "live_note": f"Final {total} > {line}"}

    # In-progress: project finishing
    inning = game.get("inning") or 0
    if isinstance(inning, str): inning = 0
    if is_over:
        if total > line: return {"status": "ON_TRACK", "live_note": f"Already {total} > {line}"}
        if inning >= 7 and total < line - 2:
            return {"status": "AT_RISK", "live_note": f"{total} at I{inning}, need {line - total + 0.5:.1f}+"}
        return {"status": "PENDING", "live_note": f"{total} thru I{inning}"}
    else:  # UNDER
        if total > line: return {"status": "LOST", "live_note": f"Already {total} > {line}"}
        if total == line: return {"status": "AT_RISK", "live_note": f"At line {total}"}
        if inning >= 7 and (line - total) < 1:
            return {"status": "AT_RISK", "live_note": f"{total} at I{inning}, only {line-total:.1f} cushion"}
        return {"status": "ON_TRACK", "live_note": f"{total} thru I{inning}, cushion {line-total:.1f}"}


def _project_player_status(lock: Dict[str, Any]) -> Dict[str, Any]:
    """Status for player-prop locks given live player stats (if available)."""
    # live_props.json or live_player_stats has per-batter cumulative stats
    live = _load(os.path.join(DATA_DIR, "live_player_stats.json"))
    target_name = (lock.get("player_or_matchup") or "").lower()
    market = (lock.get("market") or "").lower()
    line_m = re.search(r"(\d+(?:\.\d+)?)", market)
    line = float(line_m.group(1)) if line_m else None
    is_under = "under" in market

    # If no live data file exists, return PENDING
    if not live: return {"status": "PENDING", "live_note": "No live data yet"}
    players = live.get("players") or []
    for p in players:
        if (p.get("name") or "").lower() != target_name: continue
        # Match stat to market
        stat_val = None
        if "hit" in market: stat_val = p.get("hits")
        elif "hr" in market: stat_val = p.get("hr")
        elif "rbi" in market: stat_val = p.get("rbi")
        elif "run" in market: stat_val = p.get("runs")
        elif "tb" in market or "total_bases" in market: stat_val = p.get("tb")
        elif "k" in market: stat_val = p.get("k")
        if stat_val is None or line is None:
            return {"status": "PENDING", "live_note": "No matching live stat"}
        # Game state
        is_done = p.get("game_state") in ("post", "final", "Final")
        if is_done:
            if is_under:
                if stat_val < line: return {"status": "WON", "live_note": f"Final {stat_val} < {line}"}
                return {"status": "LOST", "live_note": f"Final {stat_val} >= {line}"}
            else:
                if stat_val > line: return {"status": "WON", "live_note": f"Final {stat_val} > {line}"}
                if stat_val == line and "plus" in market: return {"status": "WON", "live_note": f"At line {stat_val}"}
                return {"status": "LOST", "live_note": f"Final {stat_val} < {line}"}
        # In-progress
        if is_under:
            if stat_val >= line: return {"status": "LOST", "live_note": f"Already {stat_val} >= {line}"}
            return {"status": "ON_TRACK", "live_note": f"{stat_val} so far, cushion {line - stat_val:.1f}"}
        else:
            if stat_val > line: return {"status": "WON", "live_note": f"Cleared at {stat_val}"}
            if stat_val == line and "plus" in market: return {"status": "WON", "live_note": f"At line {stat_val}"}
            need = line - stat_val
            return {"status": "AT_RISK" if need > 1 else "PENDING",
                     "live_note": f"{stat_val} so far, need {need:.1f} more"}
    return {"status": "PENDING", "live_note": "Player not in live data"}


def _project_lock_status(lock: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch to ML / total / player based on market."""
    sport = (lock.get("sport") or "").upper()
    market = (lock.get("market") or "").lower()
    matchup = (lock.get("player_or_matchup") or "").lower()

    # Find live game by matchup
    state_files = {
        "MLB": "today.json", "MLB-PP": "today.json",
        "NBA": "nba_state.json", "NHL": "nhl_state.json",
        "WNBA": "wnba_state.json", "MLS": "mls_state.json",
        "EPL": "epl_state.json", "UCL": "ucl_state.json",
    }
    state_file = state_files.get(sport)
    if not state_file: return {"status": "PENDING", "live_note": "Unsupported sport"}
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or []

    # Player props -> player live stats (or PENDING)
    if any(k in market for k in ("pp_batter", "1_plus_hit", "1_plus_hr", "1_plus_rbi",
                                   "1_plus_run", "2_plus_hits", "total_bases", "hrr",
                                   "k_over", "er_under", "pts_over", "reb_over", "ast_over")):
        return _project_player_status(lock)

    # Game-level markets: find game
    for g in games:
        g_mu = (g.get("matchup") or g.get("name") or "").lower()
        if matchup not in g_mu and g_mu not in matchup: continue
        if "ml_home" in market or "ml_away" in market:
            return _project_ml_status(lock, g, market)
        if "over_" in market or "under_" in market:
            return _project_total_status(lock, g, market)
    return {"status": "PENDING", "live_note": "Game not found in state file"}


def run() -> Dict[str, Any]:
    locks_hist = _load(os.path.join(DATA_DIR, "locks_history.json"))
    history = locks_hist.get("history") or []
    today_str = _today_date_str()

    # Only process today's pending locks
    todays_locks = [L for L in history if L.get("date") == today_str and not L.get("settled")]

    enriched = []
    counts = {"WON": 0, "LOST": 0, "PUSH": 0, "ON_TRACK": 0, "AT_RISK": 0, "PENDING": 0}
    for lk in todays_locks:
        status = _project_lock_status(lk)
        enriched.append({
            **lk,
            "live_status": status["status"],
            "live_note": status.get("live_note", ""),
        })
        counts[status["status"]] = counts.get(status["status"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "date": today_str,
        "n_locks_today": len(todays_locks),
        "status_counts": counts,
        "locks": enriched,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Live Locks Status: {p['n_locks_today']} locks today")
    print(f"  Counts: {p['status_counts']}")
    print(f"\n  Individual:")
    for lk in p["locks"]:
        st = lk["live_status"]
        marker = {"WON": "[W]", "LOST": "[L]", "ON_TRACK": "[+]",
                   "AT_RISK": "[!]", "PUSH": "[=]", "PENDING": "[?]"}.get(st, "[?]")
        print(f"  {marker} {lk['sport']:7s} {(lk['player_or_matchup'] or '?')[:25]:25s} "
              f"{(lk['market'] or '?')[:30]:30s} {st:9s} -- {lk['live_note']}")
