"""
EdgeStat -- CLV (closing line value) tracker for Locks of the Day.

Compares the line at LOCK RECORDING time vs the closing/latest line
for each pick. Positive CLV means the market moved TOWARD our pick
(book agrees more with us than when we recorded). Negative CLV means
the book moved AWAY from our pick (we were ahead of the market wrongly).

CLV correlates 1:1 with long-run ROI for sharp bettors. Even before any
locks settle (W/L), CLV gives an early signal of whether the model is
finding real value or chasing phantom edges.

Method:
  For each game-line lock (ML_HOME / ML_AWAY / OVER_X / UNDER_X):
    1. Find the game in data/live_clv.json by matchup substring
    2. Get the opening snapshot (or earliest)
    3. Get the closing snapshot (state="post") or latest available
    4. Compute implied probabilities for the side we picked at both times
    5. CLV_pp = closing_implied - opening_implied

  Player-prop locks (PP_batter, etc.) are skipped -- PrizePicks lines
  don't move continuously like books, so CLV is not meaningful.

Output: data/locks_clv.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "locks_clv.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american_to_implied(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def _find_game_in_clv(matchup: str, clv_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Search live_clv for a game matching the lock's matchup string."""
    if not matchup: return None
    target = matchup.lower().replace(" ", "").replace("@", "")
    games = clv_data.get("games") or {}
    for game_key, g in games.items():
        gm = (g.get("matchup") or "").lower().replace(" ", "").replace("@", "")
        if target in gm or gm in target:
            return g
        # Also try matching by game_key
        if target in game_key.lower().replace("_", ""):
            return g
    return None


def _opening_and_closing(game: Dict[str, Any]) -> Dict[str, Any]:
    """Return opening + closing snapshots for a game."""
    snaps = game.get("snapshots") or []
    if not snaps: return {"opening": None, "closing": None}
    # Prefer explicit opening/closing if set
    opening = game.get("opening") or snaps[0]
    # Closing = last snapshot in "pre" state (just before first pitch) or
    # final post-game snapshot
    pre_snaps = [s for s in snaps if s.get("state") == "pre"]
    closing = (pre_snaps[-1] if pre_snaps else
               (game.get("closing") or snaps[-1]))
    return {"opening": opening, "closing": closing}


