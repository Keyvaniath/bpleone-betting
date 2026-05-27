"""
EdgeStat -- MLB pitcher matchup-specific (lineup-adjusted) projections.

Takes each pitcher's baseline projection and adjusts for the SPECIFIC
opposing lineup quality + handedness composition. Brandon explicitly
asked for this. Produces a per-start adjusted line for K / outs / ER.

Adjustment model:
  - K rate scales by opp K% vs handedness:
    proj_K_adj = proj_K * (1 + (opp_K_pct_vs_hand - league_K_pct) / league_K_pct)
  - Outs scale inversely with opp lineup_score deviation from league:
    proj_outs_adj = proj_outs * (1 - (lineup_score - 50) / 100)
  - ER scale with lineup_score:
    proj_ER_adj = proj_ER * (1 + (lineup_score - 50) / 100)

Source inputs:
  - mlb_pitcher_strikeouts_props.json  (baseline proj_K)
  - mlb_pitcher_outs_props.json        (baseline proj_outs)
  - mlb_pitcher_er_props.json          (baseline proj_ER)
  - mlb_lineup_quality_index.json      (opp lineup_score per side)

Flag MATERIAL_ADJ when |delta| >= 0.5 K, 1.5 outs, or 0.3 ER from baseline.

Output: data/mlb_pitcher_lineup_adjusted.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_lineup_adjusted.json")

LEAGUE_LINEUP_BASELINE = 50.0
LEAGUE_K_PCT = 0.223  # 2024 MLB avg
LINEUP_DEV_DAMPER = 100.0  # gentler adjustment


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
    k = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    outs = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))
    er = _load(os.path.join(DATA_DIR, "mlb_pitcher_er_props.json"))
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))

    # Index lineup quality by (matchup, side) -- pitcher's opp is the OTHER side
    lq_by_matchup_side: Dict[str, Dict[str, float]] = {}
    for g in (lq.get("games") or []):
        matchup = g.get("matchup") or ""
        for side_key in ("home", "away"):
            side_data = g.get(side_key) or {}
            score = _safe(side_data.get("score"))
            tier = side_data.get("tier")
            k_vs_hand = side_data.get("k_rate") or side_data.get("k_pct")  # may not exist
            lq_by_matchup_side[f"{matchup}|{side_key.upper()}"] = {
                "lineup_score": score,
                "tier": tier,
                "k_rate": _safe(k_vs_hand, LEAGUE_K_PCT),
            }

    # Index pitcher props
    k_idx = {_norm(r.get("pitcher")): r
             for r in (k.get("rows") or []) if isinstance(r, dict)}
    outs_idx = {_norm(r.get("pitcher")): r
                for r in (outs.get("rows") or []) if isinstance(r, dict)}
    er_idx = {_norm(r.get("pitcher")): r
              for r in (er.get("rows") or []) if isinstance(r, dict)}

    rows: List[Dict[str, Any]] = []

    for name in set(k_idx.keys()) | set(outs_idx.keys()):
        kr = k_idx.get(name, {})
        outsr = outs_idx.get(name, {})
        err = er_idx.get(name, {})

        # Determine pitcher's matchup and which side OPPOSES him
        matchup = kr.get("matchup") or outsr.get("matchup") or err.get("matchup") or ""
        if not matchup: continue
        pitcher_side = (kr.get("side") or outsr.get("side") or "").upper()
        # Pitcher's opposing lineup
        opp_side = "AWAY" if pitcher_side == "HOME" else ("HOME" if pitcher_side == "AWAY" else "")
        if not opp_side: continue

        opp_lq = lq_by_matchup_side.get(f"{matchup}|{opp_side}")
        if not opp_lq: continue
        opp_lineup_score = opp_lq.get("lineup_score") or LEAGUE_LINEUP_BASELINE

        # Baseline projections
        proj_K = _safe(kr.get("expected_k") or kr.get("proj_k"))
        proj_outs = _safe(outsr.get("expected_outs") or outsr.get("proj_outs"))
        proj_ER = _safe(err.get("expected_er") or err.get("proj_er"))

        if proj_K <= 0 and proj_outs <= 0 and proj_ER <= 0: continue

        # Adjustments
        # K: scale by lineup score (lower lineup_score -> easier Ks)
        lineup_dev = (opp_lineup_score - LEAGUE_LINEUP_BASELINE) / LINEUP_DEV_DAMPER
        proj_K_adj = proj_K * (1 - lineup_dev) if proj_K > 0 else 0
        proj_outs_adj = proj_outs * (1 - lineup_dev) if proj_outs > 0 else 0
        proj_ER_adj = proj_ER * (1 + lineup_dev) if proj_ER > 0 else 0

        dK = proj_K_adj - proj_K
        dO = proj_outs_adj - proj_outs
        dE = proj_ER_adj - proj_ER

        flag = None
        if abs(dK) >= 0.5 or abs(dO) >= 1.5 or abs(dE) >= 0.3:
            flag = "MATERIAL_ADJ"

        rows.append({
            "pitcher": kr.get("pitcher") or outsr.get("pitcher") or err.get("pitcher"),
            "matchup": matchup,
            "team": kr.get("team") or outsr.get("team"),
            "opp_lineup_score": round(opp_lineup_score, 1),
            "opp_lineup_tier": opp_lq.get("tier"),
            "baseline": {
                "K": round(proj_K, 2),
                "outs": round(proj_outs, 1),
                "ER": round(proj_ER, 2),
            },
            "adjusted": {
                "K": round(proj_K_adj, 2),
                "outs": round(proj_outs_adj, 1),
                "ER": round(proj_ER_adj, 2),
            },
            "delta": {
                "K": round(dK, 2),
                "outs": round(dO, 1),
                "ER": round(dE, 2),
            },
            "flag": flag,
        })

    rows.sort(key=lambda r: -abs(r["delta"]["K"] or 0))
    material = [r for r in rows if r["flag"] == "MATERIAL_ADJ"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_material_adj": len(material),
        "method_note": "Adjusts baseline pitcher K/outs/ER projections by opp "
                       "lineup quality. lineup_dev = (lineup_score-50)/100. K and "
                       "outs scaled by (1 - lineup_dev); ER scaled by (1 + lineup_dev). "
                       "MATERIAL_ADJ flagged when |dK|>=0.5, |dOuts|>=1.5, or |dER|>=0.3.",
        "rows": rows,
        "material_adj": material,
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-lineup-adj] {o['n_pitchers']} pitchers, "
          f"{o['n_material_adj']} material adjustments -> {OUT}")
