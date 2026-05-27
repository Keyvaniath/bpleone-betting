"""
EdgeStat -- UFC underdog finisher value alert.

Surfaces underdogs with elite finish probability:
  - ML underdog (American odds >= +150)
  - Finish probability >= 28%
  - First-round finish probability >= 14%
  - Power-style: KO >= 24% OR sub >= 14%

The value: underdogs paying +150 to +300 who finish 28-35% of the time
have positive EV vs the ML alone (because finishing is the most likely
underdog upset mode).

Output: data/ufc_underdog_finisher_alert.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_underdog_finisher_alert.json")


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
    matchup = _load(os.path.join(DATA_DIR, "ufc_matchup.json"))
    method = _load(os.path.join(DATA_DIR, "ufc_method_of_victory.json"))
    first_rd = _load(os.path.join(DATA_DIR, "ufc_first_round_finish.json"))

    # Build fighter -> ML odds map from matchup
    odds_by_fighter: Dict[str, float] = {}
    for r in (matchup.get("rows") or matchup.get("fights") or []):
        if not isinstance(r, dict): continue
        # Try both sides
        for prefix in ("fighter_a", "fighter_b", ""):
            name = r.get(prefix) if prefix else r.get("fighter")
            odds = r.get(f"{prefix}_odds") if prefix else r.get("odds")
            if name and odds:
                odds_by_fighter[_norm(name)] = _safe(odds)

    # Method idx
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

    underdog_finishers: List[Dict[str, Any]] = []
    for name, fighter_data in method_idx.items():
        odds = odds_by_fighter.get(name, 0)
        # Underdog: American odds >= +150
        if odds < 150: continue

        p_ko = _safe(fighter_data.get("p_ko") or fighter_data.get("p_ko_tko"))
        p_sub = _safe(fighter_data.get("p_sub"))
        p_finish = _safe(fighter_data.get("p_finish") or (p_ko + p_sub))

        first_data = first_idx.get(name, {})
        p_1st = _safe(first_data.get("p_1st_round_finish") or first_data.get("p_r1"))

        if p_finish < 0.28: continue

        # Value computation: implied prob = 100/(odds+100) for + lines
        implied_p = 100.0 / (odds + 100.0)
        edge = p_finish - implied_p

        flags: List[str] = []
        if p_finish >= 0.35:
            flags.append("HIGH_FINISH_PROB")
        if p_1st >= 0.14:
            flags.append("EARLY_FINISH_LIVE")
        if p_ko >= 0.24:
            flags.append("POWER_STYLE_KO")
        if p_sub >= 0.14:
            flags.append("SUB_STYLE")

        underdog_finishers.append({
            "fighter": fighter_data.get("fighter") or name.title(),
            "fight": fighter_data.get("matchup") or fighter_data.get("fight"),
            "american_odds": int(odds),
            "implied_p_win": round(implied_p, 3),
            "p_finish": round(p_finish, 3),
            "p_1st_round_finish": round(p_1st, 3),
            "p_ko": round(p_ko, 3),
            "p_sub": round(p_sub, 3),
            "value_edge_pp": round(edge * 100, 2),
            "flags": flags,
            "recommended_markets": [
                f"{fighter_data.get('fighter') or name.title()} ML (+value)",
                ("KO/TKO method" if p_ko >= 0.24 else ""),
                ("Submission method" if p_sub >= 0.14 else ""),
                ("Round 1 finish" if p_1st >= 0.14 else ""),
            ],
        })

    underdog_finishers.sort(key=lambda u: -u["value_edge_pp"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_underdogs": len(underdog_finishers),
        "method_note": "UFC underdog finisher value. ML +150 or longer AND "
                       "p_finish >= 28%. Compares model finish prob to implied "
                       "ML probability (100/(odds+100)) -> edge_pp. Underdogs "
                       "who finish are positive-EV ML plays.",
        "underdog_finishers": underdog_finishers,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-underdog] {o['n_underdogs']} value underdog finishers -> {OUT}")
