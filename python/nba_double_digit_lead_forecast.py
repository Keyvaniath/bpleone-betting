"""
EdgeStat -- NBA double-digit halftime lead forecast.

Predicts which NBA teams are likely to lead by 10+ points at halftime,
based on:
  - Team explosion alert (5+ signals)
  - Team total OVER STRONG lean
  - Opp team total UNDER lean (or weak defensive matchup)
  - Pace advantage
  - Multiple player LOCKs

Useful for half-time spread bets, "team to lead at half" props.

Output: data/nba_double_digit_lead_forecast.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_double_digit_lead_forecast.json")


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
    team_expl = _load(os.path.join(DATA_DIR, "nba_team_explosion_alerts.json"))
    team_conf = _load(os.path.join(DATA_DIR, "nba_team_confluence_score.json"))
    half_total = _load(os.path.join(DATA_DIR, "nba_half_total_props.json"))
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))
    player_conf = _load(os.path.join(DATA_DIR, "nba_player_confluence_score.json"))

    # Team explosion by (matchup, side)
    expl_idx: Dict[str, Dict[str, Any]] = {}
    for a in (team_expl.get("alerts") or []):
        if not isinstance(a, dict): continue
        key = f"{a.get('matchup','')}|{(a.get('side','') or '').upper()}"
        expl_idx[key] = a

    # Team confluence
    team_idx: Dict[str, Dict[str, Any]] = {}
    for r in (team_conf.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        team_idx[key] = r

    # Half total OVER by matchup
    half_over: Dict[str, bool] = {}
    for r in (half_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "OVER" in ec:
            half_over[r.get("matchup", "")] = True

    # Pace by matchup
    pace_by_matchup: Dict[str, float] = {}
    for g in (pace.get("games") or pace.get("rows") or []):
        if isinstance(g, dict):
            pace_by_matchup[g.get("matchup", "")] = _safe(
                g.get("projected_pace") or g.get("pace"), 100.0)

    # Player LOCKs by (matchup, team)
    player_locks_by_team: Dict[str, int] = {}
    for r in (player_conf.get("rows") or []):
        if not isinstance(r, dict): continue
        if "LOCK" not in (r.get("tier") or ""): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        player_locks_by_team[key] = player_locks_by_team.get(key, 0) + 1

    forecasts: List[Dict[str, Any]] = []
    for key, e in expl_idx.items():
        matchup, side = (key.split("|", 1) + [""])[:2]
        n_signals = e.get("n_positive_signals", 0)
        if n_signals < 4: continue

        team_data = team_idx.get(key, {})
        team_tier = team_data.get("tier") or ""

        pace_val = pace_by_matchup.get(matchup, 100.0)
        n_locks = player_locks_by_team.get(f"{matchup}|{(e.get('team','') or '').upper()}", 0)

        signals: Dict[str, int] = {}
        signals["EXPLOSION_5PLUS"] = 1 if n_signals >= 5 else 0
        signals["EXPLOSION_4PLUS"] = 1 if n_signals >= 4 else 0
        signals["TEAM_LOCK_OR_STRONG"] = 1 if "LOCK" in team_tier or "STRONG" in team_tier else 0
        signals["HALF_TOTAL_OVER"] = 1 if half_over.get(matchup) else 0
        signals["HIGH_PACE"] = 1 if pace_val >= 102.5 else 0
        signals["PLAYER_LOCK_2PLUS"] = 1 if n_locks >= 2 else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 5:
            tier = "DOUBLE_DIGIT_LIKELY"
        elif n_positive >= 4:
            tier = "DOUBLE_DIGIT_LEAN"
        else:
            tier = "DOUBLE_DIGIT_LOOK"

        forecasts.append({
            "matchup": matchup,
            "team": e.get("team"),
            "side": side,
            "explosion_signals": n_signals,
            "team_confluence_tier": team_tier or None,
            "projected_pace": round(pace_val, 1),
            "player_locks_on_team": n_locks,
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                f"{e.get('team')} -10.5 1H spread",
                f"{e.get('team')} to lead at HT YES",
                f"{e.get('team')} team total OVER",
            ],
        })

    forecasts.sort(key=lambda f: -f["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_forecasts": len(forecasts),
        "n_likely": sum(1 for f in forecasts if f["tier"] == "DOUBLE_DIGIT_LIKELY"),
        "method_note": "NBA double-digit halftime lead forecast. 3+ signals "
                       "from EXPLOSION_5PLUS/4PLUS, TEAM_LOCK/STRONG, "
                       "HALF_TOTAL_OVER, HIGH_PACE, PLAYER_LOCK_2PLUS. LIKELY "
                       "= 5+ signals; LEAN = 4; LOOK = 3.",
        "forecasts": forecasts,
        "likely_picks": [f for f in forecasts if f["tier"] == "DOUBLE_DIGIT_LIKELY"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-dd-lead] {o['n_forecasts']} forecasts ({o['n_likely']} LIKELY) -> {OUT}")
