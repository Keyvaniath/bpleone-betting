"""
EdgeStat -- MLB Pitcher Earned Runs (ER) prop projections.

Common DK/FD lines:
  - ER 1.5 over/under (popular for elite starters)
  - ER 2.5 over/under (the most common line)
  - ER 3.5 over/under (for back-end starters)

Approach:
  expected_ER = (ERA / 9) × expected_IP × matchup_mult × park_mult × form_mult
  Use Poisson distribution for ER count (since runs are discrete events).

Matchup_mult: tougher lineup OBP = more ER
Park_mult: hitter parks = more ER
Form_mult: hot pitcher = fewer ER

Outputs honest STRONG only when nearest 0.5 line gives 10%+ edge.

Output: data/mlb_pitcher_er_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_er_props.json")

LEAGUE_OBP = 0.317


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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    p_less = sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))
    return max(0.0, min(1.0, 1.0 - p_less))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_regression.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    form_by_name = {}
    for r in (form.get("rows") or form.get("pitchers") or []):
        nm = (r.get("name") or r.get("pitcher") or "").lower()
        if nm: form_by_name[nm] = _safe(r.get("delta") or r.get("z_score"), 0.0)

    parks = today.get("parks") or {}
    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        if "@" not in matchup_str: continue
        away, home = [s.strip().upper() for s in matchup_str.split("@", 1)]

        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        home_obp = _safe((g.get("home") or {}).get("obp"), LEAGUE_OBP)
        away_obp = _safe((g.get("away") or {}).get("obp"), LEAGUE_OBP)

        for side in ("home", "away"):
            opp_obp = away_obp if side == "home" else home_obp
            p_raw = g.get(f"{side}_pitcher")
            name = p_raw if isinstance(p_raw, str) else (p_raw or {}).get("name")
            pitcher = p_by_name.get((name or "").lower())
            if not pitcher and isinstance(p_raw, dict): pitcher = p_raw
            if not pitcher: continue

            era = _safe(pitcher.get("era") or pitcher.get("season", {}).get("era"), 4.20)
            avg_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)
            form_delta = form_by_name.get((name or "").lower(), 0.0)

            # Base ER expectation
            base_er = era / 9.0 * avg_ip
            # Opp OBP mult
            obp_mult = max(0.80, min(1.25, opp_obp / LEAGUE_OBP))
            # Park
            park_mult = max(0.85, min(1.20, park_run_factor))
            # Form: hot pitcher = fewer ER
            form_mult = 1.0 - max(-0.10, min(0.10, form_delta * 0.10))

            expected_er = base_er * obp_mult * park_mult * form_mult
            expected_er = max(0.3, min(6.0, expected_er))

            # Probabilities at each integer-cumulative line
            p_over_1_5 = _poisson_at_least(2, expected_er)
            p_over_2_5 = _poisson_at_least(3, expected_er)
            p_over_3_5 = _poisson_at_least(4, expected_er)
            p_under_1_5 = 1 - p_over_1_5
            p_under_2_5 = 1 - p_over_2_5
            p_under_3_5 = 1 - p_over_3_5

            # Edge classification -- only flag STRONG at the NEAREST 0.5 line
            # AND require 10%+ edge vs typical -120 book (p in [0.62, 0.72])
            edge_class = "NONE"
            best_market = None
            nearest_line = round(expected_er - 0.5) + 0.5
            for line in [nearest_line, nearest_line + 0.5]:
                if line not in (1.5, 2.5, 3.5): continue
                if abs(expected_er - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, expected_er)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"ER_OVER_{line}",
                                       "p": round(p_over, 3), "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"ER_UNDER_{line}",
                                       "p": round(p_under, 3), "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "opp_team": away if side == "home" else home,
                "era": era,
                "avg_ip": avg_ip,
                "opp_obp": opp_obp,
                "park_run_factor": park_run_factor,
                "form_delta": round(form_delta, 2),
                "expected_er": round(expected_er, 2),
                "p_over_1_5": round(p_over_1_5, 3),
                "p_over_2_5": round(p_over_2_5, 3),
                "p_over_3_5": round(p_over_3_5, 3),
                "p_under_1_5": round(p_under_1_5, 3),
                "p_under_2_5": round(p_under_2_5, 3),
                "p_under_3_5": round(p_under_3_5, 3),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "ER = (ERA/9) × IP × opp_OBP × park × form. Poisson distribution. "
                       "STRONG only at nearest 0.5 line with 10%%+ edge vs -120.",
        "starters": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[er-props] {o['n_starters']} starters, {o['n_strong_edges']} strong edges -> {OUT}")
