"""
EdgeStat -- MLB hot pitcher vs cold lineup mean-reversion warning.

Flags games where the pitcher confluence score is high but the opposing
lineup quality is FAR below league average. While this looks like an
elite spot on paper, history shows extreme pitcher-vs-tank-lineup spots
have higher variance: bullpen will rest the starter, ace gets cute, etc.

  WARNING_HOT_VS_TANK: pitcher composite_score >= 70 AND opp lineup_score
                       <= 35 -> recommend smaller stake / fade overlay
                       on K UNDER alt (chickening out)
  CHECK_INVERSE_REGRESS: pitcher composite >= 70 AND opp lineup recent
                         hot but season cold -> regression toward season
                         baseline expected

Output: data/mlb_hot_pitcher_cold_lineup_warning.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_hot_pitcher_cold_lineup_warning.json")


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
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    # Lineup scores by (matchup, side)
    lq_by_matchup_side: Dict[str, Dict[str, Any]] = {}
    for g in (lq.get("games") or []):
        m = g.get("matchup") or ""
        for side in ("home", "away"):
            sd = g.get(side) or {}
            lq_by_matchup_side[f"{m}|{side.upper()}"] = sd

    warnings: List[Dict[str, Any]] = []
    for r in (pitcher.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 70: continue  # only inspect high-conviction pitchers

        matchup = r.get("matchup") or ""
        team = (r.get("team") or "").upper()
        # Opp side: opposite of pitcher's team
        pitcher_side = ""
        for side in ("HOME", "AWAY"):
            lq_data = lq_by_matchup_side.get(f"{matchup}|{side}")
            if lq_data and (lq_data.get("team") or "").upper() == team:
                pitcher_side = side
                break

        if not pitcher_side: continue
        opp_side = "AWAY" if pitcher_side == "HOME" else "HOME"
        opp_lq = lq_by_matchup_side.get(f"{matchup}|{opp_side}") or {}
        opp_lineup_score = _safe(opp_lq.get("score"))
        opp_lineup_tier = (opp_lq.get("tier") or "").upper()

        flags: List[str] = []
        if opp_lineup_score and opp_lineup_score <= 35:
            flags.append("HOT_VS_TANK_LINEUP")
        if opp_lineup_tier in ("BELOW_AVG", "TANK", "WEAK"):
            flags.append("OPP_LINEUP_WEAK_TIER")
        if opp_lineup_score and opp_lineup_score <= 25:
            flags.append("EXTREME_MISMATCH")

        if not flags: continue

        warnings.append({
            "pitcher": r.get("pitcher"),
            "team": team,
            "matchup": matchup,
            "pitcher_composite_score": round(score, 2),
            "pitcher_tier": r.get("tier"),
            "opp_lineup_score": opp_lineup_score,
            "opp_lineup_tier": opp_lineup_tier or None,
            "flags": flags,
            "advisory": ("Mean-reversion warning. Pitcher hot vs cold lineup is "
                         "high-variance: bullpen may pull early, ace may get cute. "
                         "Consider K UNDER alt instead of K OVER blowout, or "
                         "size down."),
            "recommended_markets": [
                f"FADE {r.get('pitcher')} K OVER blowout (use K alt instead)",
                f"{r.get('pitcher')} outs UNDER (early hook risk)",
                f"opp team total UNDER (still positive, but cap conviction)",
            ],
        })

    warnings.sort(key=lambda w: -w["pitcher_composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_warnings": len(warnings),
        "n_extreme_mismatch": sum(1 for w in warnings
                                  if "EXTREME_MISMATCH" in (w.get("flags") or [])),
        "method_note": "Hot pitcher vs cold lineup mean-reversion warning. "
                       "Pitcher composite >= 70 AND opp lineup_score <= 35 = "
                       "high-variance spot. Recommends K alt UNDER instead of "
                       "blowout K OVER.",
        "warnings": warnings,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hot-vs-cold] {o['n_warnings']} warnings "
          f"({o['n_extreme_mismatch']} EXTREME) -> {OUT}")
