"""
EdgeStat -- MLB starter dominant-outing alert synthesizer.

Surfaces starters who project for a complete dominant outing — all 4 signals
aligned positively:
  - K_OVER (high strikeout projection)
  - OUTS_OVER (deep into game, 18+ outs / 6+ IP)
  - QS_YES (quality start probability >= 60%)
  - 1ST_INN_ER_NO (low early-game scoring risk)
  - BLOWUP_NO (4+ ER unlikely)

A 'dominant outing' alert means all signals point to elite performance —
strong basis for a multi-leg parlay including pitcher props.

Output: data/mlb_dominant_outing_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_dominant_outing_alerts.json")


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
    k_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))
    qs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json"))
    er_first = _load(os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_er.json"))
    blowup = _load(os.path.join(DATA_DIR, "mlb_pitcher_blowup_alert.json"))
    six_plus = _load(os.path.join(DATA_DIR, "mlb_pitcher_6plus_IP_yn.json"))

    # Index by pitcher
    k_idx = {(r.get("pitcher") or "").lower(): r
             for r in (k_props.get("rows") or []) if isinstance(r, dict)}
    outs_idx = {(r.get("pitcher") or "").lower(): r
                for r in (outs_props.get("rows") or []) if isinstance(r, dict)}
    qs_idx = {}
    for k in ("rows", "top_25_by_p_qs", "strong_edges"):
        for r in (qs_props.get(k) or []):
            if isinstance(r, dict):
                qs_idx.setdefault((r.get("pitcher") or "").lower(), r)
    er_first_idx = {(r.get("pitcher") or "").lower(): r
                    for r in (er_first.get("rows") or []) if isinstance(r, dict)}
    blowup_idx = {(r.get("pitcher") or "").lower(): r
                  for r in (blowup.get("rows") or []) if isinstance(r, dict)}
    six_plus_idx = {(r.get("pitcher") or "").lower(): r
                    for r in (six_plus.get("rows") or []) if isinstance(r, dict)}

    # Aggregate per pitcher
    all_pitchers = set(k_idx.keys()) | set(outs_idx.keys())
    alerts: List[Dict[str, Any]] = []

    for name in all_pitchers:
        kr = k_idx.get(name, {})
        outsr = outs_idx.get(name, {})
        qsr = qs_idx.get(name, {})
        ef = er_first_idx.get(name, {})
        bu = blowup_idx.get(name, {})
        sp = six_plus_idx.get(name, {})

        # Each signal: 1 if positive (dominant), 0 if neutral, -1 if negative
        signals: Dict[str, int] = {}
        k_edge = (kr.get("edge_class") or "")
        signals["K_OVER"] = 1 if "OVER" in k_edge else 0
        outs_edge = (outsr.get("edge_class") or "")
        signals["OUTS_OVER"] = 1 if "OVER" in outs_edge else 0
        p_qs = _safe(qsr.get("p_qs") or qsr.get("p_quality_start"))
        signals["QS_YES"] = 1 if p_qs >= 0.60 else 0
        p_no_er = _safe(ef.get("p_no_er"))
        signals["1ST_INN_ER_NO"] = 1 if p_no_er >= 0.65 else 0
        p_no_blowup = _safe(bu.get("p_no_4plus_ER"))
        signals["BLOWUP_NO"] = 1 if p_no_blowup >= 0.78 else 0
        p_6plus = _safe(sp.get("p_6plus_IP"))
        signals["6PLUS_IP_YES"] = 1 if p_6plus >= 0.62 else 0

        positive_count = sum(1 for v in signals.values() if v == 1)
        if positive_count < 3: continue  # need at least 3 positive signals

        pitcher_display = kr.get("pitcher") or outsr.get("pitcher") or name.title()
        matchup = kr.get("matchup") or outsr.get("matchup") or ""

        alerts.append({
            "pitcher": pitcher_display,
            "matchup": matchup,
            "team": kr.get("team") or outsr.get("team"),
            "expected_K": _safe(kr.get("expected_k")),
            "expected_outs": _safe(outsr.get("expected_outs")),
            "p_qs": round(p_qs, 3),
            "p_no_er_first": round(p_no_er, 3),
            "p_no_blowup": round(p_no_blowup, 3),
            "p_6plus_IP": round(p_6plus, 3),
            "n_positive_signals": positive_count,
            "signals": signals,
            "tier": "ELITE" if positive_count >= 5 else "STRONG",
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "ELITE"),
        "method_note": "Surfaces starters with 3+ aligned positive signals (K_OVER, "
                       "OUTS_OVER, QS_YES, 1ST_INN_ER_NO, BLOWUP_NO, 6PLUS_IP_YES). "
                       "ELITE tier = 5+ signals; STRONG = 3-4 signals.",
        "alerts": alerts,
        "elite_outings": [a for a in alerts if a["tier"] == "ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[dom-outing] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
