"""
EdgeStat -- MLB full-game pitching dominance chain alert.

Surfaces games where the FULL pitching staff has aligned dominance signals:
  - Starting pitcher: LOCK or STRONG from confluence_score
  - Bullpen: RESTED (low fatigue) from bullpen_fatigue_index
  - Closer: AVAILABLE from closer_availability_tracker

When all three align, that team has a "full-game pitching chain" — strong
basis for: opp team total UNDER, opp 5+ runs NO, F5 UNDER, opp first
inning run NO, save YES (closer).

CHAIN_LOCK   = pitcher LOCK + bullpen RESTED + closer AVAILABLE
CHAIN_STRONG = pitcher STRONG + bullpen rested + closer available
CHAIN_LEAN   = pitcher NEUTRAL/STRONG + 2 of 3 conditions met

Output: data/mlb_full_game_pitching_chain.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_full_game_pitching_chain.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    pitcher = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    closer = _load(os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json"))

    # Index pitcher confluence by (matchup, team)
    pitcher_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        pitcher_idx[key] = r

    # Bullpen by team (status: RESTED / FATIGUED / OVERWORKED)
    bullpen_by_team: Dict[str, str] = {}
    for r in (bullpen.get("rows") or bullpen.get("teams") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("tier") or r.get("flag") or "").upper()
        if team:
            bullpen_by_team[team] = status

    # Closer availability by team
    closer_by_team: Dict[str, Dict[str, Any]] = {}
    for r in (closer.get("rows") or closer.get("closers") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        if team:
            closer_by_team[team] = r

    chains: List[Dict[str, Any]] = []
    for key, p_row in pitcher_idx.items():
        matchup, team = (key.split("|", 1) + [""])[:2]
        if not team: continue

        pitcher_tier = p_row.get("tier") or ""
        bullpen_status = bullpen_by_team.get(team, "")
        closer_info = closer_by_team.get(team, {})

        bullpen_rested = "REST" in bullpen_status or "FRESH" in bullpen_status or bullpen_status in ("", "OK")
        bullpen_fatigued = "FATIG" in bullpen_status or "OVERWORK" in bullpen_status or "TIRED" in bullpen_status

        closer_status = (closer_info.get("status") or closer_info.get("flag") or "").upper()
        closer_available = ("AVAILABLE" in closer_status or "RESTED" in closer_status
                            or closer_status in ("", "OK", "FRESH"))

        conditions_met = sum([
            "LOCK" in pitcher_tier or "STRONG" in pitcher_tier,
            bullpen_rested and not bullpen_fatigued,
            closer_available,
        ])

        if conditions_met < 2: continue

        if "LOCK" in pitcher_tier and bullpen_rested and closer_available:
            tier = "CHAIN_LOCK"
        elif "STRONG" in pitcher_tier and bullpen_rested and closer_available:
            tier = "CHAIN_STRONG"
        else:
            tier = "CHAIN_LEAN"

        chains.append({
            "matchup": matchup,
            "team": team,
            "pitcher": p_row.get("pitcher"),
            "pitcher_tier": pitcher_tier,
            "pitcher_score": p_row.get("composite_score"),
            "bullpen_status": bullpen_status or "UNKNOWN",
            "closer": closer_info.get("closer") or closer_info.get("player"),
            "closer_status": closer_status or "UNKNOWN",
            "conditions_met": conditions_met,
            "tier": tier,
            "recommended_markets": [
                f"opp team total UNDER",
                f"opp 5+ runs NO",
                f"{matchup} 1st 5 innings UNDER",
                f"opp 1st inning run NO",
                f"{closer_info.get('closer') or 'closer'} save YES",
            ],
        })

    chains.sort(key=lambda c: (-c["conditions_met"], -(c.get("pitcher_score") or 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_chains": len(chains),
        "n_chain_lock": sum(1 for c in chains if c["tier"] == "CHAIN_LOCK"),
        "n_chain_strong": sum(1 for c in chains if c["tier"] == "CHAIN_STRONG"),
        "method_note": "Full-game pitching dominance chain. Pitcher LOCK/STRONG "
                       "+ bullpen RESTED + closer AVAILABLE = CHAIN tier. "
                       "Recommended: opp team total UNDER + opp 5+ runs NO + "
                       "F5 UNDER + closer save YES (5-leg same-game parlay).",
        "chains": chains,
        "locks": [c for c in chains if c["tier"] == "CHAIN_LOCK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-pitching-chain] {o['n_chains']} chains "
          f"({o['n_chain_lock']} LOCK, {o['n_chain_strong']} STRONG) -> {OUT}")
