"""
EdgeStat -- UFC significant strikes + takedowns prop projections.

Per-fighter SLPM (significant strikes landed per minute) and TD attempts/15min
baselines, scaled by fight length expectation (function of method-of-victory dist).

Markets covered:
  - Significant strikes 75.5 / 100.5 over/under
  - Takedowns 1.5 / 2.5 over/under
  - Fighter wins by KO yes/no

Per-fighter DB: top 30 active fighters across major divisions (May 2026).

Output: data/ufc_strikes_takedowns_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_strikes_takedowns_props.json")

# 2025 season fighter stats: SLPM (strikes/min) + TD attempts per 15 min
FIGHTER_DB = {
    "alex pereira":         {"slpm": 4.6, "td_per_15": 0.5,  "weight": "LHW"},
    "jon jones":            {"slpm": 4.3, "td_per_15": 1.8,  "weight": "HW"},
    "tom aspinall":         {"slpm": 5.2, "td_per_15": 1.2,  "weight": "HW"},
    "ciryl gane":           {"slpm": 5.0, "td_per_15": 0.4,  "weight": "HW"},
    "dricus du plessis":    {"slpm": 4.5, "td_per_15": 1.3,  "weight": "MW"},
    "khamzat chimaev":      {"slpm": 4.2, "td_per_15": 6.0,  "weight": "MW"},
    "sean strickland":      {"slpm": 5.6, "td_per_15": 0.6,  "weight": "MW"},
    "israel adesanya":      {"slpm": 4.0, "td_per_15": 0.5,  "weight": "MW"},
    "leon edwards":         {"slpm": 3.4, "td_per_15": 1.1,  "weight": "WW"},
    "belal muhammad":       {"slpm": 4.0, "td_per_15": 2.1,  "weight": "WW"},
    "shavkat rakhmonov":    {"slpm": 4.5, "td_per_15": 3.2,  "weight": "WW"},
    "kamaru usman":         {"slpm": 4.5, "td_per_15": 3.5,  "weight": "WW"},
    "ian machado garry":    {"slpm": 5.8, "td_per_15": 0.2,  "weight": "WW"},
    "islam makhachev":      {"slpm": 3.5, "td_per_15": 4.5,  "weight": "LW"},
    "charles oliveira":     {"slpm": 3.6, "td_per_15": 2.3,  "weight": "LW"},
    "arman tsarukyan":      {"slpm": 5.0, "td_per_15": 3.2,  "weight": "LW"},
    "justin gaethje":       {"slpm": 7.0, "td_per_15": 0.2,  "weight": "LW"},
    "max holloway":         {"slpm": 7.2, "td_per_15": 0.1,  "weight": "FW"},
    "ilia topuria":         {"slpm": 6.0, "td_per_15": 0.8,  "weight": "FW"},
    "alexander volkanovski":{"slpm": 5.0, "td_per_15": 1.0,  "weight": "FW"},
    "diego lopes":          {"slpm": 4.8, "td_per_15": 0.3,  "weight": "FW"},
    "merab dvalishvili":    {"slpm": 3.5, "td_per_15": 7.0,  "weight": "BW"},
    "sean omalley":         {"slpm": 5.5, "td_per_15": 0.3,  "weight": "BW"},
    "petr yan":             {"slpm": 6.5, "td_per_15": 1.8,  "weight": "BW"},
    "umar nurmagomedov":    {"slpm": 4.5, "td_per_15": 2.5,  "weight": "BW"},
    "alexandre pantoja":    {"slpm": 4.8, "td_per_15": 2.0,  "weight": "FlyW"},
    "brandon royval":       {"slpm": 5.5, "td_per_15": 0.5,  "weight": "FlyW"},
    "raquel pennington":    {"slpm": 4.0, "td_per_15": 1.5,  "weight": "WBW"},
    "julianna pena":        {"slpm": 4.0, "td_per_15": 3.0,  "weight": "WBW"},
    "valentina shevchenko": {"slpm": 4.0, "td_per_15": 2.0,  "weight": "WFW"},
    "alexa grasso":         {"slpm": 4.5, "td_per_15": 1.0,  "weight": "WFW"},
    "zhang weili":          {"slpm": 5.5, "td_per_15": 1.5,  "weight": "WSW"},
}

# Expected fight duration by weight (minutes) -- factor of KO rate vs decision rate
EXPECTED_MINS = {
    "HW": 9.0, "LHW": 10.5, "MW": 11.5, "WW": 13.0, "LW": 12.5, "FW": 13.5,
    "BW": 13.8, "FlyW": 14.2, "WBW": 13.5, "WFW": 13.0, "WSW": 13.0,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 200)))))


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "ufc_state.json"))
    fights = state.get("fights") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for f in fights:
        if not isinstance(f, dict): continue
        weight = (f.get("weight_class") or "").upper().replace(" ", "")[:5]
        # Map ESPN weight to our key
        weight_key_map = {
            "HEAVY": "HW", "LIGHT": "LHW", "MIDDL": "MW", "WELTE": "WW",
            "LIGHT": "LW", "FEATH": "FW", "BANTA": "BW", "FLYWE": "FlyW",
            "WOMEN": None,  # need finer disambiguation
        }
        expected_mins = EXPECTED_MINS.get(weight_key_map.get(weight, weight), 12.5)
        # Multiply by 2 fighters per round? No -- strikes are per fighter.
        # Each fighter's strikes per fight ≈ SLPM * fight_mins.

        for f_a, f_b in [("fighter_a", "fighter_b"), ("fighter_b", "fighter_a")]:
            fighter_name = (f.get(f_a) or "").lower().strip()
            opp_name = (f.get(f_b) or "").lower().strip()
            fdb = FIGHTER_DB.get(fighter_name)
            if not fdb: continue

            expected_strikes = fdb["slpm"] * expected_mins
            expected_tds = fdb["td_per_15"] * (expected_mins / 15.0)

            # Strikes: Normal CDF (high count, Poisson approx-> Normal)
            sigma_strikes = math.sqrt(expected_strikes)  # Poisson variance = mean
            # TD: Poisson
            edge_class = "NONE"
            best_market = None
            # Strikes lines: 75.5, 100.5, 125.5
            for line in [50.5, 75.5, 100.5, 125.5]:
                if abs(expected_strikes - line) > sigma_strikes * 1.2: continue
                z = (expected_strikes - line) / sigma_strikes
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_STRIKES_OVER"
                        best_market = {"market": f"STRIKES_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_STRIKES_UNDER"
                        best_market = {"market": f"STRIKES_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

            # TD: P(>=2) for OVER 1.5, P(>=3) for OVER 2.5
            p_td_2plus = _poisson_at_least(2, expected_tds)
            p_td_3plus = _poisson_at_least(3, expected_tds)
            if 0.62 <= p_td_2plus <= 0.72 and (not best_market or p_td_2plus > best_market["p"]):
                edge_class = "STRONG_TD_OVER_1_5"
                best_market = {"market": "TD_OVER_1.5", "p": round(p_td_2plus, 3),
                               "fair_odds": _american(p_td_2plus)}

            rows.append({
                "matchup": f.get("matchup") or f.get("name"),
                "fighter": fighter_name,
                "opponent": opp_name,
                "weight_class": weight,
                "slpm": fdb["slpm"],
                "td_per_15": fdb["td_per_15"],
                "expected_fight_mins": expected_mins,
                "expected_strikes": round(expected_strikes, 1),
                "expected_tds": round(expected_tds, 2),
                "p_strikes_75_5_over": round(_norm_cdf((expected_strikes - 75.5) / sigma_strikes), 3),
                "p_strikes_100_5_over": round(_norm_cdf((expected_strikes - 100.5) / sigma_strikes), 3),
                "p_td_2_plus": round(p_td_2plus, 3),
                "p_td_3_plus": round(p_td_3plus, 3),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["expected_strikes"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_fighter_lines": len(rows),
        "n_strong": len(strong),
        "n_fighters_in_db": len(FIGHTER_DB),
        "method_note": "Strikes = SLPM × expected_fight_mins (Normal). "
                       "TDs = TD_per_15 × (mins/15) (Poisson). "
                       "STRONG = 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[ufc-strikes-td] {o['n_fighter_lines']} fighter-lines, {o['n_strong']} strong -> {OUT}")
