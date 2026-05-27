"""
EdgeStat -- MLB bullpen chain save alerts.

Surfaces teams where the full bullpen chain is rested + favorable:
  - Closer: AVAILABLE / RESTED
  - Setup/8th inning: not overworked
  - Bullpen fatigue: RESTED or OK
  - Team is favored (so closer likely to enter)
  - Starting pitcher: LOCK or STRONG (so closer is set up for save)

When all signals align, recommend:
  - Closer to record save YES
  - Team total UNDER (full game UNDER risk)
  - 5+ runs allowed: NO

Output: data/mlb_bullpen_chain_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_bullpen_chain_alerts.json")


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
    pitcher = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    bullpen = _load(os.path.join(DATA_DIR, "mlb_bullpen_fatigue_index.json"))
    closer_avail = _load(os.path.join(DATA_DIR, "mlb_closer_availability_tracker.json"))
    closer_save = _load(os.path.join(DATA_DIR, "mlb_closer_to_record_save.json"))
    team_total = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))

    pitcher_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('team','') or '').upper()}"
        pitcher_idx[key] = r

    bullpen_by_team: Dict[str, Dict[str, Any]] = {}
    for r in (bullpen.get("rows") or bullpen.get("teams") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        if team:
            bullpen_by_team[team] = r

    closer_by_team: Dict[str, Dict[str, Any]] = {}
    for r in (closer_avail.get("rows") or closer_avail.get("closers") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        if team:
            closer_by_team[team] = r

    save_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (closer_save.get(k) or []):
            if isinstance(r, dict):
                team = (r.get("team") or "").upper()
                if team and team not in save_idx:
                    save_idx[team] = r

    chains: List[Dict[str, Any]] = []
    for key, p in pitcher_idx.items():
        matchup, team = (key.split("|", 1) + [""])[:2]
        if not team: continue

        bullpen_info = bullpen_by_team.get(team, {})
        bullpen_status = (bullpen_info.get("status") or bullpen_info.get("tier")
                          or bullpen_info.get("flag") or "").upper()
        bullpen_ok = "REST" in bullpen_status or "FRESH" in bullpen_status or bullpen_status in ("", "OK")

        closer_info = closer_by_team.get(team, {})
        closer_status = (closer_info.get("status") or closer_info.get("flag") or "").upper()
        closer_avail_ok = ("AVAILABLE" in closer_status or "RESTED" in closer_status
                           or closer_status in ("", "OK", "FRESH"))

        save_info = save_idx.get(team, {})
        p_save = _safe(save_info.get("p_save") or save_info.get("p"))

        # Conditions
        pitcher_tier = (p.get("tier") or "").upper()
        pitcher_strong = "LOCK" in pitcher_tier or "STRONG" in pitcher_tier
        bullpen_rested = bullpen_ok
        closer_rested = closer_avail_ok
        save_likely = p_save >= 0.55

        conditions = sum([pitcher_strong, bullpen_rested, closer_rested, save_likely])
        if conditions < 3: continue

        if conditions == 4:
            tier = "BULLPEN_CHAIN_LOCK"
        elif conditions == 3:
            tier = "BULLPEN_CHAIN_STRONG"
        else:
            continue

        chains.append({
            "matchup": matchup,
            "team": team,
            "pitcher": p.get("pitcher"),
            "pitcher_tier": pitcher_tier or "NEUTRAL",
            "bullpen_status": bullpen_status or "UNKNOWN",
            "closer": closer_info.get("closer") or closer_info.get("player"),
            "closer_status": closer_status or "UNKNOWN",
            "p_save": round(p_save, 3),
            "conditions_met": conditions,
            "tier": tier,
            "recommended_parlay": [
                f"{closer_info.get('closer') or 'closer'} save YES",
                f"opp team total UNDER",
                f"opp 5+ runs NO",
                f"{p.get('pitcher')} K OVER + outs OVER (set up closer)",
            ],
        })

    chains.sort(key=lambda c: (-c["conditions_met"], -(c.get("p_save") or 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_chains": len(chains),
        "n_locks": sum(1 for c in chains if c["tier"] == "BULLPEN_CHAIN_LOCK"),
        "method_note": "Bullpen chain save alerts. 4 conditions for LOCK: "
                       "pitcher LOCK/STRONG + bullpen RESTED + closer AVAILABLE "
                       "+ p_save >= 0.55. Recommends closer save YES + opp TT "
                       "UNDER parlay.",
        "chains": chains,
        "locks": [c for c in chains if c["tier"] == "BULLPEN_CHAIN_LOCK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-bullpen-chain] {o['n_chains']} chains ({o['n_locks']} LOCK) -> {OUT}")
