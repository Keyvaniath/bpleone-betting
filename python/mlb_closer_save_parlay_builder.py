"""
EdgeStat -- MLB closer save parlay builder.

For each team with a high p_save closer + opposing team-total UNDER lean,
builds the recommended multi-leg same-game parlay:
  Leg 1: Closer save YES (p >= 55%)
  Leg 2: Opp team total UNDER
  Leg 3: Opp 5+ runs NO
  Leg 4: Game total UNDER

Output: data/mlb_closer_save_parlay_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_closer_save_parlay_builder.json")


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


def _american_from_p(p: float):
    if p <= 0 or p >= 1: return None
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    closer_save = _load(os.path.join(DATA_DIR, "mlb_closer_to_record_save.json"))
    team_total = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    five_plus = _load(os.path.join(DATA_DIR, "mlb_team_5plus_runs.json"))
    game_total = _load(os.path.join(DATA_DIR, "mlb_game_total_alt_props.json"))

    save_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (closer_save.get(k) or []):
            if isinstance(r, dict):
                team = (r.get("team") or "").upper()
                if team and team not in save_idx:
                    save_idx[team] = r

    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (team_total.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        tt_idx[key] = r

    five_idx: Dict[str, Dict[str, Any]] = {}
    for r in (five_plus.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup','')}|{(r.get('side','') or '').upper()}"
        five_idx[key] = r

    gt_under_by_matchup: Dict[str, bool] = {}
    for r in (game_total.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:
            gt_under_by_matchup[r.get("matchup", "")] = True

    parlays: List[Dict[str, Any]] = []
    for team, save_data in save_idx.items():
        p_save = _safe(save_data.get("p_save") or save_data.get("p"))
        if p_save < 0.55: continue

        matchup = save_data.get("matchup", "")
        # Find own side
        my_side = ""
        opp_side = ""
        for side in ("HOME", "AWAY"):
            tt_data = tt_idx.get(f"{matchup}|{side}", {})
            if (tt_data.get("team") or "").upper() == team:
                my_side = side
                opp_side = "AWAY" if side == "HOME" else "HOME"
                break

        if not opp_side: continue

        opp_tt = tt_idx.get(f"{matchup}|{opp_side}", {})
        opp_tt_dir = (opp_tt.get("direction") or "").upper()
        opp_5plus = five_idx.get(f"{matchup}|{opp_side}", {})
        opp_p_5plus = _safe(opp_5plus.get("p_5plus") or opp_5plus.get("p"))
        gt_under = gt_under_by_matchup.get(matchup, False)

        legs: List[Dict[str, Any]] = []
        legs.append({
            "market": f"{save_data.get('closer') or 'closer'} save YES",
            "p": round(p_save, 3),
            "implied_odds": _american_from_p(p_save),
        })

        if opp_tt_dir in ("STRONG_UNDER", "LEAN_UNDER"):
            # Estimate p as 0.55 for STRONG_UNDER, 0.52 for LEAN_UNDER
            p_tt_under = 0.55 if "STRONG" in opp_tt_dir else 0.52
            legs.append({
                "market": f"Opp ({opp_side}) team total UNDER",
                "p": round(p_tt_under, 3),
                "implied_odds": _american_from_p(p_tt_under),
            })

        if opp_p_5plus and opp_p_5plus < 0.35:
            p_no_5plus = 1 - opp_p_5plus
            legs.append({
                "market": f"Opp 5+ runs NO",
                "p": round(p_no_5plus, 3),
                "implied_odds": _american_from_p(p_no_5plus),
            })

        if gt_under:
            p_gt_under = 0.55
            legs.append({
                "market": "Game total UNDER",
                "p": round(p_gt_under, 3),
                "implied_odds": _american_from_p(p_gt_under),
            })

        if len(legs) < 2: continue

        parlay_p = 1.0
        for leg in legs:
            parlay_p *= leg["p"]

        parlays.append({
            "team": team,
            "matchup": matchup,
            "closer": save_data.get("closer"),
            "p_save": round(p_save, 3),
            "opp_team_total_direction": opp_tt_dir or None,
            "opp_p_5plus": round(opp_p_5plus, 3),
            "game_total_under": gt_under,
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p": round(parlay_p, 4),
            "parlay_implied_odds": _american_from_p(parlay_p),
        })

    parlays.sort(key=lambda p: -p["parlay_p"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "MLB closer save same-game parlay. Required: p_save >= 0.55. "
                       "Optional legs: opp TT UNDER, opp 5+ runs NO, game total "
                       "UNDER. parlay_p = product of leg p's. Implied parlay odds "
                       "computed.",
        "parlays": parlays,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-closer-parlay] {o['n_parlays']} parlay builds -> {OUT}")