def _compute_clv_for_lock(lock: Dict[str, Any], clv_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Compute CLV for one lock. Returns None if not applicable."""
    market = (lock.get("market") or "").lower()
    # Only game-level markets get CLV
    if not any(k in market for k in ("ml_home", "ml_away", "over_", "under_")):
        return None
    # Skip if it's a player-prop sub-market (e.g. PP over/under)
    if any(k in market for k in ("pp_", "_vs_sp", "_situational")):
        return None
    matchup = lock.get("player_or_matchup")
    game = _find_game_in_clv(matchup, clv_data)
    if not game:
        return {"pick_id": lock["pick_id"], "matchup": matchup, "market": market,
                "status": "no_clv_data"}

    snaps = _opening_and_closing(game)
    opening = snaps["opening"]
    closing = snaps["closing"]
    if not opening or not closing:
        return {"pick_id": lock["pick_id"], "matchup": matchup, "market": market,
                "status": "insufficient_snapshots"}

    # Determine the side we picked + extract opening/closing American odds for that side
    if "ml_home" in market:
        open_am = opening.get("home_ml")
        close_am = closing.get("home_ml")
        side = "HOME"
    elif "ml_away" in market:
        open_am = opening.get("away_ml")
        close_am = closing.get("away_ml")
        side = "AWAY"
    elif "over_" in market:
        open_am = opening.get("total_over")
        close_am = closing.get("total_over")
        side = "OVER"
    elif "under_" in market:
        open_am = opening.get("total_under")
        close_am = closing.get("total_under")
        side = "UNDER"
    else:
        return None

    open_implied = _american_to_implied(open_am)
    close_implied = _american_to_implied(close_am)
    if open_implied is None or close_implied is None:
        return {"pick_id": lock["pick_id"], "matchup": matchup, "market": market,
                "status": "missing_odds"}

    clv_pp = (close_implied - open_implied) * 100   # percentage points

    return {
        "pick_id": lock["pick_id"],
        "matchup": matchup,
        "market": market,
        "side": side,
        "sport": lock.get("sport"),
        "source": lock.get("source"),
        "opening_american": open_am,
        "opening_implied_pct": round(open_implied * 100, 2),
        "closing_american": close_am,
        "closing_implied_pct": round(close_implied * 100, 2),
        "clv_pp": round(clv_pp, 2),
        "clv_direction": "BEAT_CLOSE" if clv_pp > 0 else ("LOST_CLOSE" if clv_pp < 0 else "FLAT"),
        "status": "settled" if closing.get("state") == "post" else "live_estimate",
    }


def run() -> Dict[str, Any]:
    locks_hist = _load(os.path.join(DATA_DIR, "locks_history.json"))
    clv_data = _load(os.path.join(DATA_DIR, "live_clv.json"))
    history = locks_hist.get("history") or []

    results: List[Dict[str, Any]] = []
    for lk in history:
        r = _compute_clv_for_lock(lk, clv_data)
        if r is not None:
            results.append(r)

    # Aggregate
    with_clv = [r for r in results if "clv_pp" in r]
    n_beat = sum(1 for r in with_clv if r["clv_pp"] > 0)
    n_flat = sum(1 for r in with_clv if r["clv_pp"] == 0)
    n_lost = sum(1 for r in with_clv if r["clv_pp"] < 0)
    avg_clv = round(sum(r["clv_pp"] for r in with_clv) / len(with_clv), 2) if with_clv else None

    # Per-source CLV
    by_source: Dict[str, Dict[str, Any]] = {}
    for r in with_clv:
        s = r.get("source") or "?"
        b = by_source.setdefault(s, {"n": 0, "sum_clv": 0.0, "beat": 0, "lost": 0})
        b["n"] += 1
        b["sum_clv"] += r["clv_pp"]
        if r["clv_pp"] > 0: b["beat"] += 1
        elif r["clv_pp"] < 0: b["lost"] += 1
    for s, b in by_source.items():
        b["avg_clv_pp"] = round(b["sum_clv"] / b["n"], 2) if b["n"] > 0 else None
        b["beat_rate"] = round(b["beat"] / b["n"], 3) if b["n"] > 0 else None
        del b["sum_clv"]

    # Top CLV winners + losers
    top_clv = sorted(with_clv, key=lambda r: -r["clv_pp"])[:5]
    worst_clv = sorted(with_clv, key=lambda r: r["clv_pp"])[:5]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_locks_total": len(history),
        "n_locks_with_clv": len(with_clv),
        "n_beat_close": n_beat,
        "n_lost_close": n_lost,
        "n_flat": n_flat,
        "avg_clv_pp": avg_clv,
        "beat_close_rate": round(n_beat / len(with_clv), 3) if with_clv else None,
        "by_source": by_source,
        "top_clv_winners": top_clv,
        "worst_clv_losers": worst_clv,
        "all_clv": results,
        "note": ("CLV (closing line value) is the gap between the market line at "
                  "the time we picked vs the closing line. Positive CLV means the "
                  "market moved TOWARD our pick -- a leading indicator of long-run "
                  "ROI even before bets settle."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Locks CLV: {p['n_locks_with_clv']} of {p['n_locks_total']} eligible for CLV")
    if p["avg_clv_pp"] is not None:
        print(f"  Avg CLV: {p['avg_clv_pp']:+.2f}pp | Beat-close rate: {p['beat_close_rate']*100:.1f}%")
        print(f"  Beat: {p['n_beat_close']} | Lost: {p['n_lost_close']} | Flat: {p['n_flat']}")
    print(f"\n  Per-source:")
    for src, b in sorted(p["by_source"].items(), key=lambda kv: -kv[1]["n"])[:5]:
        print(f"    {src:30s}  n={b['n']:3d}  avg CLV {b['avg_clv_pp']:+.2f}pp  beat={b['beat_rate']*100:.0f}%")
    if p["top_clv_winners"]:
        print(f"\n  Top 3 CLV winners:")
        for r in p["top_clv_winners"][:3]:
            print(f"    {(r['matchup'] or '?')[:30]:30s} {r.get('side','?'):6s} {r['opening_implied_pct']:.1f}% -> {r['closing_implied_pct']:.1f}% (+{r['clv_pp']:.1f}pp)")
