"""
EdgeStat -- F1 driver dominance alerts.

Surfaces drivers projected for an elite race weekend:
  - POLE_LEAN (qualifying P1 / front row probability >= 25%)
  - QUAL_TOP3 (qualifying top 3 probability >= 45%)
  - PODIUM_LIVE (podium finish probability >= 35%)
  - WIN_LIVE (race win probability >= 18%)
  - TOP10_LOCK (finishing top 10 probability >= 80%)
  - TRACK_FAVORABLE (track-specific historical performance positive)

DOMINANCE_ELITE = 5+ signals; STRONG = 3-4.

Output: data/f1_driver_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "f1_driver_dominance.json")


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
    qual = _load(os.path.join(DATA_DIR, "f1_qualifying_predictor.json"))
    podium = _load(os.path.join(DATA_DIR, "f1_podium_finish_props.json"))
    proj = _load(os.path.join(DATA_DIR, "f1_driver_projections.json"))
    track = _load(os.path.join(DATA_DIR, "f1_track_specific.json"))

    drivers: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return drivers.setdefault(key, {
            "driver": name,
            "race": r.get("race") or r.get("event") or r.get("circuit"),
            "signals": {},
            "scores": {},
        })

    # Qualifying
    for k in ("rows", "predictions"):
        for r in (qual.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("driver") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_pole = _safe(r.get("p_pole") or r.get("p_p1"))
            p_top3 = _safe(r.get("p_top3") or r.get("p_q_top3"))
            entry["signals"]["POLE_LEAN"] = 1 if p_pole >= 0.25 else 0
            entry["signals"]["QUAL_TOP3"] = 1 if p_top3 >= 0.45 else 0
            entry["scores"]["p_pole"] = round(p_pole, 3)
            entry["scores"]["p_qual_top3"] = round(p_top3, 3)

    # Podium / win
    for k in ("rows", "strong_edges"):
        for r in (podium.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("driver") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_podium = _safe(r.get("p_podium") or r.get("p"))
            p_win = _safe(r.get("p_win") or r.get("p_p1"))
            entry["signals"]["PODIUM_LIVE"] = 1 if p_podium >= 0.35 else 0
            entry["signals"]["WIN_LIVE"] = 1 if p_win >= 0.18 else 0
            entry["scores"]["p_podium"] = round(p_podium, 3)
            entry["scores"]["p_win"] = round(p_win, 3)

    # Driver projections (top 10 lock)
    for r in (proj.get("rows") or proj.get("drivers") or []):
        if not isinstance(r, dict): continue
        name = r.get("driver") or ""
        entry = _entry(name, r)
        if not entry: continue
        p_top10 = _safe(r.get("p_top10") or r.get("p_points"))
        entry["signals"]["TOP10_LOCK"] = 1 if p_top10 >= 0.80 else 0
        entry["scores"]["p_top10"] = round(p_top10, 3)

    # Track-specific (positive lean)
    for r in (track.get("rows") or track.get("drivers") or []):
        if not isinstance(r, dict): continue
        name = r.get("driver") or ""
        entry = _entry(name, r)
        if not entry: continue
        lean = (r.get("lean") or r.get("track_edge_class") or "").upper()
        if "POSITIVE" in lean or "STRONG" in lean or "FAVORABLE" in lean:
            entry["signals"]["TRACK_FAVORABLE"] = 1

    alerts: List[Dict[str, Any]] = []
    for key, entry in drivers.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        tier = "DOMINANCE_ELITE" if n >= 5 else "DOMINANCE_STRONG"
        alerts.append({
            "driver": entry["driver"],
            "race": entry["race"],
            "n_signals": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "DOMINANCE_ELITE"),
        "method_note": "F1 driver dominance synthesizer. 3+ aligned signals: "
                       "POLE_LEAN (>=25%), QUAL_TOP3 (>=45%), PODIUM_LIVE (>=35%), "
                       "WIN_LIVE (>=18%), TOP10_LOCK (>=80%), TRACK_FAVORABLE. "
                       "DOMINANCE_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_dominance": [a for a in alerts if a["tier"] == "DOMINANCE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f1-dominance] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
