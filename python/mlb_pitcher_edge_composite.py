"""
EdgeStat -- MLB pitcher edge composite (deep matchup synthesis).

Consumes:
  - mlb_lineup_quality_index.json (opposing lineup score 0-100)
  - mlb_pitcher_logs.json (pitcher ERA, K%, BB%, recent form)
  - mlb_pitcher_strikeouts_props.json (model K projection)
  - mlb_pitcher_outs_props.json (model outs projection)
  - mlb_pitcher_quality_start_props.json (P(QS))
  - mlb_pitcher_rest_advantage.json (days rest)

Produces per-pitcher composite "edge_score" (0-100) for tonight's start:
  Higher = stronger lean OVER on K, longer outings, QS yes.
  Lower  = stronger lean UNDER, opposing team total OVER lean.

Score breakdown:
  base = 50
  + lineup_weakness_factor: (60 - opp_lineup_score) / 1.5  (positive when facing weak lineup)
  + rest_factor: rest_days_above_avg * 4
  + form_factor: (recent_ERA - season_ERA) * -5  (better recent form = positive)
  + k_rate_factor: K_per_9 above 8.0 = +1 per 0.5 K9 above 8
  + walk_penalty: BB_per_9 above 3.0 = -1 per 0.3 above 3

Tiers:
  80+ ELITE_MATCHUP    — Top recommendation for K-OVER, QS-YES, ML-FAV
  65-79 STRONG         — Lean OVER on K, decent QS chance
  50-64 NEUTRAL        — No directional bias
  35-49 SOFT           — Lean UNDER on K, fade ML
  <35 BAD_SPOT          — Bullpen-game potential, fade K-OVER aggressively

Output: data/mlb_pitcher_edge_composite.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json")

LEAGUE_ERA = 4.20
LEAGUE_K9 = 8.5
LEAGUE_BB9 = 3.1


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


def _tier(score: float) -> str:
    if score >= 80: return "ELITE_MATCHUP"
    if score >= 65: return "STRONG"
    if score >= 50: return "NEUTRAL"
    if score >= 35: return "SOFT"
    return "BAD_SPOT"


def _lineup_score_for_pitcher(matchup: str, pitcher_side: str,
                              lineup_data: Dict[str, Any]) -> float:
    """Find opposing lineup score from lineup_quality_index data."""
    for g in (lineup_data.get("games") or []):
        if g.get("matchup") != matchup: continue
        # Pitcher on HOME side -> opposing lineup is AWAY
        opp_side = "away" if pitcher_side == "HOME" else "home"
        return _safe((g.get(opp_side) or {}).get("score"), 50.0)
    return 50.0


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    k_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))
    qs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json"))
    rest_data = _load(os.path.join(DATA_DIR, "mlb_pitcher_rest_advantage.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    # Index supporting prop modules by pitcher name
    def _idx_rows(d, key="pitcher"):
        rows = d.get("rows") or d.get("strong_edges") or []
        if not rows:
            for k in ("top_25_by_p_qs", "top_25_by_xK", "top_25_by_xOuts"):
                if k in d and isinstance(d[k], list):
                    rows = d[k]; break
        return {(r.get(key) or "").lower(): r for r in rows if isinstance(r, dict)}

    k_idx = _idx_rows(k_props)
    outs_idx = _idx_rows(outs_props)
    qs_idx = _idx_rows(qs_props)
    rest_idx = _idx_rows(rest_data)

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_l = sp_name.lower()
            sp_row = p_by_name.get(sp_l, {})
            stats = sp_row.get("stats") or {}

            era = _safe(stats.get("era"), LEAGUE_ERA)
            k9 = _safe(stats.get("k_per_9"), LEAGUE_K9)
            bb9 = _safe(stats.get("bb_per_9"), LEAGUE_BB9)
            recent_era = _safe(stats.get("recent_era"), era)

            opp_lineup = _lineup_score_for_pitcher(matchup, side, lineup_q)
            lineup_factor = (60.0 - opp_lineup) / 1.5  # +6 to +12 vs weak; -6 to -10 vs elite
            lineup_factor = max(-15, min(15, lineup_factor))

            rest_row = rest_idx.get(sp_l, {})
            days_rest = _safe(rest_row.get("days_rest"), 5.0)
            rest_factor = max(-3, min(8, (days_rest - 4.5) * 2))

            form_factor = max(-8, min(8, (era - recent_era) * 5))
            k_rate_factor = max(-4, min(8, (k9 - 8.0) / 0.5))
            walk_penalty = max(-6, min(0, -(bb9 - 3.0) / 0.3))

            score = 50.0 + lineup_factor + rest_factor + form_factor + k_rate_factor + walk_penalty
            score = max(10.0, min(100.0, score))
            score = round(score, 1)

            k_row = k_idx.get(sp_l, {})
            outs_row = outs_idx.get(sp_l, {})
            qs_row = qs_idx.get(sp_l, {})

            tier = _tier(score)

            # Directional lean recommendations
            lean: List[str] = []
            if tier in ("ELITE_MATCHUP", "STRONG"):
                lean += ["K_OVER", "OUTS_OVER", "QS_YES", "1ST_INN_ER_NO"]
            elif tier in ("SOFT", "BAD_SPOT"):
                lean += ["K_UNDER", "OPP_TT_OVER", "1ST_INN_ER_YES"]

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "era": era,
                "k_per_9": k9,
                "bb_per_9": bb9,
                "recent_era": recent_era,
                "days_rest": days_rest,
                "opp_lineup_score": opp_lineup,
                "factors": {
                    "lineup": round(lineup_factor, 1),
                    "rest": round(rest_factor, 1),
                    "form": round(form_factor, 1),
                    "k_rate": round(k_rate_factor, 1),
                    "walks": round(walk_penalty, 1),
                },
                "edge_score": score,
                "tier": tier,
                "model_proj": {
                    "xK": k_row.get("xK") or k_row.get("expected_strikeouts"),
                    "xOuts": outs_row.get("xOuts") or outs_row.get("expected_outs"),
                    "p_qs": qs_row.get("p_qs") or qs_row.get("p_quality_start"),
                },
                "directional_lean": lean,
            })

    rows.sort(key=lambda r: -r["edge_score"])

    n_elite = sum(1 for r in rows if r["tier"] == "ELITE_MATCHUP")
    n_strong = sum(1 for r in rows if r["tier"] == "STRONG")
    n_bad = sum(1 for r in rows if r["tier"] == "BAD_SPOT")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_elite_matchups": n_elite,
        "n_strong": n_strong,
        "n_bad_spots": n_bad,
        "method_note": "Deep composite: 50 + lineup_weakness + rest_adv + recent_form "
                       "+ K-rate - walk_rate. Tiers ELITE_MATCHUP/STRONG drive K_OVER, "
                       "OUTS_OVER, QS_YES leans; SOFT/BAD_SPOT drive K_UNDER, OPP_TT_OVER.",
        "rows": rows,
        "elite_matchups": [r for r in rows if r["tier"] == "ELITE_MATCHUP"],
        "bad_spots": [r for r in rows if r["tier"] == "BAD_SPOT"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitch-edge] {o['n_pitchers']} pitchers, {o['n_elite_matchups']} elite, "
          f"{o['n_strong']} strong, {o['n_bad_spots']} bad spots -> {OUT}")
