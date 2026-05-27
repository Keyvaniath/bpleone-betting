"""
EdgeStat -- NBA player matchup-specific projection adjustments.

Counterpart to mlb_pitcher_lineup_adjusted but for NBA. Adjusts baseline
player prop projections by opponent defensive matchup signals:
  - Opponent DRtg (defensive rating)
  - Opponent pace
  - Opponent positional defense vs player's position
  - Home/road split

Adjustment model:
  pace_mult = projected_pace / 100.0  (league avg ~100)
  drtg_mult = 1 + (opp_drtg - 113) / 100  (lower DRtg = more offense allowed)
  pts_adj   = pts_baseline * pace_mult * drtg_mult

Flag MATERIAL_ADJ when |delta_pts| >= 1.5 OR |delta_reb| >= 0.8.

Output: data/nba_player_matchup_adjusted.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_matchup_adjusted.json")

LEAGUE_DRTG = 113.0
LEAGUE_PACE = 100.0
DRTG_DAMPER = 100.0


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
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    reb = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    ast = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    pace = _load(os.path.join(DATA_DIR, "nba_pace_adjusted.json"))
    team_total = _load(os.path.join(DATA_DIR, "nba_team_total_edge.json"))

    # Per matchup, get projected pace + opp DRtg
    matchup_ctx: Dict[str, Dict[str, float]] = {}
    for g in (pace.get("games") or pace.get("rows") or []):
        if not isinstance(g, dict): continue
        m = g.get("matchup", "")
        if not m: continue
        matchup_ctx[m] = {
            "pace": _safe(g.get("projected_pace") or g.get("pace"), LEAGUE_PACE),
            "opp_drtg": _safe(g.get("opp_drtg"), LEAGUE_DRTG),
        }

    # Per (matchup, side), get team's opp_drtg via team_total_edge
    tt_ctx: Dict[str, Dict[str, float]] = {}
    for r in (team_total.get("rows") or []):
        if not isinstance(r, dict): continue
        key = f"{r.get('matchup', '')}|{(r.get('side', '') or '').upper()}"
        tt_ctx[key] = {
            "opp_drtg": _safe(r.get("opp_drtg"), LEAGUE_DRTG),
        }

    # Aggregate player baseline projections
    players: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return players.setdefault(key, {
            "player": name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "side": (r.get("side") or "").upper(),
            "baseline": {},
        })

    for r in (pts.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["baseline"]["pts"] = _safe(r.get("projected_pts") or r.get("expected_pts"))

    for r in (reb.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["baseline"]["reb"] = _safe(r.get("projected_reb") or r.get("expected_reb"))

    for r in (ast.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["baseline"]["ast"] = _safe(r.get("projected_ast") or r.get("expected_ast"))

    # Apply matchup adjustments
    rows: List[Dict[str, Any]] = []
    for key, entry in players.items():
        baseline = entry["baseline"]
        if not baseline: continue
        matchup = entry["matchup"] or ""
        ctx = matchup_ctx.get(matchup) or {}
        opp_drtg = ctx.get("opp_drtg", LEAGUE_DRTG)
        pace = ctx.get("pace", LEAGUE_PACE)

        # If not in matchup_ctx, fall back to team_total ctx
        if not ctx:
            tt_key = f"{matchup}|{entry['side']}"
            tt_data = tt_ctx.get(tt_key) or {}
            opp_drtg = tt_data.get("opp_drtg", LEAGUE_DRTG)

        pace_mult = pace / LEAGUE_PACE
        drtg_mult = 1 + (opp_drtg - LEAGUE_DRTG) / DRTG_DAMPER  # opp_drtg > LEAGUE = boost offense
        # Wait — lower DRtg = better defense = LESS offense allowed.
        # So if opp_drtg < LEAGUE, OPP is better defense → reduce.
        # 1 + (opp_drtg - LEAGUE)/100 :
        #   opp_drtg = 113 (league) → 1.0 (no change) ✓
        #   opp_drtg = 116 (worse D) → 1.03 (boost) ✓
        #   opp_drtg = 110 (better D) → 0.97 (reduce) ✓

        baseline_pts = baseline.get("pts", 0)
        baseline_reb = baseline.get("reb", 0)
        baseline_ast = baseline.get("ast", 0)

        adj_pts = baseline_pts * pace_mult * drtg_mult if baseline_pts else 0
        adj_reb = baseline_reb * pace_mult if baseline_reb else 0
        adj_ast = baseline_ast * pace_mult * drtg_mult if baseline_ast else 0

        d_pts = adj_pts - baseline_pts
        d_reb = adj_reb - baseline_reb
        d_ast = adj_ast - baseline_ast

        flag = None
        if abs(d_pts) >= 1.5 or abs(d_reb) >= 0.8 or abs(d_ast) >= 0.8:
            flag = "MATERIAL_ADJ"

        rows.append({
            "player": entry["player"],
            "team": entry["team"],
            "matchup": matchup,
            "side": entry["side"],
            "opp_drtg": round(opp_drtg, 1),
            "projected_pace": round(pace, 1),
            "baseline": {
                "pts": round(baseline_pts, 1),
                "reb": round(baseline_reb, 1),
                "ast": round(baseline_ast, 1),
            },
            "adjusted": {
                "pts": round(adj_pts, 1),
                "reb": round(adj_reb, 1),
                "ast": round(adj_ast, 1),
            },
            "delta": {
                "pts": round(d_pts, 2),
                "reb": round(d_reb, 2),
                "ast": round(d_ast, 2),
            },
            "flag": flag,
        })

    rows.sort(key=lambda r: -abs(r["delta"]["pts"] or 0))
    material = [r for r in rows if r["flag"] == "MATERIAL_ADJ"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_material_adj": len(material),
        "method_note": "Adjusts baseline NBA player pts/reb/ast projections by "
                       "opp DRtg + projected pace. pace_mult = pace/100; "
                       "drtg_mult = 1 + (opp_drtg-113)/100. pts and ast scaled "
                       "by both; reb scaled by pace only. MATERIAL_ADJ flagged "
                       "when |dpts|>=1.5 or |dreb/dast|>=0.8.",
        "rows": rows,
        "material_adj": material,
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-player-matchup] {o['n_players']} players, "
          f"{o['n_material_adj']} material adjustments -> {OUT}")
