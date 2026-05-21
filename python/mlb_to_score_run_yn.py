"""
EdgeStat -- MLB to-score-a-run yes/no per batter.

Common DK line: "Player to score a run yes/no" (~-150 to +180 each side).
Different from "1+ run" / "1+ RBI" -- this is whether the player crosses home.

Method:
  P(scores >= 1 run) = 1 - exp(-expected_runs_for_batter)
  expected_runs_for_batter = E[PA] × runs_per_PA

  runs_per_PA depends on:
    - Batter OBP (need to reach base)
    - Lineup spots BEFORE them (top of order = more PAs but less RBI context;
      middle = fewer PAs but better runners-on)
    - Team run-scoring rate
    - Park factor

Output: data/mlb_to_score_run_yn.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_to_score_run_yn.json")

LEAGUE_RUNS_PER_PA = 0.128  # ~4.5 R/g / 35 PA per team


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


def _runs_per_pa_by_order(order: int) -> float:
    """Runs scored per PA varies by lineup spot.
    Top of order: more runs (better runners behind, more PAs)
    Middle: fewer runs (often drive in, not score)
    Bottom: lowest runs (poor hitters, no one drives them in)
    """
    if order == 1: return 0.135
    if order == 2: return 0.140
    if order == 3: return 0.135
    if order == 4: return 0.115  # RBI guys
    if order == 5: return 0.110
    if order == 6: return 0.115
    if order == 7: return 0.105
    if order == 8: return 0.095
    return 0.100  # 9th


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    # 2026-05-21: real recent-form 1+ run probs from MLB Stats API
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
    rows: List[Dict[str, Any]] = []

    for g in games:
        park = g.get("park") or g.get("venue")
        park_info = parks.get(park) if isinstance(parks, dict) else None
        park_run_factor = _safe((park_info or {}).get("run_factor"), 1.0) or 1.0
        lineups = g.get("lineups") or {}
        matchup_str = g.get("matchup") or ""

        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            team_runs = _safe((g.get(side) or {}).get("runs"), 4.5)
            team_run_mult = max(0.80, min(1.20, team_runs / 4.5))

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                order = batter.get("order") or 9
                lvr_row = lvr_idx.get((name or "").lower(), {})

                # 2026-05-21: prefer REAL recent 1+ run probability from batter logs.
                # Falls back to OPS-derived OBP proxy when batter not in logs.
                run_source = "ops_proxy"
                blog = batter_log_idx.get((name or "").lower())
                if blog:
                    props = blog.get("props") or {}
                    real_p_run = (props.get("1_plus_run") or {}).get("p")
                    n_games = blog.get("n_games_logged") or 0
                    if real_p_run is not None and n_games >= 8:
                        p_scores = float(real_p_run)
                        # Apply park run factor lightly (real data already includes home/away mix)
                        p_scores *= park_run_factor ** 0.20
                        p_scores = max(0.05, min(0.95, p_scores))
                        p_no_run = 1 - p_scores
                        run_source = "real_last_14"
                        expected_runs = -math.log(max(1 - p_scores, 1e-6))
                        obp_proxy = None
                        runs_per_pa = expected_runs / _expected_pa(order)

                if run_source == "ops_proxy":
                    # FALLBACK: OPS-derived OBP estimate
                    season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
                    obp_proxy = max(0.27, min(0.42, season_ops - 0.40))
                    obp_mult = obp_proxy / 0.317

                    runs_per_pa = _runs_per_pa_by_order(order)
                    runs_per_pa *= obp_mult * team_run_mult * (park_run_factor ** 0.5)

                    pa = _expected_pa(order)
                    expected_runs = runs_per_pa * pa
                    p_scores = 1 - math.exp(-expected_runs)
                    p_no_run = 1 - p_scores

                edge_class = "NONE"
                best_market = None
                # Book lines typically -150 (60%% breakeven) YES for top hitters,
                # +150 NO. STRONG_YES when model >= 70%%; STRONG_NO when <= 35%%.
                if 0.70 <= p_scores <= 0.82:
                    edge_class = "STRONG_YES"
                    best_market = {"market": "TO_SCORE_RUN_YES", "p": round(p_scores, 3),
                                   "fair_odds": _american(p_scores)}
                elif 0.62 <= p_no_run <= 0.72:
                    edge_class = "STRONG_NO"
                    best_market = {"market": "TO_SCORE_RUN_NO", "p": round(p_no_run, 3),
                                   "fair_odds": _american(p_no_run)}

                rows.append({
                    "matchup": matchup_str,
                    "batter": name,
                    "team": (lvr_row.get("team_abbr") or batter.get("team") or "").upper(),
                    "order": order,
                    "run_source": run_source,
                    "obp_proxy": round(obp_proxy, 3) if obp_proxy is not None else None,
                    "team_runs_per_game": team_runs,
                    "park_run_factor": park_run_factor,
                    "expected_runs": round(expected_runs, 3),
                    "p_scores": round(p_scores, 3),
                    "p_no_run": round(p_no_run, 3),
                    "fair_yes": _american(p_scores),
                    "fair_no": _american(p_no_run),
                    "edge_class": edge_class,
                    "best_market": best_market,
                })

    rows.sort(key=lambda r: -r["p_scores"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(scores) = 1 - exp(-runs_per_PA × E[PA]). Per-order runs_per_PA "
                       "× OBP_mult × team_runs × park^0.5. STRONG_YES 70-82%% (vs -150 book), "
                       "STRONG_NO 62-72%% (vs +150 book).",
        "top_25_by_p_scores": rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[score-run] {o['n_batters']} batters, {o['n_strong_edges']} strong -> {OUT}")
