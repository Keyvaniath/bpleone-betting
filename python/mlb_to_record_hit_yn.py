"""
EdgeStat -- MLB to-record-a-hit yes/no per batter.

Common DK line: "1+ hit yes/no". Books price between -200 (top hitters) and
+150 (weak hitters facing elite pitchers). Most-bet prop in baseball.

Method:
  P(>=1 hit) = 1 - (1 - hit_rate_per_PA) ^ expected_PA
  hit_rate_per_PA = batter AVG × AB-per-PA ratio (~0.92).
  Adjusted by opposing pitcher's BABIP allowed + park.

Output: data/mlb_to_record_hit_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_to_record_hit_yn.json")

LEAGUE_AVG = 0.247
LEAGUE_OBP = 0.317
LEAGUE_HIT_PER_PA = 0.227


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


def _expected_pa(order: int) -> float:
    if order <= 3: return 4.4
    if order <= 6: return 4.1
    return 3.7


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    parks = today.get("parks") or {}
    lvr_idx = {}
    for row in (lvr.get("all_batters") or []):
        nm = (row.get("batter") or "").lower()
        if nm: lvr_idx[nm] = row
    p_idx = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher_name = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")
            opp_p = p_idx.get((opp_pitcher_name or "").lower(), {})
            # Pitcher hit-allowed rate proxy (BAA - batting avg against)
            opp_whip = _safe(opp_p.get("whip") or opp_p.get("season", {}).get("whip"), 1.25)
            # WHIP × 9 / TBF ≈ hits-allowed/PA. WHIP=1.25 typical → 0.23 hits per PA
            opp_hits_per_pa = max(0.18, min(0.30, opp_whip * 0.20))

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # Batter hit rate (split-adjusted)
                split_avg = _safe(lvr_row.get("split_avg"), LEAGUE_AVG)
                split_pa = int(_safe(lvr_row.get("split_pa"), 0))
                blended_avg = ((split_pa * split_avg + 80 * LEAGUE_AVG) / (split_pa + 80)
                               if split_pa > 0 else LEAGUE_AVG)
                batter_hit_per_pa = max(0.15, min(0.35, blended_avg * 0.92))

                # Effective hit/PA = average of batter + pitcher rates, adjusted by park
                hit_per_pa = (batter_hit_per_pa + opp_hits_per_pa) / 2
                hit_per_pa *= max(0.92, min(1.10, park_run_factor ** 0.4))
                pa = _expected_pa(order)

                # P(>= 1 hit) = 1 - (1 - rate) ^ PA
                p_no_hit = (1 - hit_per_pa) ** pa
                p_hit = 1 - p_no_hit

                edge_class = "NONE"
                best_market = None
                # Book lines: YES typically -200 to -150 for top hitters.
                # STRONG_YES if model says >= 80%% (vs -200 book = 67%% breakeven)
                # STRONG_NO if model says <= 50%% (vs typical +120 NO = 45%%)
                if p_hit >= 0.80:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "TO_RECORD_HIT_YES", "p": round(p_hit, 3),
                                   "fair_odds": _american(p_hit)}
                elif p_hit <= 0.50:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "TO_RECORD_HIT_NO", "p": round(p_no_hit, 3),
                                   "fair_odds": _american(p_no_hit)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "opp_pitcher": opp_pitcher_name,
                    "blended_avg": round(blended_avg, 3),
                    "batter_hit_per_pa": round(batter_hit_per_pa, 3),
                    "opp_hits_per_pa": round(opp_hits_per_pa, 3),
                    "expected_pa": pa,
                    "p_hit": round(p_hit, 3),
                    "p_no_hit": round(p_no_hit, 3),
                    "fair_yes": _american(p_hit),
                    "fair_no": _american(p_no_hit),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_hit"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(hit) = 1 - (1 - effective_hit_per_PA)^E[PA]. Effective rate = "
                       "avg(batter_hit_per_PA, opp_hit_allowed_per_PA) × park^0.4. "
                       "STRONG_YES >= 80%% (book -200 = 67%%). STRONG_NO <= 50%% (book ~+120).",
        "top_25_by_p_hit": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[hit-yn] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
