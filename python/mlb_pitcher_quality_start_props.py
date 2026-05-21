"""
EdgeStat -- MLB pitcher quality start (QS) yes/no prop.

Quality Start = 6+ IP AND <=3 ER. Common DK line: -110 to +110 each side.

Joint probability:
  P(QS) = P(IP >= 6) × P(ER <= 3 | IP >= 6)

Approach:
  - P(IP >= 6) from normal distribution around projected_IP with sigma=1.2
  - P(ER <= 3 | IP >= 6) from Poisson on expected_ER_in_6_IP = era/9 × 6

Output: data/mlb_pitcher_quality_start_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json")

LEAGUE_OBP = 0.317
IP_STDDEV = 1.2


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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_most(k: int, lam: float) -> float:
    """P(X <= k)"""
    if lam <= 0: return 1.0 if k >= 0 else 0.0
    return max(0.0, min(1.0, sum(_poisson_pmf(i, lam) for i in range(k + 1))))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

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
            pitcher = p_by_name.get((name or "").lower()) or (p_raw if isinstance(p_raw, dict) else None)
            if not pitcher: continue

            era = _safe(pitcher.get("era") or pitcher.get("season", {}).get("era"), 4.20)
            avg_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)

            # Adjust projected IP by opposing OBP (better lineup = shorter outing)
            obp_mult_ip = max(0.85, min(1.10, LEAGUE_OBP / opp_obp))
            projected_ip = avg_ip * obp_mult_ip

            # P(IP >= 6) from Normal distribution
            z = (projected_ip - 6.0) / IP_STDDEV
            p_ip_ge_6 = _norm_cdf(z)

            # Expected ER in 6 IP (the QS threshold)
            obp_mult_er = max(0.85, min(1.20, opp_obp / LEAGUE_OBP))
            park_mult = max(0.90, min(1.15, park_run_factor))
            expected_er_in_6 = (era / 9 * 6) * obp_mult_er * park_mult

            # P(ER <= 3 | reached 6 IP) ~ Poisson at most 3
            p_er_le_3 = _poisson_at_most(3, expected_er_in_6)

            p_qs = p_ip_ge_6 * p_er_le_3
            p_no_qs = 1 - p_qs

            edge_class = "NONE"
            best_market = None
            # Book lines -110 to +110. STRONG_YES at 60%%+ (vs -110 = 52% breakeven).
            if 0.62 <= p_qs <= 0.75:
                edge_class = "STRONG_YES"
                best_market = {"market": "QUALITY_START_YES", "p": round(p_qs, 3),
                               "fair_odds": _american(p_qs)}
            elif 0.62 <= p_no_qs <= 0.75:
                edge_class = "STRONG_NO"
                best_market = {"market": "QUALITY_START_NO", "p": round(p_no_qs, 3),
                               "fair_odds": _american(p_no_qs)}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "era": era,
                "avg_ip": avg_ip,
                "projected_ip": round(projected_ip, 2),
                "opp_obp": opp_obp,
                "park_run_factor": park_run_factor,
                "p_ip_ge_6": round(p_ip_ge_6, 3),
                "expected_er_in_6": round(expected_er_in_6, 2),
                "p_er_le_3": round(p_er_le_3, 3),
                "p_qs": round(p_qs, 3),
                "p_no_qs": round(p_no_qs, 3),
                "fair_qs_yes": _american(p_qs),
                "fair_qs_no": _american(p_no_qs),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_qs"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(QS) = P(IP>=6) × P(ER<=3 | reached 6 IP). "
                       "IP via Normal sigma=1.2. ER via Poisson on era/9 × 6.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[qs-prop] {o['n_starters']} starters, {o['n_strong_edges']} strong -> {OUT}")
