"""
EdgeStat -- MLB pitcher fade alerts (negative-side counterpart to dominant outing).

Surfaces starters projecting for a BAD outing -- aligned negative signals:
  - K_UNDER (low strikeout projection / UNDER lean)
  - OUTS_UNDER (won't go deep -- 16- outs / <5 IP)
  - QS_NO (quality start probability <= 35%)
  - 1ST_INN_ER_YES (high early-game scoring risk)
  - BLOWUP_RISK (4+ ER likely)

A 'fade' alert means all signals point to a struggle -- strong basis for
opposing team total OVER and pitcher prop UNDERs.

Pairs naturally with mlb_offensive_explosion_alerts on the opposing side
for confluence parlay signal.

Output: data/mlb_pitcher_fade_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_fade_alerts.json")


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

    # Index by pitcher (case-insensitive)
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

    all_pitchers = set(k_idx.keys()) | set(outs_idx.keys())
    alerts: List[Dict[str, Any]] = []

    for name in all_pitchers:
        kr = k_idx.get(name, {})
        outsr = outs_idx.get(name, {})
        qsr = qs_idx.get(name, {})
        ef = er_first_idx.get(name, {})
        bu = blowup_idx.get(name, {})
        sp = six_plus_idx.get(name, {})

        # Negative signals (1 = bad spot, 0 = neutral/positive)
        signals: Dict[str, int] = {}
        k_edge = (kr.get("edge_class") or "")
        signals["K_UNDER"] = 1 if "UNDER" in k_edge else 0
        outs_edge = (outsr.get("edge_class") or "")
        signals["OUTS_UNDER"] = 1 if "UNDER" in outs_edge else 0
        p_qs = _safe(qsr.get("p_qs") or qsr.get("p_quality_start"))
        signals["QS_NO"] = 1 if 0 < p_qs <= 0.35 else 0
        p_er_first = _safe(ef.get("p_er")) or (1 - _safe(ef.get("p_no_er")) if ef.get("p_no_er") else 0)
        signals["1ST_INN_ER_RISK"] = 1 if p_er_first >= 0.35 else 0
        p_blowup = _safe(bu.get("p_4plus_ER")) or (1 - _safe(bu.get("p_no_4plus_ER")) if bu.get("p_no_4plus_ER") else 0)
        signals["BLOWUP_RISK"] = 1 if p_blowup >= 0.22 else 0
        p_6plus = _safe(sp.get("p_6plus_IP"))
        signals["6PLUS_IP_NO"] = 1 if 0 < p_6plus <= 0.45 else 0

        positive_count = sum(1 for v in signals.values() if v == 1)
        if positive_count < 3: continue  # need 3+ negative signals

        pitcher_display = kr.get("pitcher") or outsr.get("pitcher") or name.title()
        matchup = kr.get("matchup") or outsr.get("matchup") or ""

        alerts.append({
            "pitcher": pitcher_display,
            "matchup": matchup,
            "team": kr.get("team") or outsr.get("team"),
            "expected_K": _safe(kr.get("expected_k")),
            "expected_outs": _safe(outsr.get("expected_outs")),
            "p_qs": round(p_qs, 3),
            "p_er_first": round(p_er_first, 3),
            "p_blowup": round(p_blowup, 3),
            "p_6plus_IP": round(p_6plus, 3),
            "n_negative_signals": positive_count,
            "signals": signals,
            "tier": "FADE_ELITE" if positive_count >= 5 else "FADE_STRONG",
        })

    alerts.sort(key=lambda a: -a["n_negative_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite_fades": sum(1 for a in alerts if a["tier"] == "FADE_ELITE"),
        "method_note": "Surfaces starters with 3+ aligned NEGATIVE signals (K_UNDER, "
                       "OUTS_UNDER, QS_NO, 1ST_INN_ER_RISK, BLOWUP_RISK, 6PLUS_IP_NO). "
                       "FADE_ELITE tier = 5+ signals; FADE_STRONG = 3-4 signals. "
                       "Pair with mlb_offensive_explosion_alerts on opposing team "
                       "for confluence parlay signal.",
        "alerts": alerts,
        "elite_fades": [a for a in alerts if a["tier"] == "FADE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-fade] {o['n_alerts']} alerts ({o['n_elite_fades']} ELITE) -> {OUT}")
