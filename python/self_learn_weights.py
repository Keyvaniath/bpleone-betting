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
    # New (May 2026)
    "mlb_f5": 0.70,                  # F5 sharp market, high signal
    "mlb_total_bases_2plus": 0.60,
    "mlb_hrr_2_plus_hrr": 0.60, "mlb_hrr_3_plus_hrr": 0.55,
    "mlb_steal_1plus": 0.55,
    "rlm_strong": 0.65,              # reverse line movement = sharp money
    "mlb_pitcher_deep_matchup": 0.65,
    "mlb_catcher_framing": 0.55,
    "mlb_batter_advanced_splits": 0.60,
    "golf_live_tracker": 0.55,
    "nhl_goalie_pull_leverage": 0.65,
    "f1_track_specific": 0.55,
    "nba_pace_adjusted": 0.55,
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

    # User overrides (from /model-control dashboard)
    try:
        import model_overrides as _mo
        _mo.reload()
    except Exception:
        _mo = None

    # Learning integrity guards (don't learn from noise)
    guards = _load(os.path.join(DATA_DIR, "learning_guards.json"))

    # Previous learned weights (for velocity-capping)
    prev_learned = _load(os.path.join(DATA_DIR, "learned_weights.json")).get("weights", {})

    learned: Dict[str, Dict[str, Any]] = {}
    for source, prior in PRIOR_WEIGHTS.items():
        stats = by_source.get(source) or {}
        n = (stats.get("wins") or 0) + (stats.get("losses") or 0)
        hit_rate = stats.get("hit_rate")
        guard = guards.get(source, {})
        max_delta = guard.get("max_weight_delta", MAX_WEIGHT_DELTA_PER_CYCLE if 'MAX_WEIGHT_DELTA_PER_CYCLE' in globals() else 1.0)
        use_wilson_lo = guard.get("use_wilson_lo", True)  # safer default

        # Observed: use Wilson lower bound for unproven sources, point estimate for proven
        if hit_rate is not None and n > 0:
            hits = int(round(hit_rate * n))
            if use_wilson_lo:
                # Wilson 95% lower bound -- conservative, won't fit noise
                import math as _m
                z = 1.96
                p = hits / n
                denom = 1 + z**2/n
                center = (p + z**2/(2*n)) / denom
                spread = z * _m.sqrt(p*(1-p)/n + z**2/(4*n*n)) / denom
                effective_rate = max(0.0, center - spread)
            else:
                effective_rate = hit_rate
            w_observed = _clamp((effective_rate - 0.50) * 2 + 0.55, 0.30, 0.90)
        else:
            w_observed = prior

        # Shrink toward prior by sample size
        pull = n / (n + SHRINKAGE_PRIOR_N)
        w_target = pull * w_observed + (1 - pull) * prior

        # Velocity-cap: w_learned can only move max_delta per cycle from prev value
        prev_w = prev_learned.get(source, {}).get("w_learned", prior)
        if max_delta > 0:
            delta = w_target - prev_w
            if abs(delta) > max_delta:
                w_learned = prev_w + max_delta * (1 if delta > 0 else -1)
            else:
                w_learned = w_target
        else:
            # No learning allowed -- stay at prior
            w_learned = prior

        # User override -- blends 50/50 with learned (so user retains control without nuking learning)
        user_override = _mo.source_weight(source) if _mo else None
        if user_override is not None:
            blend_alpha = 0.7  # 70% user, 30% learned (so they keep adapting)
            w_final = blend_alpha * float(user_override) + (1 - blend_alpha) * w_learned
            w_final = _clamp(w_final, 0.10, 0.95)
        else:
            w_final = w_learned

        learned[source] = {
            "prior": prior,
            "n_settled": n,
            "hit_rate": hit_rate,
            "w_observed": round(w_observed, 3),
            "pull_toward_observed": round(pull, 3),
            "w_target_uncapped": round(w_target, 3),
            "w_learned": round(w_learned, 3),
            "w_final": round(w_final, 3),
            "user_override": user_override,
            "delta_from_prior": round(w_final - prior, 3),
            "guard_grade": guard.get("grade"),
            "guard_used_wilson_lo": use_wilson_lo,
            "guard_max_delta": max_delta,
            "guard_reason": guard.get("reason"),
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
