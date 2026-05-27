"""
EdgeStat -- UFC per-fight preview synthesizer.

For each UFC fight, produces a unified preview combining:
  - Both fighters' confluence scores
  - Dominance alerts
  - Method of victory + first round finish + rounds OVER/UNDER signals

Each fight gets a tier:
  FIGHT_LOCK   = one fighter LOCK + opponent FADE
  FIGHT_STRONG = one fighter LOCK or both with significant edges
  FIGHT_LEAN   = at least 1 STRONG with finishing signal
  FIGHT_PASS   = no aligned signals

Output: data/ufc_fight_card_preview.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_fight_card_preview.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "ufc_fighter_confluence_score.json"))
    dom = _load(os.path.join(DATA_DIR, "ufc_fighter_dominance.json"))
    method = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    first_rd = _load(os.path.join(DATA_DIR, "ufc_first_round_finish.json"))
    rounds = _load(os.path.join(DATA_DIR, "ufc_rounds_over_under_props.json"))

    fighters_by_fight: Dict[str, List[Dict[str, Any]]] = {}
    for r in (conf.get("rows") or []):
        if not isinstance(r, dict): continue
        fight = r.get("fight") or ""
        fighters_by_fight.setdefault(fight, []).append(r)

    rounds_signal: Dict[str, str] = {}
    for r in (rounds.get("rows") or []):
        if not isinstance(r, dict): continue
        fight = r.get("matchup") or r.get("fight") or ""
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:
            rounds_signal[fight] = "UNDER"
        elif "OVER" in ec:
            rounds_signal[fight] = "OVER"

    previews: List[Dict[str, Any]] = []
    for fight, fighters in fighters_by_fight.items():
        if not fight: continue

        locks = [f for f in fighters if "LOCK" in (f.get("tier") or "")]
        strong = [f for f in fighters if "STRONG" in (f.get("tier") or "")]
        fades = [f for f in fighters if "FADE" in (f.get("tier") or "")]

        rounds_lean = rounds_signal.get(fight)

        if locks and fades:
            tier = "FIGHT_LOCK"
        elif locks:
            tier = "FIGHT_STRONG"
        elif strong and rounds_lean == "UNDER":
            tier = "FIGHT_LEAN"
        else:
            tier = "FIGHT_PASS"

        angle: List[str] = []
        for f in locks:
            angle.append(f"{f.get('fighter')} ML + finish + rounds UNDER")
        for fd in fades:
            angle.append(f"FADE {fd.get('fighter')} (opp ML)")
        if rounds_lean == "UNDER":
            angle.append(f"{fight} rounds UNDER")
        elif rounds_lean == "OVER":
            angle.append(f"{fight} rounds OVER (cardio fight)")

        previews.append({
            "fight": fight,
            "tier": tier,
            "n_locks": len(locks),
            "n_strong": len(strong),
            "n_fades": len(fades),
            "rounds_signal": rounds_lean,
            "fighter_summary": [
                {"fighter": f.get("fighter"), "tier": f.get("tier"),
                 "score": f.get("composite_score"),
                 "p_finish": f.get("p_finish")}
                for f in fighters
            ],
            "recommended_angles": angle,
        })

    tier_order = {"FIGHT_LOCK": 4, "FIGHT_STRONG": 3, "FIGHT_LEAN": 2, "FIGHT_PASS": 1}
    previews.sort(key=lambda p: -tier_order.get(p["tier"], 0))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fights": len(previews),
        "n_locks": sum(1 for p in previews if p["tier"] == "FIGHT_LOCK"),
        "n_strong": sum(1 for p in previews if p["tier"] == "FIGHT_STRONG"),
        "n_lean": sum(1 for p in previews if p["tier"] == "FIGHT_LEAN"),
        "method_note": "Per-fight UFC preview. FIGHT_LOCK = one fighter LOCK + "
                       "opp FADE; STRONG = one LOCK; LEAN = STRONG + rounds "
                       "UNDER signal.",
        "previews": previews,
        "locks_and_strong": [p for p in previews
                             if p["tier"] in ("FIGHT_LOCK", "FIGHT_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-fight-preview] {o['n_fights']} fights "
          f"({o['n_locks']} LOCK, {o['n_strong']} STRONG, "
          f"{o['n_lean']} LEAN) -> {OUT}")
