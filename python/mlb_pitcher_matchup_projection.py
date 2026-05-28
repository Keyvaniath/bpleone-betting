"""
EdgeStat -- MLB pitcher matchup-specific projection.

Pure-model (no book line). Joins per-pitcher feeds into one projected
stat line vs the SPECIFIC opponent lineup tonight:

  proj_ip   from ERA quality + rest (deeper when sharp + rested)
  proj_k    from expected_k (opp-K% + park adjusted) + lineup K delta
  proj_er   from ERA/recent-ERA blend * IP, scaled by opp lineup quality
  proj_bb   from BB/9 * IP
  p_qs      model quality-start prob (from edge feed or IP/ER heuristic)

Tiers each start (ACE_SPOT / STRONG / NEUTRAL / FADE_RISK) and emits
recommended markets. Anchors K/ER/outs leans independent of book lines.

Output: data/mlb_pitcher_matchup_projection.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_matchup_projection.json")


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


def _idx(data, key="pitcher"):
    return {_norm(r.get(key)): r
            for r in (data.get("rows") or []) if isinstance(r, dict)}


def run() -> Dict[str, Any]:
    edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    kprop = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    conf = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_starter_recent_form_index.json"))

    edge_idx = _idx(edge)
    kprop_idx = _idx(kprop)
    conf_idx = _idx(conf)
    form_idx = _idx(form)

    names = set(edge_idx) | set(kprop_idx) | set(conf_idx)

    rows: List[Dict[str, Any]] = []
    for name in names:
        e = edge_idx.get(name, {})
        k = kprop_idx.get(name, {})
        c = conf_idx.get(name, {})
        f = form_idx.get(name, {})

        pitcher = e.get("pitcher") or k.get("pitcher") or c.get("pitcher") or name.title()
        matchup = e.get("matchup") or k.get("matchup") or c.get("matchup") or "?"
        team = e.get("team") or k.get("team") or c.get("team")

        era = _safe(e.get("era") or k.get("era"), 4.0)
        recent_era = _safe(e.get("recent_era") or f.get("recent_era"), era)
        k9 = _safe(e.get("k_per_9") or k.get("k_per_9"), 8.0)
        bb9 = _safe(e.get("bb_per_9"), 3.0)
        days_rest = _safe(e.get("days_rest"), 5.0)
        opp_lineup = _safe(e.get("opp_lineup_score"), 50.0)
        expected_k = _safe(k.get("expected_k"))
        opp_k_mult = _safe(k.get("opp_k_mult"), 1.0)
        park_k = _safe(k.get("park_k_factor"), 1.0)
        delta_k_lineup = _safe(c.get("delta_K_lineup_adj"))
        p_qs_feed = None
        mp = e.get("model_proj") if isinstance(e.get("model_proj"), dict) else {}
        if mp and mp.get("p_qs") is not None:
            p_qs_feed = _safe(mp.get("p_qs"))

        # --- projected innings: sharper ERA + more rest -> deeper outing ---
        era_blend = 0.55 * recent_era + 0.45 * era
        proj_ip = 5.3 + (4.2 - era_blend) * 0.18
        if days_rest < 4: proj_ip -= 0.4
        elif days_rest >= 6: proj_ip += 0.2
        proj_ip = max(4.0, min(7.0, proj_ip))

        # --- projected K: prefer adjusted expected_k, else rate * IP ---
        if expected_k > 0:
            proj_k = expected_k + 0.5 * delta_k_lineup
        else:
            proj_k = k9 * proj_ip / 9.0 * opp_k_mult * park_k + delta_k_lineup
        proj_k = max(0.0, proj_k)

        # --- projected ER: ERA blend scaled by opp lineup quality ---
        lineup_mult = 1.0 + (opp_lineup - 50.0) / 100.0 * 0.5
        proj_er = era_blend * proj_ip / 9.0 * lineup_mult
        proj_er = max(0.0, proj_er)

        # --- projected BB ---
        proj_bb = bb9 * proj_ip / 9.0

        # --- quality-start prob ---
        if p_qs_feed is not None:
            p_qs = p_qs_feed
        else:
            p_qs = 0.0
            if proj_ip >= 6.0: p_qs += 0.45
            if proj_er <= 3.0: p_qs += 0.35
            p_qs = min(0.95, p_qs + 0.1)

        # --- tier the start ---
        if proj_k >= 7.0 and proj_er <= 2.5:
            tier = "ACE_SPOT"
        elif proj_k >= 6.0 and proj_er <= 3.2:
            tier = "STRONG"
        elif proj_er >= 4.0:
            tier = "FADE_RISK"
        else:
            tier = "NEUTRAL"

        markets: List[str] = []
        if proj_k >= 6.5: markets.append("K OVER")
        if proj_k >= 8.0: markets.append("8+ K alt")
        if p_qs >= 0.5: markets.append("quality start YES")
        if proj_ip >= 6.0: markets.append("outs OVER 17.5")
        if proj_er >= 4.0: markets.append("ER OVER / fade pitcher")
        if not markets: markets.append("no strong matchup lean")

        rows.append({
            "pitcher": pitcher,
            "team": team,
            "matchup": matchup,
            "opp_lineup_score": round(opp_lineup, 1),
            "days_rest": round(days_rest, 1),
            "proj_ip": round(proj_ip, 2),
            "proj_k": round(proj_k, 2),
            "proj_er": round(proj_er, 2),
            "proj_bb": round(proj_bb, 2),
            "p_quality_start": round(p_qs, 3),
            "lineup_k_delta": round(delta_k_lineup, 2),
            "tier": tier,
            "recommended_markets": markets,
        })

    # Rank: ACE_SPOT/STRONG first, then by projected K
    order = {"ACE_SPOT": 0, "STRONG": 1, "NEUTRAL": 2, "FADE_RISK": 3}
    rows.sort(key=lambda r: (order.get(r["tier"], 9), -r["proj_k"]))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_ace_spot": sum(1 for r in rows if r["tier"] == "ACE_SPOT"),
        "n_strong": sum(1 for r in rows if r["tier"] == "STRONG"),
        "n_fade_risk": sum(1 for r in rows if r["tier"] == "FADE_RISK"),
        "method_note": "Matchup-specific pitcher projection. proj_ip from ERA "
                       "blend (.55 recent/.45 season) + rest; proj_k from "
                       "opp/park-adj expected_k + lineup K delta; proj_er = "
                       "ERA_blend*IP/9 scaled by opp_lineup_score; p_qs from "
                       "edge feed or IP/ER heuristic. Tiers: ACE_SPOT "
                       "(K>=7,ER<=2.5), STRONG, NEUTRAL, FADE_RISK (ER>=4).",
        "rows": rows,
        "ace_spots": [r for r in rows if r["tier"] == "ACE_SPOT"],
        "fade_risks": [r for r in rows if r["tier"] == "FADE_RISK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-pitcher-matchup] {o['n_pitchers']} starters projected "
          f"({o['n_ace_spot']} ACE_SPOT, {o['n_strong']} STRONG, "
          f"{o['n_fade_risk']} FADE_RISK) -> {OUT}")
