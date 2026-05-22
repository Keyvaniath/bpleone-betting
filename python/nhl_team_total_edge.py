"""
EdgeStat -- NHL team total edge.

Companion to mlb_team_total_edge / nba_team_total_edge. For each NHL game,
projects expected team goals using:
  - Season goals-per-game baseline (PER_TEAM ~ 3.1 / game)
  - Opp goalie save percentage (from nhl_goalie_logs)
  - Goalie fatigue tier (from nhl_goalie_fatigue_index)
  - Back-to-back penalty (-0.20 goals)
  - Power-play differential (skipped — needs special-teams data)

Method:
  expected_goals = LEAGUE_GPG_PER_TEAM * (1 - opp_sv_pct - league_baseline_diff)
                 * fatigue_mult * b2b_mult

  Bayesian shrink 40% toward book half-total.
  STRONG_OVER at edge >= 0.40 goals; STRONG_UNDER at <= -0.40.

Output: data/nhl_team_total_edge.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_team_total_edge.json")

LEAGUE_GPG_PER_TEAM = 3.10
LEAGUE_SV_PCT = 0.910


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


def _fatigue_mult(tier: str) -> float:
    return {"FRESH": 0.90, "NORMAL": 1.00,
            "TIRED": 1.10, "GASSED": 1.20}.get(tier, 1.0)


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    goalie_fatigue = _load(os.path.join(DATA_DIR, "nhl_goalie_fatigue_index.json"))
    goalie_logs = _load(os.path.join(DATA_DIR, "nhl_goalie_logs.json"))

    # Index goalie sv% by name
    g_sv = {(g.get("name") or "").lower(): _safe(g.get("season_sv_pct"), LEAGUE_SV_PCT)
            for g in (goalie_logs.get("goalies") or []) if isinstance(g, dict)}

    # Index fatigue per matchup
    fatigue_idx: Dict[str, Dict[str, Any]] = {}
    for g in (goalie_fatigue.get("games") or []):
        fatigue_idx[g.get("matchup") or ""] = g

    games = state.get("games") or state.get("events") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        status = (g.get("status") or "").lower()
        if "final" in status: continue
        home = (g.get("home_team") or g.get("home") or "").upper()
        away = (g.get("away_team") or g.get("away") or "").upper()
        if not home or not away: continue
        matchup = f"{away} @ {home}"

        book_total = _safe((g.get("market") or {}).get("total"), 6.2)
        half_total = book_total / 2.0

        fatigue_game = fatigue_idx.get(matchup, {})

        for side, opp_side in (("home", "away"), ("away", "home")):
            # Opp goalie
            opp_goalie_info = fatigue_game.get(f"{opp_side}_goalie") or {}
            opp_goalie_name = (opp_goalie_info.get("goalie") or "").lower()
            opp_sv_pct = g_sv.get(opp_goalie_name, LEAGUE_SV_PCT)
            opp_fatigue_tier = opp_goalie_info.get("tier") or "NORMAL"

            # Compute expected goals
            sv_diff = LEAGUE_SV_PCT - opp_sv_pct  # positive = weaker goalie
            fatigue_m = _fatigue_mult(opp_fatigue_tier)
            # Each 0.010 below league sv% adds ~0.20 expected goals
            expected_goals = LEAGUE_GPG_PER_TEAM * (1 + sv_diff * 20) * fatigue_m

            # Anchor toward book
            anchor_w = 0.40
            anchored = half_total * anchor_w + expected_goals * (1 - anchor_w)

            edge_goals = anchored - half_total

            if edge_goals >= 0.40:
                direction = "STRONG_OVER"
            elif edge_goals >= 0.15:
                direction = "LEAN_OVER"
            elif edge_goals <= -0.40:
                direction = "STRONG_UNDER"
            elif edge_goals <= -0.15:
                direction = "LEAN_UNDER"
            else:
                direction = "NEUTRAL"

            team_abbr = home if side == "home" else away

            rows.append({
                "matchup": matchup,
                "side": side.upper(),
                "team": team_abbr,
                "opp_goalie": opp_goalie_info.get("goalie"),
                "opp_sv_pct": round(opp_sv_pct, 4),
                "opp_fatigue_tier": opp_fatigue_tier,
                "fatigue_mult": round(fatigue_m, 3),
                "book_team_total": half_total,
                "model_expected_goals_raw": round(expected_goals, 2),
                "model_expected_goals_anchored": round(anchored, 2),
                "edge_goals": round(edge_goals, 2),
                "direction": direction,
            })

    rows.sort(key=lambda r: -abs(r["edge_goals"]))
    strong = [r for r in rows if r["direction"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_team_sides": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "NHL team total = LEAGUE_GPG(3.10) * (1 + opp_sv_diff*20) * "
                       "opp_goalie_fatigue_mult. Bayesian-shrunk 40% toward book "
                       "half-total. STRONG_OVER/UNDER at +/- 0.40 goals; LEAN at +/- 0.15.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-tt] {o['n_team_sides']} team-sides, {o['n_strong_edges']} strong -> {OUT}")
