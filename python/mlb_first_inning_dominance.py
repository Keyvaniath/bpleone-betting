"""
EdgeStat -- MLB first-inning dominance alerts.

Combines first-inning specific props to surface pitchers projected to
dominate the opening frame:
  - 1st inning ER probability low (<= 30%)
  - 1st inning K probability high (>= 55% to get 1+ K)
  - Pitcher form not COLD
  - Opposing lineup's top 1-3 hitters have K_OVER signal

DOMINANCE_1ST = 3+ aligned positive signals.

Output: data/mlb_first_inning_dominance.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_first_inning_dominance.json")


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
    first_er = _load(os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_er.json"))
    first_k = _load(os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_k.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json"))
    first_inn_run = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))

    # Pitcher 1st inning ER
    er_idx = {_norm(r.get("pitcher")): r
              for r in (first_er.get("rows") or []) if isinstance(r, dict)}

    # Pitcher 1st inning K
    k_idx = {_norm(r.get("pitcher")): r
             for r in (first_k.get("rows") or []) if isinstance(r, dict)}

    # Form
    form_idx = {_norm(r.get("pitcher")): r
                for r in (form.get("rows") or []) if isinstance(r, dict)}

    # Opp team first inning run probability
    fir_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_25_by_p"):
        for r in (first_inn_run.get(k) or []):
            if isinstance(r, dict):
                fir_idx[(r.get("matchup", ""), (r.get("side", "") or "").upper())] = (
                    _safe(r.get("p_yes") or r.get("p")))

    all_pitchers = set(er_idx) | set(k_idx)

    alerts: List[Dict[str, Any]] = []
    for name in all_pitchers:
        er_data = er_idx.get(name, {})
        k_data = k_idx.get(name, {})
        f_data = form_idx.get(name, {})

        p_no_er = _safe(er_data.get("p_no_er"))
        p_er = _safe(er_data.get("p_er")) or (1 - p_no_er if p_no_er > 0 else 0)
        p_k = _safe(k_data.get("p_k") or k_data.get("p_1plus_k") or k_data.get("p"))

        form_class = (f_data.get("trend") or f_data.get("form") or "").upper()
        form_ok = "COLD" not in form_class and "REGRESS" not in form_class

        # Opp first inning run prob (lower = better for pitcher)
        matchup = er_data.get("matchup") or k_data.get("matchup") or ""
        side = (er_data.get("side") or k_data.get("side") or "").upper()
        opp_side = "AWAY" if side == "HOME" else ("HOME" if side == "AWAY" else "")
        opp_fir_p = fir_idx.get((matchup, opp_side), 0)
        opp_fir_low = opp_fir_p > 0 and opp_fir_p <= 0.45

        signals: Dict[str, int] = {}
        signals["LOW_1ST_INN_ER_RISK"] = 1 if p_no_er >= 0.70 else 0
        signals["HIGH_1ST_INN_K"] = 1 if p_k >= 0.55 else 0
        signals["FORM_OK"] = 1 if form_ok and form_class else 0
        signals["OPP_LOW_1ST_INN_RUN"] = 1 if opp_fir_low else 0

        n_positive = sum(1 for v in signals.values() if v == 1)
        if n_positive < 2: continue

        if n_positive >= 4:
            tier = "DOMINANCE_1ST_ELITE"
        elif n_positive >= 3:
            tier = "DOMINANCE_1ST_STRONG"
        else:
            tier = "DOMINANCE_1ST_LEAN"

        alerts.append({
            "pitcher": er_data.get("pitcher") or k_data.get("pitcher") or name.title(),
            "matchup": matchup,
            "team": er_data.get("team") or k_data.get("team"),
            "p_no_er_1st": round(p_no_er, 3),
            "p_k_1st": round(p_k, 3),
            "form_class": form_class or None,
            "opp_p_1st_inn_run": round(opp_fir_p, 3),
            "n_positive_signals": n_positive,
            "signals": signals,
            "tier": tier,
            "recommended_markets": [
                "1st inning ER NO",
                "Pitcher 1+ K 1st inning YES",
                "1st inning run NO (opp)",
                "Pitcher records strikeout in 1st inning YES",
            ],
        })

    alerts.sort(key=lambda a: -a["n_positive_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "DOMINANCE_1ST_ELITE"),
        "n_strong": sum(1 for a in alerts if a["tier"] == "DOMINANCE_1ST_STRONG"),
        "method_note": "1st inning dominance. Signals: LOW_1ST_INN_ER_RISK "
                       "(p_no_er >= 70%), HIGH_1ST_INN_K (p_k >= 55%), FORM_OK, "
                       "OPP_LOW_1ST_INN_RUN (opp p_run <= 45%). ELITE = 4+; "
                       "STRONG = 3; LEAN = 2.",
        "alerts": alerts,
        "elite_strong": [a for a in alerts
                         if a["tier"] in ("DOMINANCE_1ST_ELITE",
                                          "DOMINANCE_1ST_STRONG")],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[1st-inn-dominance] {o['n_alerts']} alerts "
          f"({o['n_elite']} ELITE, {o['n_strong']} STRONG) -> {OUT}")
