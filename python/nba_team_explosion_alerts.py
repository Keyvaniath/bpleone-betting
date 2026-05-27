"""
EdgeStat -- NBA team explosion alerts.

NBA analog to mlb_offensive_explosion_alerts but for team-level scoring.
Surfaces teams projecting for an offensive explosion night:
  - TT_OVER (team total STRONG_OVER lean from nba_team_total_edge)
  - HIGH_PACE (pace projection above league avg)
  - SOFT_DEFENSE (opp defensive rating in bottom tier)
  - HOME_BOOST (home team in friendly environment)
  - RACE_EARLY_PTS (favored in race-to-points markets)
  - HALF_TOTAL_OVER (half total props lean OVER)

EXPLOSION_ELITE = 5+ signals; STRONG = 3-4.

Output: data/nba_team_explosion_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_team_explosion_alerts.json")


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


def run() -> Dict[str, Any]:
    tt_edge = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))
    race = _load(os.path.join(DATA_DIR, "nba_race_to_points.json"))
    half_total = _load(os.path.join(DATA_DIR, "nba_half_total_props.json"))
    game_total = _load(os.path.join(DATA_DIR, "nba_game_total_alts.json"))

    # Index TT edge by (matchup, side)
    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt_edge.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        tt_idx[key] = r

    # Pace by matchup
    pace_idx: Dict[str, Dict[str, Any]] = {}
    for g in (pace.get("games") or pace.get("rows") or []):
        if not isinstance(g, dict): continue
        pace_idx[g.get("matchup", "")] = g

    # Race-to-points favorites
    race_fav: Dict[str, str] = {}  # matchup -> favored team
    for r in (race.get("rows") or []):
        if not isinstance(r, dict): continue
        # Highest p favorite for that matchup
        m = r.get("matchup", "")
        p_team = _safe(r.get("p"))
        existing = race_fav.get(m)
        if not existing or p_team > _safe(race_fav.get(m + "_p", 0)):
            race_fav[m] = r.get("team", "")
            race_fav[m + "_p"] = p_team

    # Half totals OVER by matchup
    half_over: Dict[str, bool] = {}
    for r in (half_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            half_over[r.get("matchup", "")] = True

    # Build alerts per side
    alerts: List[Dict[str, Any]] = []
    seen: set = set()

    for r in (tt_edge.get("rows") or []):
        if not isinstance(r, dict): continue
        matchup = r.get("matchup", "")
        side = (r.get("side", "") or "").upper()
        team = r.get("team", "")
        if not matchup or not side: continue
        seen_key = f"{matchup}|{side}|{team}"
        if seen_key in seen: continue
        seen.add(seen_key)

        signals: Dict[str, int] = {}

        # 1. TT direction
        tt_dir = (r.get("direction") or "").upper()
        signals["TT_OVER"] = 1 if tt_dir in ("STRONG_OVER", "LEAN_OVER") else 0

        # 2. Pace
        pace_game = pace_idx.get(matchup, {})
        pace_val = _safe(pace_game.get("projected_pace") or pace_game.get("pace"))
        signals["HIGH_PACE"] = 1 if pace_val >= 102.5 else 0

        # 3. Soft defense (opp DRtg bottom tier)
        opp_drtg = _safe(r.get("opp_drtg") or pace_game.get("opp_drtg"))
        signals["SOFT_DEFENSE"] = 1 if opp_drtg >= 116.0 else 0  # bottom 25% league avg ~114

        # 4. Home boost
        signals["HOME_BOOST"] = 1 if side == "HOME" and tt_dir in ("STRONG_OVER", "LEAN_OVER") else 0

        # 5. Race favorite
        signals["RACE_EARLY_PTS"] = 1 if race_fav.get(matchup) == team else 0

        # 6. Half total OVER
        signals["HALF_TOTAL_OVER"] = 1 if half_over.get(matchup) else 0

        positive_count = sum(1 for v in signals.values() if v == 1)
        if positive_count < 3: continue

        tier = "EXPLOSION_ELITE" if positive_count >= 5 else "EXPLOSION_STRONG"

        alerts.append({
            "matchup": matchup,
            "team": team,
            "side": side,
            "tt_direction": tt_dir,
            "projected_pace": round(pace_val, 1) if pace_val else None,
            "opp_drtg": round(opp_drtg, 1) if opp_drtg else None,
            "n_positive_signals": positive_count,
            "signals": signals,
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "EXPLOSION_ELITE"),
        "method_note": "NBA team-level analog to mlb_offensive_explosion_alerts. "
                       "3+ aligned signals: TT_OVER, HIGH_PACE (>=102.5), "
                       "SOFT_DEFENSE (opp DRtg>=116), HOME_BOOST, RACE_EARLY_PTS, "
                       "HALF_TOTAL_OVER. EXPLOSION_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_explosions": [a for a in alerts if a["tier"] == "EXPLOSION_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-team-explosion] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
