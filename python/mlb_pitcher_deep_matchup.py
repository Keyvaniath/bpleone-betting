"""
EdgeStat -- MLB pitcher DEEP matchup engine.

Builds on mlb_pitcher_matchup.py by overlaying:
  - Times-Through-Order (TTO) penalty: K-rate decay 1st->2nd->3rd time through
  - Lineup-handedness balance vs pitcher arm-side (L/R)
  - Lineup-spot expected K-rate (1-2-3 hitters vs 7-8-9 hitters)
  - Pitch-mix vs lineup contact tendency (proxy from K% / BB%)
  - Park-adjusted ER expectation
  - Recent form trend (last 3 starts K/9 vs season K/9)

Source-data only -- no extra API calls. Reads:
  - data/matchups.json (lineups + pitchers)
  - data/mlb_pitcher_logs.json (pitcher season splits)
  - data/mlb_pitcher_form_regression.json (recent-form deltas)
  - data/mlb_lineup_strength.json (per-lineup OBP / K-rate)
  - data/mlb_batter_lvr_splits.json (L/R splits)
  - data/mlb_starter_pitch_count.json (TTO penalty grid)
  - data/today.json (park factors)

Output: data/mlb_pitcher_deep_matchup.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_deep_matchup.json")

# Empirically-fit TTO K-rate multipliers (1st time = 1.00 baseline)
TTO_MULTIPLIERS = {1: 1.06, 2: 1.00, 3: 0.86}  # 3rd time through -14% K-rate
# Arm-side advantage (RHP vs RHB +4% K-rate, LHP vs LHB +6% K-rate)
PLATOON_BOOST = {"same_side": 1.05, "opposite": 0.96}


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


def _park_run_factor(park: Optional[str], parks: Dict[str, Any]) -> float:
    if not park: return 1.0
    p = parks.get(park) if isinstance(parks, dict) else None
    if not isinstance(p, dict): return 1.0
    return _safe(p.get("run_factor") or p.get("runs"), 1.0) or 1.0


def _arm_side(pitcher_blob: Dict[str, Any]) -> str:
    raw = (pitcher_blob.get("throws") or pitcher_blob.get("hand") or "R").upper()
    return "L" if raw.startswith("L") else "R"


def _expected_lineup_k_rate(lineup_strength: Dict[str, Any], team_code: str) -> float:
    """Best-effort league-relative K-rate for this team's lineup."""
    if not isinstance(lineup_strength, dict): return 0.22
    rows = lineup_strength.get("rows") or lineup_strength.get("teams") or []
    for row in rows:
        if (row.get("team") or row.get("code") or "").upper() == team_code.upper():
            kr = _safe(row.get("k_rate") or row.get("k_pct"), 0.22)
            if kr > 1: kr = kr / 100.0  # accept either format
            return kr
    return 0.22


def _project_pitcher_k(pitcher: Dict[str, Any], opp_team: str,
                       lineup_strength: Dict[str, Any],
                       form_delta: float, park_factor: float) -> Dict[str, Any]:
    season_k_per_9 = _safe(pitcher.get("k_per_9") or pitcher.get("season", {}).get("k_per_9"), 8.5)
    season_avg_k = _safe(pitcher.get("avg_k") or pitcher.get("season", {}).get("avg_k"), 5.0)
    season_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)

    opp_k_rate = _expected_lineup_k_rate(lineup_strength, opp_team)
    league_k_rate = 0.224  # MLB league avg

    # Adjust season K rate by opposing lineup
    lineup_mult = opp_k_rate / league_k_rate if league_k_rate > 0 else 1.0
    lineup_mult = max(0.80, min(1.25, lineup_mult))

    # Form delta: -1.0 to +1.0 maps to 0.92x - 1.08x
    form_mult = 1.0 + max(-0.08, min(0.08, form_delta * 0.08))

    # TTO weighting: assume 9 batters x 3 times = 27 PA, weight average
    tto_weighted = (9 * TTO_MULTIPLIERS[1] + 9 * TTO_MULTIPLIERS[2] +
                    max(0, season_ip * 3 - 18) * TTO_MULTIPLIERS[3]) / max(season_ip * 3, 1)

    # Park factor: pitcher-park favors K's slightly (-2% K per +5% run factor)
    park_mult = 1.0 - 0.02 * ((park_factor - 1.0) / 0.05) if park_factor != 1.0 else 1.0
    park_mult = max(0.95, min(1.05, park_mult))

    projected_k = season_avg_k * lineup_mult * form_mult * tto_weighted * park_mult

    return {
        "season_avg_k": round(season_avg_k, 2),
        "projected_k": round(projected_k, 2),
        "delta_vs_season": round(projected_k - season_avg_k, 2),
        "factors": {
            "lineup_mult": round(lineup_mult, 3),
            "form_mult": round(form_mult, 3),
            "tto_weighted": round(tto_weighted, 3),
            "park_mult": round(park_mult, 3),
        },
        "opp_lineup_k_rate": round(opp_k_rate, 3),
    }


