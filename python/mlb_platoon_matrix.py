"""
EdgeStat -- MLB platoon matrix.

For each game tonight, computes the L/R handedness composition of each
lineup and cross-references against the opposing starter's throwing hand.

Surface signals:
  - REVERSE_PLATOON_ADV: Pitcher throwing R faces lineup of mostly LHB (or vice
    versa). Standard advantage to the lineup (~0.05 OPS boost).
  - PLATOON_LOCK: Pitcher throwing R faces lineup of mostly RHB. Pitcher edge
    (~0.04 OPS reduction in his favor).
  - BALANCED: 50/50 handedness in lineup, no platoon edge.

Per-game output includes:
  - n_RHB / n_LHB / n_SWITCH per side
  - opposing_pitcher_throws (R / L)
  - platoon_label
  - estimated_OPS_shift for the offense (positive = offense advantage)

Output: data/mlb_platoon_matrix.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_platoon_matrix.json")


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


def _classify_platoon(opp_throws: str, n_LHB: int, n_RHB: int, n_SWITCH: int) -> Dict[str, Any]:
    """Compute platoon edge from lineup handedness vs opp pitcher."""
    total = n_LHB + n_RHB + n_SWITCH
    if total == 0:
        return {"label": "UNKNOWN", "est_ops_shift": 0.0}

    # Switch hitters bat opposite hand of pitcher (always have platoon advantage)
    advantage_count = n_SWITCH
    if opp_throws == "R":
        # Lefty batters have advantage vs RHP
        advantage_count += n_LHB
    elif opp_throws == "L":
        # Righty batters have advantage vs LHP
        advantage_count += n_RHB

    advantage_pct = advantage_count / total

    if advantage_pct >= 0.70:
        label = "REVERSE_PLATOON_ADV"
        ops_shift = +0.040
    elif advantage_pct >= 0.55:
        label = "MILD_PLATOON_ADV"
        ops_shift = +0.020
    elif advantage_pct <= 0.30:
        label = "PLATOON_LOCK"
        ops_shift = -0.040
    elif advantage_pct <= 0.45:
        label = "MILD_PLATOON_LOCK"
        ops_shift = -0.020
    else:
        label = "BALANCED"
        ops_shift = 0.0

    return {
        "label": label,
        "advantage_pct": round(advantage_pct, 2),
        "advantage_count": advantage_count,
        "total_batters": total,
        "est_ops_shift": ops_shift,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    # Index batter handedness from LvR splits
    bat_hands: Dict[str, str] = {}
    for r in (lvr.get("all_batters") or []):
        name = (r.get("batter") or "").lower()
        # LvR module stores "bat_side" or "hand"
        h = (r.get("bat_side") or r.get("hand") or "").upper()
        if name and h in ("L", "R", "S"):
            bat_hands[name] = h

    # Pitcher throwing hand
    p_throws: Dict[str, str] = {}
    for p in (pitcher_logs.get("pitchers") or []):
        n = (p.get("name") or "").lower()
        th = (p.get("throws") or "").upper()
        if n and th in ("L", "R"):
            p_throws[n] = th

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        lineups = g.get("lineups") or {}

        side_out: Dict[str, Any] = {}
        for side, opp_pitcher_field in (("home", "away_pitcher"), ("away", "home_pitcher")):
            lineup = lineups.get(side) or []
            n_LHB = n_RHB = n_SWITCH = 0
            for b in lineup:
                if not isinstance(b, dict): continue
                name = (b.get("name") or "").lower()
                hand = bat_hands.get(name) or (b.get("bat_side") or "").upper()
                if hand == "L": n_LHB += 1
                elif hand == "R": n_RHB += 1
                elif hand == "S": n_SWITCH += 1

            opp_p_raw = g.get(opp_pitcher_field)
            opp_p_name = opp_p_raw if isinstance(opp_p_raw, str) else (opp_p_raw or {}).get("name")
            opp_throws = p_throws.get((opp_p_name or "").lower(), "")

            platoon = _classify_platoon(opp_throws, n_LHB, n_RHB, n_SWITCH)
            side_out[side] = {
                "n_LHB": n_LHB,
                "n_RHB": n_RHB,
                "n_SWITCH": n_SWITCH,
                "opp_pitcher": opp_p_name,
                "opp_pitcher_throws": opp_throws or "?",
                **platoon,
            }

        out_games.append({
            "matchup": matchup,
            "home": side_out.get("home"),
            "away": side_out.get("away"),
        })

    # Surface platoon alerts
    alerts: List[Dict[str, Any]] = []
    for g in out_games:
        for side in ("home", "away"):
            s = g.get(side) or {}
            if s.get("label") in ("REVERSE_PLATOON_ADV", "PLATOON_LOCK"):
                alerts.append({
                    "matchup": g["matchup"],
                    "side": side.upper(),
                    "label": s["label"],
                    "est_ops_shift": s["est_ops_shift"],
                    "opp_pitcher": s.get("opp_pitcher"),
                    "opp_throws": s.get("opp_pitcher_throws"),
                    "advantage_pct": s.get("advantage_pct"),
                })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_platoon_alerts": len(alerts),
        "method_note": "Counts L/R/S in each lineup, cross-refs opposing pitcher's "
                       "throwing hand. >=70% advantageous matchup = REVERSE_PLATOON_ADV "
                       "(+.04 OPS shift); <=30% = PLATOON_LOCK (-.04 OPS).",
        "games": out_games,
        "platoon_alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[platoon] {o['n_games']} games, {o['n_platoon_alerts']} platoon alerts -> {OUT}")
