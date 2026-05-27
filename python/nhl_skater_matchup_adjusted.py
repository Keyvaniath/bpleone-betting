"""
EdgeStat -- NHL skater matchup-specific projection adjustments.

Counterpart to nba_player_matchup_adjusted but for NHL skaters. Adjusts
baseline SOG/Points projections by opponent metrics:
  - Opponent shots-against per game (SA/GP)
  - Opponent goals-against per game (GA/GP)
  - Opponent goalie fatigue (boost if fatigued)
  - Power-play opportunity multiplier

Adjustment model:
  sog_mult = opp_sa_gp / league_sa_gp_baseline
  pts_mult = opp_ga_gp / league_ga_gp_baseline
  fatigue_boost = 1.10 if opp goalie fatigued else 1.00

Output: data/nhl_skater_matchup_adjusted.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_matchup_adjusted.json")

LEAGUE_SA_GP = 30.0   # league avg shots-against per game
LEAGUE_GA_GP = 3.05   # league avg goals-against per game
FATIGUE_BOOST = 1.10


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


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    sog = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    pts = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))
    tt_edge = _load(os.path.join(DATA_DIR, "nhl_team_total_edge.json"))
    fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))

    # Opp metrics per (matchup, side) -- side here = OPP team's side
    opp_metrics: Dict[str, Dict[str, float]] = {}
    for r in (tt_edge.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup', '')}|{(r.get('side', '') or '').upper()}"
        opp_metrics[key] = {
            "opp_sa_gp": _safe(r.get("opp_sa_gp") or r.get("opp_shots_against_gp"),
                               LEAGUE_SA_GP),
            "opp_ga_gp": _safe(r.get("opp_ga_gp") or r.get("opp_goals_against_gp"),
                               LEAGUE_GA_GP),
        }

    # Fatigued opp goalies (team -> status)
    fatigued_teams: set = set()
    for r in (fatigue.get("rows") or []):
        if not isinstance(r, dict): continue
        team = (r.get("team") or "").upper()
        status = (r.get("status") or r.get("flag") or "").upper()
        if status in ("FATIGUED", "TIRED", "BACK_TO_BACK"):
            fatigued_teams.add(team)

    # Aggregate skater baseline projections
    skaters: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return skaters.setdefault(key, {
            "skater": name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "side": (r.get("side") or "").upper(),
            "opp_team": (r.get("opp_team") or "").upper(),
            "baseline": {},
        })

    for r in (sog.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or r.get("skater") or "", r)
        if not entry: continue
        entry["baseline"]["sog"] = _safe(r.get("projected_sog") or r.get("expected_sog"))

    for r in (pts.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or r.get("skater") or "", r)
        if not entry: continue
        entry["baseline"]["pts"] = _safe(r.get("projected_pts") or r.get("expected_pts"))

    # Apply adjustments
    rows: List[Dict[str, Any]] = []
    for key, entry in skaters.items():
        baseline = entry["baseline"]
        if not baseline: continue
        side = entry["side"]
        matchup = entry["matchup"] or ""

        # Opp side = OPPOSITE of skater's side
        opp_side = "AWAY" if side == "HOME" else "HOME"
        opp_key = f"{matchup}|{opp_side}"
        opp = opp_metrics.get(opp_key, {})
        opp_sa_gp = opp.get("opp_sa_gp", LEAGUE_SA_GP)
        opp_ga_gp = opp.get("opp_ga_gp", LEAGUE_GA_GP)

        sog_mult = opp_sa_gp / LEAGUE_SA_GP
        pts_mult = opp_ga_gp / LEAGUE_GA_GP

        # Fatigue boost if opp goalie fatigued
        boost = FATIGUE_BOOST if entry["opp_team"] in fatigued_teams else 1.0
        sog_mult *= boost
        pts_mult *= boost

        baseline_sog = baseline.get("sog", 0)
        baseline_pts = baseline.get("pts", 0)

        adj_sog = baseline_sog * sog_mult if baseline_sog else 0
        adj_pts = baseline_pts * pts_mult if baseline_pts else 0

        d_sog = adj_sog - baseline_sog
        d_pts = adj_pts - baseline_pts

        flag = None
        if abs(d_sog) >= 0.4 or abs(d_pts) >= 0.15:
            flag = "MATERIAL_ADJ"

        rows.append({
            "skater": entry["skater"],
            "team": entry["team"],
            "matchup": matchup,
            "side": side,
            "opp_sa_gp": round(opp_sa_gp, 2),
            "opp_ga_gp": round(opp_ga_gp, 2),
            "opp_goalie_fatigued": entry["opp_team"] in fatigued_teams,
            "baseline": {
                "sog": round(baseline_sog, 2),
                "pts": round(baseline_pts, 2),
            },
            "adjusted": {
                "sog": round(adj_sog, 2),
                "pts": round(adj_pts, 2),
            },
            "delta": {
                "sog": round(d_sog, 2),
                "pts": round(d_pts, 2),
            },
            "flag": flag,
        })

    rows.sort(key=lambda r: -abs(r["delta"]["sog"] or 0))
    material = [r for r in rows if r["flag"] == "MATERIAL_ADJ"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(rows),
        "n_material_adj": len(material),
        "method_note": "Adjusts baseline NHL skater SOG/pts by opp SA/GP, opp "
                       "GA/GP, and opp goalie fatigue. sog_mult = opp_sa_gp/30; "
                       "pts_mult = opp_ga_gp/3.05; fatigue boost = 1.10. "
                       "MATERIAL_ADJ flagged when |dSOG|>=0.4 or |dpts|>=0.15.",
        "rows": rows,
        "material_adj": material,
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-skater-matchup] {o['n_skaters']} skaters, "
          f"{o['n_material_adj']} material adjustments -> {OUT}")
