"""
EdgeStat -- SELF-LEARNING shrinkage weight tuner.

Reads data/all_picks_ledger.json per-source W-L stats and recomputes
SOURCE_SHRINKAGE_W values that todays_top_plays.py uses. Sources that
hit >55% get higher trust (less shrinkage); sources < 45% get heavier
shrinkage toward baseline.

The feedback loop:
   1. Today's picks surface from various sources
   2. Tomorrow they settle
   3. all_picks_ledger.by_source updates
   4. This module recomputes per-source weights
   5. Tomorrow's todays_top_plays uses the new weights
   6. Better-performing sources get more influence on the top board

Output: data/learned_weights.json (consumed by todays_top_plays.py)

Logic (Bayesian-ish, shrunk for small samples):
   For each source:
     n = wins + losses
     w_prior = SOURCE_SHRINKAGE_W default (0.55-0.80 hand-tuned)
     w_observed = clamp((hit_rate - 0.50) * 2 + 0.55, 0.30, 0.90)
        e.g. 60% hit -> 0.75 weight, 50% -> 0.55, 40% -> 0.35
     # Shrinkage by sample size
     pull = n / (n + 30)
     w_learned = pull * w_observed + (1 - pull) * w_prior
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "learned_weights.json")

# Prior weights (what we hand-coded in todays_top_plays.py SOURCE_SHRINKAGE_W)
PRIOR_WEIGHTS = {
    "today": 0.80, "today_reco": 0.80,
    "mlb_ext_batter": 0.60, "mlb_ext_pitcher": 0.65,
    "mlb_batter_logs": 0.55, "mlb_batter_lvr": 0.60,
    "mlb_batter_sp_edges": 0.60, "mlb_batter_situational": 0.55,
    "pitcher_matchup": 0.65, "pitcher_form_regression": 0.65,
    "pp_over": 0.45, "pp_under": 0.45,
    "nba_ext": 0.55, "wnba_ext": 0.55, "nhl_ext": 0.55,
    "nhl_goalie": 0.65, "nhl_skater": 0.55,
    "mlb_team_total": 0.60, "mlb_run_line": 0.60,
    "f1_driver": 0.50,
    "lock_of_day": 0.65, "pod": 0.70,
    "whale_whale": 0.75, "whale_strong": 0.65,
    "consensus_hit_strong": 0.70, "consensus_hit_elite": 0.80,
    "consensus_hr_strong": 0.70, "consensus_hr_elite": 0.80,
    "mlb_under_alert": 0.65,
    "sharp_strong": 0.70, "sharp_elite": 0.80,
    "top_25_board": 0.55,
}
SHRINKAGE_PRIOR_N = 30   # need 30 settled to fully trust observed hit rate


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _clamp(x, lo, hi): return max(lo, min(hi, x))


def run() -> Dict[str, Any]:
    ledger = _load(os.path.join(DATA_DIR, "all_picks_ledger.json"))
    by_source = ledger.get("by_source") or {}

    learned: Dict[str, Dict[str, Any]] = {}
    for source, prior in PRIOR_WEIGHTS.items():
        stats = by_source.get(source) or {}
        n = (stats.get("wins") or 0) + (stats.get("losses") or 0)
        hit_rate = stats.get("hit_rate")

        # Observed weight: hit_rate -> shrinkage weight
        # 60% hit -> 0.75; 55% -> 0.65; 50% -> 0.55; 45% -> 0.45; 40% -> 0.35
        if hit_rate is not None:
            w_observed = _clamp((hit_rate - 0.50) * 2 + 0.55, 0.30, 0.90)
        else:
            w_observed = prior

        # Shrink toward prior by sample size
        pull = n / (n + SHRINKAGE_PRIOR_N)
        w_learned = pull * w_observed + (1 - pull) * prior

        learned[source] = {
            "prior": prior,
            "n_settled": n,
            "hit_rate": hit_rate,
            "w_observed": round(w_observed, 3),
            "pull_toward_observed": round(pull, 3),
            "w_learned": round(w_learned, 3),
            "delta_from_prior": round(w_learned - prior, 3),
        }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "shrinkage_prior_n": SHRINKAGE_PRIOR_N,
        "n_sources_with_data": sum(1 for s in learned.values() if s["n_settled"] > 0),
        "weights": learned,
        "note": ("Per-source shrinkage weights learned from all_picks_ledger "
                  "settled outcomes. Sources hit > 55% earn higher weight; "
                  "< 45% get pushed toward baseline. Shrunk by sample size "
                  "(needs 30+ settled to fully trust observed rate). "
                  "todays_top_plays.py reads this to dynamically adjust "
                  "calibration."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Self-learn weights: {p['n_sources_with_data']} sources with settled data")
    sources_with_data = [(s, w) for s, w in p["weights"].items() if w["n_settled"] > 0]
    sources_with_data.sort(key=lambda x: -x[1]["n_settled"])
    for source, w in sources_with_data[:10]:
        delta = w["delta_from_prior"]
        sign = "+" if delta >= 0 else ""
        print(f"  {source:28s}  n={w['n_settled']:3d}  hit {(w['hit_rate'] or 0)*100:5.1f}%  prior {w['prior']:.2f} -> learned {w['w_learned']:.2f}  ({sign}{delta:.3f})")
