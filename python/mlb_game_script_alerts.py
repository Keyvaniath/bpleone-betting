"""
EdgeStat -- MLB game-script confluence alerts.

Surfaces games where multi-signal game-flow indicators align:
  - 1ST_INNING_RUN_YES (>=42%)
  - 1ST_3_INN_RUNS_OVER (>=55%)
  - 5PLUS_RUNS_GAME_YES (high prob of 5+ team runs)
  - GAME_TOTAL_OVER (game total OVER lean)
  - FIRST_5_INN_OVER (1st 5 innings OVER)
  - RUN_LINE_FAVORED (run line covering >= 45%)
  - EXTRA_INN_UNDER (extra innings UNDER lean = decisive game)

A high-scoring game script alert is when 4+ signals align, suggesting a
high-action game ripe for parlay legs across multiple inning markets.

SCRIPT_ELITE = 5+ signals; STRONG = 3-4.

Output: data/mlb_game_script_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_game_script_alerts.json")


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


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    first_inn_run = _load(os.path.join(DATA_DIR, "mlb_team_first_inning_run.json"))
    first_3_inn = _load(os.path.join(DATA_DIR, "mlb_team_first_3_innings_runs.json"))
    five_plus = _load(os.path.join(DATA_DIR, "mlb_team_5plus_runs.json"))
    game_total = _load(os.path.join(DATA_DIR, "mlb_game_total_alt_props.json"))
    first_5 = _load(os.path.join(DATA_DIR, "mlb_first5_market.json"))
    run_line = _load(os.path.join(DATA_DIR, "mlb_run_line_props.json"))
    extra_inn = _load(os.path.join(DATA_DIR, "mlb_extra_innings_prop.json"))

    # Index by matchup
    def _build_signal(src: Dict[str, Any], p_field: str, threshold: float,
                      list_keys: List[str] = None) -> Dict[str, float]:
        idx: Dict[str, float] = {}
        list_keys = list_keys or ["rows", "strong_edges", "top_15_by_p", "top_25_by_p"]
        for k in list_keys:
            for r in (src.get(k) or []):
                if not isinstance(r, dict): continue
                matchup = _norm(r.get("matchup", ""))
                if not matchup: continue
                p_val = _safe(r.get(p_field) or r.get("p"))
                if matchup not in idx or p_val > idx[matchup]:
                    idx[matchup] = p_val
        return idx

    def _build_over_signal(src: Dict[str, Any], match_field: str = "matchup") -> Dict[str, bool]:
        idx: Dict[str, bool] = {}
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            matchup = _norm(r.get(match_field, ""))
            ec = (r.get("edge_class") or "").upper()
            if "OVER" in ec:
                idx[matchup] = True
        return idx

    p_first_inn = _build_signal(first_inn_run, "p_yes", 0.42)
    p_first_3 = _build_signal(first_3_inn, "p_over", 0.55)
    p_5plus = _build_signal(five_plus, "p_5plus", 0.35)
    gt_over = _build_over_signal(game_total)
    first5_over = _build_over_signal(first_5)
    rl_fav = _build_signal(run_line, "p_cover", 0.45)
    ei_under = _build_over_signal(extra_inn)  # OVER on extra-inn UNDER = decisive

    # All matchups touched
    all_matchups = (set(p_first_inn) | set(p_first_3) | set(p_5plus)
                    | set(gt_over) | set(first5_over) | set(rl_fav)
                    | set(ei_under))

    alerts: List[Dict[str, Any]] = []
    for m in all_matchups:
        signals: Dict[str, int] = {}
        signals["1ST_INN_RUN_YES"] = 1 if p_first_inn.get(m, 0) >= 0.42 else 0
        signals["1ST_3_INN_OVER"] = 1 if p_first_3.get(m, 0) >= 0.55 else 0
        signals["5PLUS_RUNS_GAME"] = 1 if p_5plus.get(m, 0) >= 0.35 else 0
        signals["GAME_TOTAL_OVER"] = 1 if gt_over.get(m) else 0
        signals["FIRST_5_INN_OVER"] = 1 if first5_over.get(m) else 0
        signals["RUN_LINE_FAVORED"] = 1 if rl_fav.get(m, 0) >= 0.45 else 0
        signals["EXTRA_INN_UNDER"] = 1 if ei_under.get(m) else 0

        n = sum(1 for v in signals.values() if v == 1)
        if n < 3: continue

        tier = "SCRIPT_ELITE" if n >= 5 else "SCRIPT_STRONG"

        alerts.append({
            "matchup": m,
            "n_signals": n,
            "signals": signals,
            "p_1st_inn_run": round(p_first_inn.get(m, 0), 3),
            "p_5plus_runs": round(p_5plus.get(m, 0), 3),
            "p_run_line_cover": round(rl_fav.get(m, 0), 3),
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_signals"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "SCRIPT_ELITE"),
        "method_note": "MLB game-script confluence. 3+ aligned signals: "
                       "1ST_INN_RUN_YES (>=42%), 1ST_3_INN_OVER (>=55%), "
                       "5PLUS_RUNS_GAME (>=35%), GAME_TOTAL_OVER, FIRST_5_INN_OVER, "
                       "RUN_LINE_FAVORED (>=45%), EXTRA_INN_UNDER. "
                       "SCRIPT_ELITE = 5+ signals.",
        "alerts": alerts,
        "elite_scripts": [a for a in alerts if a["tier"] == "SCRIPT_ELITE"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-game-script] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
