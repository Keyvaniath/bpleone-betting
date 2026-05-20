"""
EdgeStat -- in-game prop lock detector.

For each pending pick in all_picks_ledger that involves an IN-PROGRESS
game, computes whether the prop is:
   LOCKED_WON     mathematically clinched (e.g., 1+ hit pick with 2 hits already)
   LOCKED_LOST    mathematically failed (e.g., UNDER 3.5 already at 4)
   CASHING        likely to win (>= 80% live probability)
   SWEATING       at risk (40-60% live)
   ON_TRACK       leading the line in our direction
   AT_RISK        behind, recovery possible

When a prop is LOCKED_WON, Brandon can cash out at the book or just
hold. When LOCKED_LOST, hedge opportunities surface.

Pulls live state from data/live_player_stats.json (if available) +
data/today.json (for game state / inning).

Output: data/in_game_locks.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "in_game_locks.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _classify_player_prop(pick, live_stats):
    """Status for a player prop given live state."""
    name = (pick.get("player_or_matchup") or "").lower()
    market = (pick.get("market") or "").lower()
    line_m = re.search(r"(\d+(?:\.\d+)?)", market)
    if not line_m: return None
    line = float(line_m.group(1))
    is_under = "under" in market

    # Find player in live data
    for p in (live_stats.get("players") or []):
        if (p.get("name") or "").lower() != name: continue
        # Determine stat
        stat = None
        if "hit" in market and "1_plus" in market: stat = p.get("hits")
        elif "2_plus_hits" in market: stat = p.get("hits")
        elif "total_bases" in market: stat = p.get("tb")
        elif "hrr" in market: stat = (p.get("hits") or 0) + (p.get("runs") or 0) + (p.get("rbi") or 0)
        elif "1_plus_hr" in market: stat = p.get("hr")
        elif "1_plus_rbi" in market: stat = p.get("rbi")
        elif "1_plus_run" in market: stat = p.get("runs")
        elif "k_over" in market: stat = p.get("k")
        elif "er_under" in market: stat = p.get("er")
        if stat is None: continue

        # Has the player's game ended?
        game_done = p.get("game_state") in ("post", "final", "Final")
        if game_done:
            if is_under:
                return {"status": "LOCKED_WON" if stat < line else "LOCKED_LOST",
                         "stat_val": stat, "line": line, "detail": f"Final {stat} vs line {line}"}
            else:
                won = stat > line or (stat == line and "plus" in market)
                return {"status": "LOCKED_WON" if won else "LOCKED_LOST",
                         "stat_val": stat, "line": line, "detail": f"Final {stat} vs line {line}"}

        # Mid-game logic
        if is_under:
            if stat >= line:
                return {"status": "LOCKED_LOST", "stat_val": stat, "line": line,
                         "detail": f"Already at {stat}, line {line} -- broken"}
            margin = line - stat
            # If 8th inning+ and stat at 0, very likely won
            return {"status": "ON_TRACK" if margin >= 1 else "SWEATING",
                     "stat_val": stat, "line": line, "margin": margin,
                     "detail": f"{stat} so far, {margin:.1f} cushion to {line}"}
        else:
            # OVER / plus
            if stat > line or (stat == line and "plus" in market):
                return {"status": "LOCKED_WON", "stat_val": stat, "line": line,
                         "detail": f"Cleared at {stat}"}
            need = line - stat + (0 if "plus" in market else 1)
            return {"status": "AT_RISK" if need > 1 else "ON_TRACK",
                     "stat_val": stat, "line": line, "need": need,
                     "detail": f"{stat} so far, need {need:.1f} more"}
    return None


def _classify_game_market(pick, today):
    """Status for an ML / total pick given live state."""
    matchup = (pick.get("player_or_matchup") or "").lower()
    market = (pick.get("market") or "").lower()
    for g in (today.get("games") or []):
        g_mu = (g.get("matchup") or "").lower()
        if matchup not in g_mu and g_mu not in matchup: continue
        home_s = g.get("home_score") or 0
        away_s = g.get("away_score") or 0
        total = home_s + away_s
        state = g.get("state") or g.get("status") or "pre"
        final = state in ("post", "final", "Final", "Full Time") or "complete" in str(state).lower()
        if "over_" in market or "under_" in market:
            line_m = re.search(r"(\d+(?:\.\d+)?)", market)
            if not line_m: return None
            line = float(line_m.group(1))
            is_over = "over_" in market
            if final:
                if is_over:
                    if total > line: return {"status": "LOCKED_WON", "detail": f"Final {total} > {line}"}
                    if total == line: return {"status": "LOCKED_PUSH", "detail": f"Push {total}"}
                    return {"status": "LOCKED_LOST", "detail": f"Final {total} < {line}"}
                else:
                    if total < line: return {"status": "LOCKED_WON", "detail": f"Final {total} < {line}"}
                    if total == line: return {"status": "LOCKED_PUSH", "detail": f"Push {total}"}
                    return {"status": "LOCKED_LOST", "detail": f"Final {total} > {line}"}
            # In progress
            inning = g.get("inning") or 0
            if is_over:
                if total > line: return {"status": "LOCKED_WON", "detail": f"Cleared at {total}"}
                if inning >= 7 and total < line - 3:
                    return {"status": "AT_RISK", "detail": f"{total} at I{inning}, need {line-total:.1f}"}
                return {"status": "ON_TRACK", "detail": f"{total} thru I{inning}"}
            else:
                if total > line: return {"status": "LOCKED_LOST", "detail": f"Already {total} > {line}"}
                cushion = line - total
                return {"status": "ON_TRACK" if cushion >= 2 else "SWEATING",
                         "detail": f"{total} thru I{inning}, cushion {cushion:.1f}"}
        if "ml_home" in market or "ml_away" in market:
            side = "HOME" if "ml_home" in market else "AWAY"
            if final:
                winner_is_home = home_s > away_s
                won = (side == "HOME") == winner_is_home
                return {"status": "LOCKED_WON" if won else "LOCKED_LOST",
                         "detail": f"Final: {away_s}-{home_s}"}
            lead = (home_s - away_s) if side == "HOME" else (away_s - home_s)
            inning = g.get("inning") or 0
            if lead >= 4 and inning >= 8: return {"status": "ON_TRACK", "detail": f"Up by {lead} at I{inning}"}
            if lead >= 1: return {"status": "ON_TRACK", "detail": f"Lead by {lead}"}
            if lead == 0: return {"status": "SWEATING", "detail": f"Tied {home_s}-{home_s}"}
            return {"status": "AT_RISK", "detail": f"Down by {-lead}"}
    return None


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    live_stats = _load(os.path.join(DATA_DIR, "live_player_stats.json"))
    ledger = _load(os.path.join(DATA_DIR, "all_picks_ledger.json"))
    today_str = dt.date.today().isoformat()

    picks_today = [p for p in (ledger.get("picks") or [])
                    if p.get("date") == today_str and not p.get("settled")]

    results: List[Dict[str, Any]] = []
    for p in picks_today:
        market = (p.get("market") or "").lower()
        if any(k in market for k in ("ml_home", "ml_away", "over_", "under_")) and "pp_" not in market:
            r = _classify_game_market(p, today)
        else:
            r = _classify_player_prop(p, live_stats)
        if r:
            results.append({**p, **r})

    # Tier counts
    from collections import Counter
    counts = Counter(r.get("status") for r in results)

    locked_won = [r for r in results if r.get("status") == "LOCKED_WON"]
    locked_lost = [r for r in results if r.get("status") == "LOCKED_LOST"]
    on_track = [r for r in results if r.get("status") == "ON_TRACK"]
    sweating = [r for r in results if r.get("status") in ("SWEATING", "AT_RISK")]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_picks_today_pending": len(picks_today),
        "n_classified": len(results),
        "status_counts": dict(counts),
        "locked_won": locked_won,
        "locked_lost": locked_lost,
        "on_track": on_track,
        "sweating": sweating,
        "all": results,
        "note": ("In-game lock detector. LOCKED_WON = cash out / hold. "
                  "LOCKED_LOST = move on. ON_TRACK = leading. SWEATING / "
                  "AT_RISK = consider hedge if book offers contra-side "
                  "at favorable price."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"In-game locks: {p['n_classified']} picks classified ({p['status_counts']})")
    for r in p.get("locked_won", [])[:5]:
        print(f"  WON  {r.get('source','?'):20s} {r.get('player_or_matchup','?')[:25]:25s} {r.get('market','?')[:25]:25s} -- {r.get('detail','')}")
    for r in p.get("on_track", [])[:5]:
        print(f"  ON_TRACK {r.get('player_or_matchup','?')[:25]:25s} -- {r.get('detail','')}")
    for r in p.get("sweating", [])[:5]:
        print(f"  AT_RISK  {r.get('player_or_matchup','?')[:25]:25s} -- {r.get('detail','')}")
