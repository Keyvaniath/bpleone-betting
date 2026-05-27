"""
EdgeStat -- F1 race preview synthesizer.

For each race weekend, produces a unified preview combining:
  - Top driver confluence picks (LOCK, STRONG)
  - Dominance alerts
  - Qualifying + podium + win + top10 signals
  - Track-specific historical performance

Output: data/f1_race_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "f1_race_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "f1_driver_confluence_score.json"))
    qual = _load(os.path.join(DATA_DIR, "f1_qualifying_predictor.json"))
    podium = _load(os.path.join(DATA_DIR, "f1_podium_finish_props.json"))

    # Group drivers by race
    drivers_by_race: Dict[str, List[Dict[str, Any]]] = {}
    for r in (conf.get("rows") or []):
        if not isinstance(r, dict): continue
        race = r.get("race") or "?"
        drivers_by_race.setdefault(race, []).append(r)

    # Top podium pick per race
    podium_pick: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (podium.get(k) or []):
            if not isinstance(r, dict): continue
            race = r.get("race", "?")
            p_podium = r.get("p_podium") or r.get("p") or 0
            existing = podium_pick.get(race)
            if not existing or p_podium > existing.get("p_podium", 0):
                podium_pick[race] = {"driver": r.get("driver"), "p_podium": p_podium}

    # Top pole pick per race
    pole_pick: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "predictions"):
        for r in (qual.get(k) or []):
            if not isinstance(r, dict): continue
            race = r.get("race", "?")
            p_pole = r.get("p_pole") or r.get("p_p1") or 0
            existing = pole_pick.get(race)
            if not existing or p_pole > existing.get("p_pole", 0):
                pole_pick[race] = {"driver": r.get("driver"), "p_pole": p_pole}

    previews: List[Dict[str, Any]] = []
    for race, drivers in drivers_by_race.items():
        drivers.sort(key=lambda p: -(p.get("composite_score") or 0))

        locks = [d for d in drivers if "LOCK" in (d.get("tier") or "")]
        strong = [d for d in drivers if "STRONG" in (d.get("tier") or "")]
        fades = [d for d in drivers if "FADE" in (d.get("tier") or "")]

        if locks and fades:
            tier = "RACE_LOCK"
        elif locks or len(strong) >= 3:
            tier = "RACE_STRONG"
        elif len(strong) >= 1:
            tier = "RACE_LEAN"
        else:
            tier = "RACE_PASS"

        pp = podium_pick.get(race, {})
        pl = pole_pick.get(race, {})

        angle: List[str] = []
        for d in locks:
            angle.append(f"{d.get('driver')} podium + qual top-3")
        if pl.get("driver"):
            angle.append(f"{pl.get('driver')} pole position (p={round(pl.get('p_pole', 0), 3)})")
        if pp.get("driver"):
            angle.append(f"{pp.get('driver')} podium (p={round(pp.get('p_podium', 0), 3)})")
        for s in strong[:2]:
            angle.append(f"{s.get('driver')} top 10 finish")
        for fd in fades[:3]:
            angle.append(f"FADE {fd.get('driver')} (DNF / outside top 10)")

        previews.append({
            "race": race,
            "tier": tier,
            "n_locks": len(locks),
            "n_strong": len(strong),
            "n_fades": len(fades),
            "pole_pick": pl.get("driver"),
            "podium_pick": pp.get("driver"),
            "top_5_contenders": [
                {"driver": d.get("driver"), "tier": d.get("tier"),
                 "score": d.get("composite_score"),
                 "p_podium": d.get("p_podium"), "p_win": d.get("p_win")}
                for d in drivers[:5]
            ],
            "recommended_angles": angle,
        })

    tier_order = {"RACE_LOCK": 4, "RACE_STRONG": 3, "RACE_LEAN": 2, "RACE_PASS": 1}
    previews.sort(key=lambda p: -tier_order.get(p["tier"], 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_races": len(previews),
        "n_locks": sum(1 for p in previews if p["tier"] == "RACE_LOCK"),
        "n_strong": sum(1 for p in previews if p["tier"] == "RACE_STRONG"),
        "method_note": "Per-race F1 preview. RACE_LOCK = 1+ LOCK + 1+ FADE; "
                       "STRONG = 1+ LOCK or 3+ STRONGs; LEAN = 1+ STRONG.",
        "previews": previews,
        "locks_and_strong": [p for p in previews
                             if p["tier"] in ("RACE_LOCK", "RACE_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f1-race-preview] {o['n_races']} races "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG) -> {OUT}")
