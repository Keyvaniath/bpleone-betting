"""
EdgeStat -- MLB Total Bases (TB) prop projections.

For each slate batter, projects:
  - Expected TB per game (1B + 2*2B + 3*3B + 4*HR)
  - P(TB >= 1), P(TB >= 2), P(TB >= 3) given Poisson approximation
  - Fair odds vs typical book lines
  - Edge classification (STRONG / STANDARD / NONE)

Method:
  Per-PA TB rate from batter season splits, conditioned on opposing pitcher's
  TB allowed per PA. Expected PA = ~4.2 for 1-3 hitters, ~3.8 for 4-9 hitters.
  Poisson approximation for TB distribution.

Source data:
  - data/matchups.json (lineups + pitchers)
  - data/mlb_batter_lvr_splits.json (batter season + matchup)
  - data/mlb_pitcher_logs.json (pitcher TB allowed)
  - data/today.json (park factors)

Output: data/mlb_total_bases_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_total_bases_props.json")

# League-average TB rates (per PA)
LEAGUE_TB_PER_PA = 0.355  # ~0.247 BA, with ~.40 SLG -> 0.355 TB/PA
LEAGUE_PA_PER_GAME = 4.1


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    """P(X >= k) for Poisson(lam)."""
    if lam <= 0: return 0.0 if k > 0 else 1.0
    p_less = sum(_poisson_pmf(i, lam) for i in range(k))
    return max(0.0, min(1.0, 1.0 - p_less))


def _american_from_p(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _expected_pa(order: int) -> float:
    """Expected PA per game based on lineup order."""
    # 1-3: 4.4 PA, 4-6: 4.1, 7-9: 3.7
    if order <= 3: return 4.4
    if order <= 6: return 4.1
    return 3.7


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    # 2026-05-21: real recent-form per-batter stats (last 14 games)
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    batter_log_idx = {}
    for b in (batter_logs.get("batters") or []):
        nm = (b.get("name") or "").lower()
        if nm: batter_log_idx[nm] = b

    parks = today.get("parks") or {}
    lvr_idx = {}
    for row in (lvr.get("all_batters") or []):
        nm = (row.get("batter") or "").lower()
        if nm: lvr_idx[nm] = row

    games = matchups.get("games") or today.get("games") or []
    tb_rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_hr_factor = _safe((park_info or {}).get("hr_factor"), 1.0) or 1.0
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0

        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # 2026-05-21: prefer REAL recent-form TB/AB from mlb_batter_logs
                # over OPS-derived SLG proxy. Falls back to OPS proxy if batter
                # not in logs or has <10 AB recent sample.
                batter_log = batter_log_idx.get((name or "").lower())
                tb_source = "ops_proxy"
                if batter_log:
                    s14 = batter_log.get("stats_last_14") or {}
                    real_ab = int(s14.get("ab") or 0)
                    real_tb = int(s14.get("tb") or 0)
                    if real_ab >= 10:
                        # tb_per_ab (real recent) -> tb_per_pa via PA = AB * ~1.10
                        real_tb_per_pa = real_tb / real_ab * 0.91  # 0.91 = AB/PA
                        tb_per_pa = max(0.10, min(0.75, real_tb_per_pa))
                        tb_source = "real_last_14"

                if tb_source == "ops_proxy":
                    # FALLBACK: SLG proxy from OPS
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    split_ops = _safe(lvr_row.get("split_ops"), season_ops)
                    split_pa = int(_safe(lvr_row.get("split_pa"), 0))
                    blended_ops = (split_pa * split_ops + 80 * season_ops) / (split_pa + 80) if split_pa > 0 else season_ops
                    slg_proxy = max(0.28, min(0.60, blended_ops * 0.55))
                    tb_per_pa = slg_proxy * 0.92

                # Park HR factor boosts TB ceiling, run factor adjusts contact
                tb_per_pa *= (1 + (park_hr_factor - 1) * 0.4)  # 40% of HR boost flows to TB
                tb_per_pa *= park_run_factor ** 0.4  # partial exposure to general run env
                tb_per_pa = max(0.20, min(0.65, tb_per_pa))

                pa = _expected_pa(order)
                expected_tb = tb_per_pa * pa

                p_1plus = _poisson_at_least(1, expected_tb)
                p_2plus = _poisson_at_least(2, expected_tb)
                p_3plus = _poisson_at_least(3, expected_tb)

                # Edge classification: against a typical book line of -150 for TB 1.5+
                # If model P(2+) > 0.50, that beats -100; > 0.55 beats -125; > 0.60 beats -150
                edge_class = "NONE"
                if p_2plus >= 0.62:
                    edge_class = "STRONG_2PLUS"
                elif p_2plus >= 0.55:
                    edge_class = "STANDARD_2PLUS"
                elif p_3plus >= 0.30:
                    edge_class = "STANDARD_3PLUS"

                if expected_tb < 0.5: continue

                tb_rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "opp_pitcher": opp_pitcher,
                    "park": park,
                    "expected_pa": pa,
                    "tb_source": tb_source,
                    "tb_per_pa": round(tb_per_pa, 3),
                    "expected_tb": round(expected_tb, 2),
                    "p_1_plus": round(p_1plus, 3),
                    "p_2_plus": round(p_2plus, 3),
                    "p_3_plus": round(p_3plus, 3),
                    "fair_odds_1_plus": _american_from_p(p_1plus),
                    "fair_odds_2_plus": _american_from_p(p_2plus),
                    "fair_odds_3_plus": _american_from_p(p_3plus),
                    "edge_class": edge_class,
                })

    tb_rows.sort(key=lambda r: -r["expected_tb"])
    strong = [r for r in tb_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_total": len(tb_rows),
        "n_strong_edges": len(strong),
        "league_tb_per_pa": LEAGUE_TB_PER_PA,
        "top_25_by_xTB": tb_rows[:25],
        "strong_2plus_edges": strong[:15],
        "note": "Total Bases prop projections via Poisson on per-PA TB rate.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[total-bases] {o['n_total']} batters, {o['n_strong_edges']} strong 2+ TB edges -> {OUT}")
