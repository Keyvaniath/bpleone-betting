"""
EdgeStat -- UFC fighter dominance alerts.

UFC counterpart to other sport dominance synthesizers. Surfaces fighters
projected for a finish-heavy outing:
  - FINISH_LIKELY (any-finish probability >= 55%)
  - FIRST_ROUND_FINISH (first round finish >= 25%)
  - STRIKES_OVER (volume striker projecting OVER)
  - TAKEDOWNS_OVER (grappler projecting OVER)
  - METHOD_KO_LEAN (KO/TKO probability >= 35%)
  - METHOD_SUB_LEAN (submission probability >= 18%)
  - ROUNDS_UNDER (fight not going distance)

DOMINANCE_ELITE = 5+ signals; STRONG = 3-4.

Output: data/ufc_fighter_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_fighter_dominance.json")


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
    method = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    first_rd = _load(os.path.join(DATA_DIR, "ufc_first_round_finish.json"))
    rounds = _load(os.path.join(DATA_DIR, "ufc_rounds_over_under_props.json"))
    strikes_td = _load(os.path.join(DATA_DIR, "ufc_strikes_takedowns_props.json"))

    fighters: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return fighters.setdefault(key, {
            "fighter": name,
            "fight": r.get("matchup") or r.get("fight") or r.get("match"),
            "signals": {},
            "scores": {},
        })

    # Method (likely KO/Sub by fighter)
    for k in ("rows", "strong_edges"):
        for r in (method.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("fighter") or r.get("favorite") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_ko = _safe(r.get("p_ko") or r.get("p_ko_tko"))
            p_sub = _safe(r.get("p_sub") or r.get("p_submission"))
            p_any = _safe(r.get("p_finish") or (p_ko + p_sub))
            entry["signals"]["FINISH_LIKELY"] = 1 if p_any >= 0.55 else 0
            entry["signals"]["METHOD_KO_LEAN"] = 1 if p_ko >= 0.35 else 0
            entry["signals"]["METHOD_SUB_LEAN"] = 1 if p_sub >= 0.18 else 0
            entry["scores"]["p_finish"] = round(p_any, 3)
            entry["scores"]["p_ko"] = round(p_ko, 3)
            entry["scores"]["p_sub"] = round(p_sub, 3)

    # First round finish
    for k in ("rows", "strong_edges"):
        for r in (first_rd.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("fighter") or r.get("favorite") or ""
            entry = _entry(name, r)
            if not entry: continue
            p_1st = _safe(r.get("p_1st_round_finish") or r.get("p_r1"))
            entry["signals"]["FIRST_ROUND_FINISH"] = 1 if p_1st >= 0.25 else 0
            entry["scores"]["p_1st_finish"] = round(p_1st, 3)

    # Rounds UNDER (finish-heavy fights)
    for r in (rounds.get("rows") or []):
        if not isinstance(r, dict): continue
        # Rounds line is fight-level not fighter-level, but tag both fighters
        ec = (r.get("edge_class") or "").upper()
        fight_str = r.get("matchup") or r.get("fight") or ""
        if "UNDER" not in ec: continue
        # Try to credit both fighters in this fight
        for name in (r.get("fighter_a"), r.get("fighter_b")):
            if not name: continue
            entry = _entry(name, r)
            if not entry: continue
            entry["signals"]["ROUNDS_UNDER"] = 1

    # Strikes / takedowns OVERs
    for r in (strikes_td.get("rows") or []):
        if not isinstance(r, dict): continue
        name = r.get("fighter") or ""
        entry = _entry(name, r)
        if not entry: continue
        ec_strikes = (r.get("strikes_edge_class") or "").upper()
        ec_td = (r.get("takedowns_edge_class") or "").upper()
        if "OVER" in ec_strikes:
            entry["signals"]["STRIKES_OVER"] = 1
        if "OVER" in ec_td:
            entry["signals"]["TAKEDOWNS_OVER"] = 1

    alerts: List[Dict[str, Any]] = []
    for key, entry in fighters.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        tier = "DOMINANCE_ELITE" if n >= 5 else "DOMINANCE_STRONG"
        alerts.append({
            "fighter": entry["fighter"],
            "fight": entry["fight"],
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
        "method_note": "UFC dominance synthesizer. 3+ aligned signals across "
                       "FINISH_LIKELY (p_finish>=55%), FIRST_ROUND_FINISH (>=25%), "
                       "METHOD_KO_LEAN (>=35%), METHOD_SUB_LEAN (>=18%), "
                       "STRIKES_OVER, TAKEDOWNS_OVER, ROUNDS_UNDER. "
                       "DOMINANCE_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_dominance": [a for a in alerts if a["tier"] == "DOMINANCE_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-dominance] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
