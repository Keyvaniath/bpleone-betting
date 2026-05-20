"""
EdgeStat -- MLB Pitcher Outs Recorded prop projections.

"Outs recorded" is a niche but high-edge market. Common lines:
  - 16.5 outs (5.5 IP)
  - 17.5 outs
  - 18.5 outs (6 IP -- the "quality start" line)
  - 19.5 outs

Closely tied to expected IP. Skewed by:
  - Pitch count limits (rookies, returning from injury)
  - Manager hooks (does this pitcher get pulled early in tight games?)
  - Opposing lineup quality (high-OBP teams force more pitches)
  - Park run factor (hitter parks shorten outings)

Approach:
  expected_IP = season_avg_IP × matchup_mult × manager_hook_mult
  outs = expected_IP × 3
  Normal distribution around mean with sigma ~ 3 outs (1 inning)

Output: data/mlb_pitcher_outs_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json")

OUTS_STDDEV = 3.0  # ~1 IP variance per start
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


def _norm_cdf(x):
    """Std normal CDF (Abramowitz approximation)."""
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
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    pitch_count = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    pc_by_name = {}
    for row in (pitch_count.get("rows") or pitch_count.get("starters") or []):
        nm = (row.get("name") or row.get("pitcher") or "").lower()
        if nm: pc_by_name[nm] = row

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

            # Base avg IP
            season_ip = _safe(pitcher.get("avg_ip") or pitcher.get("season", {}).get("avg_ip"), 5.3)
            # Pitch-count specific projection (more accurate if available)
            pc_row = pc_by_name.get((name or "").lower())
            if pc_row:
                projected_ip = _safe(pc_row.get("projected_ip"), season_ip)
            else:
                projected_ip = season_ip

            # Adjustments
            obp_mult = max(0.85, min(1.10, LEAGUE_OBP / opp_obp))  # tougher lineup = fewer IP
            park_mult = max(0.92, min(1.05, (1.0 - (park_run_factor - 1.0) * 0.3)))
            expected_ip = projected_ip * obp_mult * park_mult
            expected_outs = expected_ip * 3

            # Lines: 14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5
            line_probs = {}
            for line in [14.5, 15.5, 16.5, 17.5, 18.5, 19.5, 20.5]:
                # Normal CDF: P(outs > line)
                z = (expected_outs - line) / OUTS_STDDEV
                p_over = _norm_cdf(z)
                line_probs[f"line_{line}"] = {
                    "p_over": round(p_over, 3),
                    "p_under": round(1 - p_over, 3),
                    "fair_odds_over": _american(p_over),
                    "fair_odds_under": _american(1 - p_over),
                }

            # Edge classification -- only flag STRONG when within +/- 2 outs of the line
            # (book lines are typically the closest 0.5-out level to expected_outs).
            # This avoids "98% UNDER 20.5 against a -2000 book line" false-positives.
            # Edge classification: book sets the line CLOSE to expected_outs (within 1
            # out usually). Only evaluate the nearest 0.5 line. Real edge = significant
            # model disagreement vs the book's coin-flip line.
            edge_class = "NONE"
            best_market = None
            nearest_line = round(expected_outs * 2) / 2  # round to nearest 0.5
            if nearest_line == expected_outs: nearest_line -= 0.5  # avoid exact-tie line
            # Try +/- 0.5 from nearest
            for line_val in [nearest_line - 0.5, nearest_line, nearest_line + 0.5]:
                # Distance must be <= 1.5 outs (book sets lines tight)
                if abs(expected_outs - line_val) > 1.5: continue
                # Recompute prob for THIS line
                z = (expected_outs - line_val) / OUTS_STDDEV
                p_over = _norm_cdf(z)
                p_under = 1 - p_over
                # STRONG = 10%+ edge vs typical -120 book line (54.5% breakeven)
                # so p >= 0.65 with cap at 0.72 (above that the book has priced it in)
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"OUTS_OVER_{line_val}",
                                       "p": round(p_over, 3), "fair_odds": _american(p_over)}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"OUTS_UNDER_{line_val}",
                                       "p": round(p_under, 3), "fair_odds": _american(p_under)}
                # STANDARD = 5-10% edge
                elif 0.56 <= p_over < 0.62:
                    if not best_market:
                        edge_class = "STANDARD_OVER"
                        best_market = {"market": f"OUTS_OVER_{line_val}",
                                       "p": round(p_over, 3), "fair_odds": _american(p_over)}
                elif 0.56 <= p_under < 0.62:
                    if not best_market:
                        edge_class = "STANDARD_UNDER"
                        best_market = {"market": f"OUTS_UNDER_{line_val}",
                                       "p": round(p_under, 3), "fair_odds": _american(p_under)}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": home if side == "home" else away,
                "opp_team": away if side == "home" else home,
                "season_avg_ip": round(season_ip, 2),
                "projected_ip": round(expected_ip, 2),
                "expected_outs": round(expected_outs, 1),
                "opp_obp": opp_obp,
                "park_run_factor": park_run_factor,
                "line_probs": line_probs,
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -(r["best_market"]["p"] if r["best_market"] else 0))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Normal CDF on expected_outs = expected_IP × 3. "
                       "expected_IP adjusts season avg by opp OBP and park run factor.",
        "starters": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[outs-props] {o['n_starters']} starters, {o['n_strong_edges']} strong edges -> {OUT}")