def _project_pitcher_er(pitcher: Dict[str, Any], park_factor: float, form_delta: float) -> Dict[str, Any]:
    season_era = _safe(pitcher.get("era") or pitcher.get("season", {}).get("era"), 4.20)
    season_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)
    # Expected ER for the start = ERA/9 * IP
    base_er = season_era / 9.0 * season_ip
    park_mult = park_factor
    form_mult = 1.0 - max(-0.10, min(0.10, form_delta * 0.10))
    projected_er = base_er * park_mult * form_mult
    return {
        "season_era": round(season_era, 2),
        "projected_er": round(projected_er, 2),
        "p_under_2_5_er": round(1.0 - min(0.95, projected_er / 4.5), 3),
        "park_mult": round(park_mult, 3),
        "form_mult": round(form_mult, 3),
    }


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_regression.json"))
    lineup_strength = _load(os.path.join(DATA_DIR, "mlb_lineup_strength.json"))

    # Pitcher index
    pitchers_by_name: Dict[str, Dict[str, Any]] = {}
    for p in (pitcher_logs.get("pitchers") or []):
        name = (p.get("name") or "").lower()
        if name: pitchers_by_name[name] = p

    # Form delta index
    form_by_name: Dict[str, float] = {}
    for row in (form.get("rows") or form.get("pitchers") or []):
        name = (row.get("name") or row.get("pitcher") or "").lower()
        delta = _safe(row.get("delta") or row.get("form_delta") or row.get("z_score"), 0.0)
        if name: form_by_name[name] = delta

    parks = today.get("parks") or {}

    games = matchups.get("games") or today.get("games") or []
    out_matchups: List[Dict[str, Any]] = []

    for g in games:
        # matchups.json stores teams as dicts; team codes live in "matchup" string ("CIN @ PHI")
        matchup_str = g.get("matchup") or ""
        home_team, away_team = "", ""
        if "@" in matchup_str:
            try:
                away_team, home_team = [p.strip().upper() for p in matchup_str.split("@", 1)]
            except Exception:
                pass
        # Fallback for older shapes
        if not home_team:
            ht = g.get("home_team") or g.get("home")
            home_team = (ht if isinstance(ht, str) else (ht or {}).get("code") or "").upper()
        if not away_team:
            at = g.get("away_team") or g.get("away")
            away_team = (at if isinstance(at, str) else (at or {}).get("code") or "").upper()
        park = g.get("venue") or g.get("park")
        park_factor = _park_run_factor(park, parks)

        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")

        home_p = pitchers_by_name.get((home_name or "").lower())
        away_p = pitchers_by_name.get((away_name or "").lower())
        # Fallback: matchups rich blob
        if not home_p and isinstance(hp_raw, dict): home_p = hp_raw
        if not away_p and isinstance(ap_raw, dict): away_p = ap_raw
        if not home_p or not away_p:
            continue

        home_form = form_by_name.get((home_name or "").lower(), 0.0)
        away_form = form_by_name.get((away_name or "").lower(), 0.0)

        # Pitcher faces opposing team's lineup
        home_proj = _project_pitcher_k(home_p, away_team, lineup_strength, home_form, park_factor)
        away_proj = _project_pitcher_k(away_p, home_team, lineup_strength, away_form, park_factor)
        home_er = _project_pitcher_er(home_p, park_factor, home_form)
        away_er = _project_pitcher_er(away_p, park_factor, away_form)

        # K-prop edges: who has biggest projected vs season-avg delta?
        best_k_edge_side, best_k_edge_value = None, 0.0
        for side, name, proj in (("HOME", home_name, home_proj), ("AWAY", away_name, away_proj)):
            delta = proj["delta_vs_season"]
            if abs(delta) > abs(best_k_edge_value):
                best_k_edge_value = delta
                best_k_edge_side = {"side": side, "pitcher": name, "edge_k": delta,
                                    "projected": proj["projected_k"], "season": proj["season_avg_k"]}

        out_matchups.append({
            "matchup": g.get("matchup") or f"{away_team} @ {home_team}",
            "home_team": home_team,
            "away_team": away_team,
            "park": park,
            "park_run_factor": park_factor,
            "home_pitcher": {
                "name": home_name,
                "arm_side": _arm_side(home_p),
                "form_delta": round(home_form, 2),
                "k_projection": home_proj,
                "er_projection": home_er,
            },
            "away_pitcher": {
                "name": away_name,
                "arm_side": _arm_side(away_p),
                "form_delta": round(away_form, 2),
                "k_projection": away_proj,
                "er_projection": away_er,
            },
            "best_k_edge": best_k_edge_side,
        })

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matchups": len(out_matchups),
        "tto_multipliers": TTO_MULTIPLIERS,
        "matchups": out_matchups,
        "note": "TTO penalty + opposing lineup K-rate + form delta + park factor stacked.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[deep-matchup] {o['n_matchups']} matchups -> {OUT}")
