"""
EdgeStat -- MLB extra-base hit (doubles+triples+HR) prop projections.

Common DK/FD prop:
  - 1+ extra base hit (XBH) yes/no, typically -120 to +110

Approach:
  Per-PA XBH rate from batter ISO (Isolated Power = SLG - AVG).
  ISO directly measures power production beyond singles.
  Expected XBH = ISO * 1.05 * E[AB] (close approximation of XBH/AB)
  P(1+ XBH) = 1 - exp(-expected_xbh)

Adjustments:
  - Park HR factor proxies XBH lift (hitter parks add ~10%% XBH)
  - Opposing SP K-rate (high-K pitcher reduces XBH chances)
  - Lineup spot (top 4 hitters get more PAs and better counts)

Output: data/mlb_doubles_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

import mlb_batter_splits as _SPL   # batter home/away + platoon (vsL/vsR) multiplier


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_doubles_props.json")

LEAGUE_ISO = 0.165  # 2024 league avg ISO
LEAGUE_K_RATE = 0.224


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


def _expected_ab(order: int) -> float:
    """Expected at-bats per game for this lineup spot (PAs - walks)."""
    if order <= 3: return 4.0
    if order <= 6: return 3.7
    return 3.4


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    # 2026-05-21: real recent-form stats from MLB Stats API
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
    p_idx = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    spl = _SPL.load(DATA_DIR)   # home/away + platoon split multipliers (neutral if absent)

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_hr_factor = _safe((park_info or {}).get("hr_factor"), 1.0) or 1.0

        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher_name = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")
            opp_pitcher = p_idx.get((opp_pitcher_name or "").lower(), {})
            opp_k_per_9 = _safe(opp_pitcher.get("k_per_9") or opp_pitcher.get("season", {}).get("k_per_9"), 8.5)
            # Convert K/9 to K% per PA (roughly K/9 / (9*4.1) PA/inning)
            opp_k_rate = opp_k_per_9 / (9 * 4.1)

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # 2026-05-21: prefer REAL recent-form XBH/AB from mlb_batter_logs.
                # XBH ≈ tb - h - 2*hr (since tb = h + 1*2B + 2*3B + 3*HR
                # ≈ h + (2B + 3B + HR) + 2*HR -- approx if 3B is rare).
                blog = batter_log_idx.get((name or "").lower())
                xbh_source = "ops_proxy"
                blended_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                if blog:
                    s14 = blog.get("stats_last_14") or {}
                    real_ab = int(s14.get("ab") or 0)
                    real_h = int(s14.get("h") or 0)
                    real_tb = int(s14.get("tb") or 0)
                    real_hr = int(s14.get("hr") or 0)
                    if real_ab >= 10:
                        # XBH = TB - H - 2*HR (triples treated as doubles for this approx)
                        real_xbh = max(0, real_tb - real_h - 2 * real_hr)
                        xbh_per_ab = real_xbh / real_ab if real_ab else 0
                        xbh_per_ab = max(0.01, min(0.30, xbh_per_ab))
                        xbh_source = "real_last_14"

                if xbh_source == "ops_proxy":
                    # FALLBACK: ISO-derived estimate
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    split_ops = _safe(lvr_row.get("split_ops"), season_ops)
                    split_pa = int(_safe(lvr_row.get("split_pa"), 0))
                    blended_ops = ((split_pa * split_ops + 80 * season_ops) / (split_pa + 80)
                                   if split_pa > 0 else season_ops)
                    blended_iso = max(0.08, min(0.32, blended_ops * 0.30))
                    xbh_per_ab = blended_iso / 3.0
                park_mult = 1.0 + (park_hr_factor - 1.0) * 0.6
                k_mult = max(0.75, min(1.10, 1.0 - (opp_k_rate - LEAGUE_K_RATE) * 0.8))
                # Batter-specific home/away + platoon (vsL/vsR) power skew (1.0 if absent).
                power_mult = spl.power_mult(name, side == "home")
                expected_xbh_per_ab = xbh_per_ab * park_mult * k_mult * power_mult
                expected_xbh = expected_xbh_per_ab * _expected_ab(order)

                p_1plus = 1 - math.exp(-expected_xbh)

                edge_class = "NONE"
                best_market = None
                # Book lines for 1+ XBH typically +100 to +160 (50-38%% breakeven)
                # STRONG: model says player has higher than book breakeven prob.
                # Real-world top sluggers hit 25-35%% P(XBH+) per game.
                if 0.32 <= p_1plus <= 0.45:
                    edge_class = "STRONG_1_PLUS_XBH"
                    best_market = {"market": "1_PLUS_XBH", "p": round(p_1plus, 3),
                                   "fair_odds": _american(p_1plus)}
                elif p_1plus < 0.18 and order <= 5:
                    # Cold matchup for top-order hitter -- UNDER play
                    edge_class = "STRONG_NO_XBH"
                    best_market = {"market": "NO_XBH", "p": round(1 - p_1plus, 3),
                                   "fair_odds": _american(1 - p_1plus)}

                if expected_xbh < 0.15: continue  # skip super low

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "opp_pitcher": opp_pitcher_name,
                    "park": park,
                    "park_hr_factor": park_hr_factor,
                    "xbh_source": xbh_source,
                    "split_power_mult": power_mult,
                    "blended_ops": round(blended_ops, 3),
                    "xbh_per_ab": round(xbh_per_ab, 3),
                    "opp_k_rate": round(opp_k_rate, 3),
                    "expected_xbh": round(expected_xbh, 3),
                    "p_1_plus": round(p_1plus, 3),
                    "fair_odds_1_plus": _american(p_1plus),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["expected_xbh"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "league_iso": LEAGUE_ISO,
        "method_note": "XBH/AB = ISO × park × opp_K. Poisson approx. STRONG 1+: p 58-72%%. "
                       "STRONG_NO_XBH: top-order hitters facing elite K-pitcher in pitcher park.",
        "top_25_by_xXBH": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[doubles] {o['n_batters']} batters, {o['n_strong_edges']} strong edges -> {OUT}")
