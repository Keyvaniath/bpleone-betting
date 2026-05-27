"""
EdgeStat -- UFC fighter confluence score.

Composite per-fighter score combining:
  - ufc_fighter_dominance (n_signals)
  - ufc_method_of_victory (p_finish, p_ko, p_sub)
  - ufc_first_round_finish (p_1st_finish)
  - ufc_rounds_over_under_props
  - ufc_strikes_takedowns_props

Score formula:
  score = dom_signals * 2.5 + p_finish * 15 + p_1st_finish * 20
        + rounds_under_signal * 3 + strikes_or_td_over_signal

FIGHTER_LOCK = score >= 18 with dom_signals >= 4
FIGHTER_STRONG = 11-17
FIGHTER_FADE = score <= 2

Output: data/ufc_fighter_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_fighter_confluence_score.json")


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
    dom = _load(os.path.join(DATA_DIR, "ufc_fighter_dominance.json"))
    method = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    first_rd = _load(os.path.join(DATA_DIR, "ufc_first_round_finish.json"))
    rounds = _load(os.path.join(DATA_DIR, "ufc_rounds_over_under_props.json"))
    strikes_td = _load(os.path.join(DATA_DIR, "ufc_strikes_takedowns_props.json"))

    dom_idx = {_norm(a.get("fighter")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}

    method_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (method.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("fighter") or r.get("favorite") or "")
                if key and key not in method_idx:
                    method_idx[key] = r

    first_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (first_rd.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("fighter") or r.get("favorite") or "")
                if key and key not in first_idx:
                    first_idx[key] = r

    # Rounds UNDER lean: tag both fighters in fight
    rounds_under_fights: set = set()
    for r in (rounds.get("rows") or []):
        if not isinstance(r, dict): continue
        ec = (r.get("edge_class") or "").upper()
        if "UNDER" in ec:
            rounds_under_fights.add(r.get("matchup") or r.get("fight") or "")

    strikes_td_idx = {_norm(r.get("fighter")): r for r in (strikes_td.get("rows") or []) if isinstance(r, dict)}

    all_fighters = (set(dom_idx) | set(method_idx) | set(first_idx) | set(strikes_td_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_fighters:
        d = dom_idx.get(name, {})
        mr = method_idx.get(name, {})
        fr = first_idx.get(name, {})
        st = strikes_td_idx.get(name, {})

        dom_signals = int(d.get("n_signals", 0) or 0)
        p_finish = _safe(mr.get("p_finish") or (
            _safe(mr.get("p_ko") or mr.get("p_ko_tko")) + _safe(mr.get("p_sub"))))
        p_1st = _safe(fr.get("p_1st_round_finish") or fr.get("p_r1"))

        fight = d.get("fight") or mr.get("matchup") or fr.get("matchup") or ""
        rounds_under_lean = 3 if fight in rounds_under_fights else 0

        strikes_ec = (st.get("strikes_edge_class") or "").upper()
        td_ec = (st.get("takedowns_edge_class") or "").upper()
        strikes_or_td_signal = (1.5 if "OVER" in strikes_ec else 0) + (1.5 if "OVER" in td_ec else 0)

        score = (dom_signals * 2.5
                 + p_finish * 15
                 + p_1st * 20
                 + rounds_under_lean
                 + strikes_or_td_signal)

        has_data = (dom_signals > 0 or p_finish > 0 or p_1st > 0
                    or rounds_under_lean > 0 or strikes_or_td_signal > 0)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 18 and dom_signals >= 4:
            tier = "FIGHTER_LOCK"
        elif score >= 11:
            tier = "FIGHTER_STRONG"
        elif score <= 2:
            tier = "FIGHTER_FADE"
        else:
            tier = "FIGHTER_NEUTRAL"

        rows.append({
            "fighter": (d.get("fighter") or mr.get("fighter") or fr.get("fighter")
                        or st.get("fighter") or name.title()),
            "fight": fight,
            "dom_signals": dom_signals,
            "p_finish": round(p_finish, 3),
            "p_1st_round_finish": round(p_1st, 3),
            "rounds_under_lean": rounds_under_lean > 0,
            "strikes_over": "OVER" in strikes_ec,
            "td_over": "OVER" in td_ec,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fighters": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "FIGHTER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "FIGHTER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "FIGHTER_FADE"),
        "method_note": "Composite UFC fighter score. dom_signals*2.5 + "
                       "p_finish*15 + p_1st_finish*20 + rounds_under_lean(3) + "
                       "strikes_or_td_over*1.5. LOCK >= 18 with dom>=4; "
                       "STRONG 11-17.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "FIGHTER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "FIGHTER_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-confluence] {o['n_fighters']} fighters "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
