"""
EdgeStat -- MLB Pitcher hits allowed prop projections.

Common DK lines:
  - Hits allowed 4.5 over/under
  - Hits allowed 5.5 over/under
  - Hits allowed 6.5 over/under

Approach:
  expected_H = (WHIP - BB/9/4.1) * expected_IP  (approximate H per inning from WHIP - walks)
  OR more directly: H/9 * expected_IP / 9.
  Poisson approximation for the count.

Adjusters:
  - Opposing lineup batting avg
  - Park HR factor (hitter parks = more hits)
  - Pitcher form

Output: data/mlb_pitcher_hits_allowed_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_hits_allowed_props.json")

LEAGUE_OBP = 0.317
LEAGUE_BA = 0.247
LEAGUE_H_PER_9 = 8.2


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
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


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

            # Hits per 9 -- compute from WHIP minus walks, or direct H/9 if available
            whip = _safe(pitcher.get("whip") or pitcher.get("season", {}).get("whip"), 1.25)
            bb_per_9 = _safe(pitcher.get("bb_per_9") or pitcher.get("season", {}).get("bb_per_9"), 3.0)
            # WHIP * 9 = WH per game (hits + walks). Subtract walks per 9 to isolate hits per 9.
            h_per_9 = max(5.0, min(11.5, whip * 9 - bb_per_9))

            avg_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)
            form_delta = form_by_name.get((name or "").lower(), 0.0)

            base_hits = h_per_9 / 9.0 * avg_ip

            # Adjustments
            obp_mult = max(0.85, min(1.20, opp_obp / LEAGUE_OBP))
            park_mult = max(0.90, min(1.15, park_run_factor))
            form_mult = 1.0 - max(-0.10, min(0.10, form_delta * 0.10))

            expected_h = base_hits * obp_mult * park_mult * form_mult
            expected_h = max(2.0, min(9.0, expected_h))

            # Edge classification: book sets line at nearest 0.5, only flag STRONG when
            # within 0.75 of expected AND p in 62-72% range
            edge_class = "NONE"
            best_market = None
            nearest_line = round(expected_h - 0.5) + 0.5
            for line in (nearest_line, nearest_line + 0.5):
                if line < 3.5 or line > 8.5: continue
                if abs(expected_h - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, expected_h)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"H_OVER_{line}",
                                       "p": round(p_over, 3), "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"H_UNDER_{line}",
                                       "p": round(p_under, 3), "fair_odds": _american(p_under), "line": line}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "opp_team": away if side == "home" else home,
                "h_per_9": round(h_per_9, 2),
                "avg_ip": avg_ip,
                "opp_obp": opp_obp,
                "park_run_factor": park_run_factor,
                "expected_h": round(expected_h, 2),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Hits allowed = (WHIP × 9 - BB/9) / 9 × avg_IP × opp_OBP × park × form. "
                       "Poisson. STRONG only at nearest 0.5 line with 10%%+ edge vs -120 book.",
        "starters": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[h-allowed] {o['n_starters']} starters, {o['n_strong_edges']} strong edges -> {OUT}")
