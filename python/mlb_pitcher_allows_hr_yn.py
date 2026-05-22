"""
EdgeStat -- MLB pitcher to allow HR yes/no prop.

Popular DK alt: 'Pitcher to allow a HR yes/no'. Typical pricing:
  - HR-prone pitchers (Quintana, mid-tier): -130 to +110 YES
  - Aces with HR/9 < 1.0: +130 to +200
  - Elite HR-suppressors (Skenes, Skubal at home): +220 to +400

Method:
  expected_HR_allowed = HR_per_9 / 9 * expected_IP
  Where expected_IP from pitcher_outs_props or default ~5.2 IP.
  Adjust for opp lineup ISO + park HR factor.

  P(>= 1 HR allowed) = 1 - exp(-expected_HR_allowed)

  STRONG_YES at p in [0.62, 0.78] vs -150 book.
  STRONG_NO at p_no in [0.45, 0.60] vs +120 NO.

Output: data/mlb_pitcher_allows_hr_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_allows_hr_yn.json")

LEAGUE_HR_PER_9 = 1.20


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))

    parks = today.get("parks") or {}
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    outs_idx = {(r.get("pitcher") or "").lower(): r
                for r in (outs_props.get("rows") or []) if isinstance(r, dict)}

    games = matchups.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup = g.get("matchup") or ""
        park = g.get("park") or g.get("venue")
        park_hr_factor = _safe((parks.get(park) or {}).get("hr_factor"), 1.0) if isinstance(parks, dict) else 1.0

        for side, sp_field, opp_side_key in (
            ("HOME", "home_pitcher", "away"),
            ("AWAY", "away_pitcher", "home")
        ):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_row = p_by_name.get(sp_name.lower(), {})
            stats = sp_row.get("stats") or {}

            hr_per_9 = _safe(stats.get("hr_per_9"), LEAGUE_HR_PER_9)
            opp_lineup_ops = _safe((g.get(opp_side_key) or {}).get("ops"), 0.72)
            # Higher OPS lineups -> more HR threat
            lineup_hr_mult = max(0.80, min(1.30, 1.0 + (opp_lineup_ops - 0.72) * 0.8))

            outs_row = outs_idx.get(sp_name.lower(), {})
            expected_outs = _safe(outs_row.get("expected_outs") or outs_row.get("xOuts"), 16.0)
            expected_IP = expected_outs / 3.0  # convert outs to IP

            expected_hr = (hr_per_9 / 9.0) * expected_IP * lineup_hr_mult * park_hr_factor
            p_1plus_hr = 1 - math.exp(-expected_hr)
            p_no_hr = 1 - p_1plus_hr

            edge_class = "NONE"
            best_market = None
            # Tighter thresholds: require meaningful conviction (away from coinflip)
            if 0.65 <= p_1plus_hr <= 0.80:
                edge_class = "STRONG_YES"
                best_market = {"market": "PITCHER_ALLOWS_HR_YES",
                               "p": round(p_1plus_hr, 3),
                               "fair_odds": _american(p_1plus_hr)}
            elif 0.55 <= p_no_hr <= 0.68:
                edge_class = "STRONG_NO"
                best_market = {"market": "PITCHER_ALLOWS_HR_NO",
                               "p": round(p_no_hr, 3),
                               "fair_odds": _american(p_no_hr)}

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": sp_row.get("team_abbr"),
                "hr_per_9": round(hr_per_9, 2),
                "expected_IP": round(expected_IP, 2),
                "opp_lineup_ops": opp_lineup_ops,
                "lineup_hr_mult": round(lineup_hr_mult, 3),
                "park_hr_factor": round(park_hr_factor, 3),
                "expected_hr_allowed": round(expected_hr, 3),
                "p_1plus_hr": round(p_1plus_hr, 3),
                "p_no_hr": round(p_no_hr, 3),
                "fair_yes": _american(p_1plus_hr),
                "fair_no": _american(p_no_hr),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_1plus_hr"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(>=1 HR allowed) = 1 - exp(-hr_per_9/9 * expected_IP * "
                       "lineup_OPS_mult * park_HR_factor). STRONG_YES p in [0.62, 0.78] "
                       "vs -150 book; STRONG_NO p_no in [0.45, 0.60] vs +120 NO.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hr-allow] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
