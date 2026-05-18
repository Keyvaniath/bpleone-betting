"""
EdgeStat -- self-training backtest loop for ESPN sport models.

Reads historical_<sport>.json (real completed games) and back-runs each
sport's ELO model on those games. For each completed game we compare the
model's pre-game P(home win) to the actual outcome and accumulate:

  - Brier score (calibration)
  - Log loss (sharpness)
  - Hit rate (rounded model predictions)
  - Margin error (predicted vs actual point diff)
  - Per-sport bias estimate (avg model prob minus avg actual hit rate)

The bias estimate is then surfaced as a recommended calibration shift,
which the per-sport pipeline can apply to future P(home win) predictions.

Output: data/self_training_<sport>.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SPORT_CONFIGS = {
    "nba":  {"hfa_elo": 35},
    "nhl":  {"hfa_elo": 20},
    "wnba": {"hfa_elo": 30},
    "mls":  {"hfa_elo": 60},
    "epl":  {"hfa_elo": 65},
    "mlb":  {"hfa_elo": 25},
    "cws":  {"hfa_elo": 25},
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _winpct_to_elo(wp: float, base: float = 1500) -> float:
    if wp <= 0.01: return base - 250
    if wp >= 0.99: return base + 250
    return base + 400 * math.log10(wp / (1 - wp))


def _elo_winprob(home_elo: float, away_elo: float, hfa: float = 35) -> float:
    diff = (home_elo + hfa) - away_elo
    return 1 / (1 + 10 ** (-diff / 400))


def backtest_sport(sport_key: str) -> Dict[str, Any]:
    """Walk historical games chronologically, building running W-L records
    per team and back-computing what the ELO model would have predicted."""
    h = _load(os.path.join(DATA_DIR, f"historical_{sport_key}.json"))
    games = h.get("games") or []
    if not games:
        return {"sport": sport_key, "n_games": 0, "note": "no historical games"}

    # Sort chronologically (oldest first) for proper walk-forward
    games_sorted = sorted(games, key=lambda g: g["date"])
    cfg = SPORT_CONFIGS.get(sport_key, {"hfa_elo": 30})
    hfa = cfg["hfa_elo"]

    # Build running records as we walk
    team_records: Dict[str, Dict[str, int]] = {}    # team -> {w, l, t}
    predictions: List[Dict[str, Any]] = []

    for g in games_sorted:
        ht, at = g["home_team"], g["away_team"]
        if not (ht and at): continue
        # Pre-game records (BEFORE counting this game)
        h_rec = team_records.get(ht, {"w": 0, "l": 0, "t": 0})
        a_rec = team_records.get(at, {"w": 0, "l": 0, "t": 0})
        h_tot = h_rec["w"] + h_rec["l"] + h_rec["t"]
        a_tot = a_rec["w"] + a_rec["l"] + a_rec["t"]
        h_wp = (h_rec["w"] + 0.5 * h_rec["t"]) / max(1, h_tot) if h_tot else 0.5
        a_wp = (a_rec["w"] + 0.5 * a_rec["t"]) / max(1, a_tot) if a_tot else 0.5
        h_elo = _winpct_to_elo(h_wp)
        a_elo = _winpct_to_elo(a_wp)
        p_home = _elo_winprob(h_elo, a_elo, hfa=hfa)

        actual = 1 if g["home_score"] > g["away_score"] else 0 if g["away_score"] > g["home_score"] else 0.5
        margin_err = (h_elo - a_elo) / 50 - g["margin"]   # rough proxy
        predictions.append({
            "date": g["date"], "matchup": f"{at} @ {ht}",
            "p_home_pregame": round(p_home, 4),
            "actual_home_win": actual,
            "margin_err": margin_err,
            "h_record_pre": f"{h_rec['w']}-{h_rec['l']}",
            "a_record_pre": f"{a_rec['w']}-{a_rec['l']}",
        })

        # Update running records (AFTER predicting)
        if g["home_score"] > g["away_score"]:
            team_records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["w"] += 1
            team_records.setdefault(at, {"w": 0, "l": 0, "t": 0})["l"] += 1
        elif g["away_score"] > g["home_score"]:
            team_records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["l"] += 1
            team_records.setdefault(at, {"w": 0, "l": 0, "t": 0})["w"] += 1
        else:
            team_records.setdefault(ht, {"w": 0, "l": 0, "t": 0})["t"] += 1
            team_records.setdefault(at, {"w": 0, "l": 0, "t": 0})["t"] += 1

    # Aggregate metrics
    n = len(predictions)
    if n == 0:
        return {"sport": sport_key, "n_games": 0, "note": "no usable predictions"}

    brier = sum((p["p_home_pregame"] - p["actual_home_win"]) ** 2 for p in predictions) / n
    ll = 0
    for p in predictions:
        pp = max(1e-6, min(1 - 1e-6, p["p_home_pregame"]))
        actual = p["actual_home_win"]
        ll += -(actual * math.log(pp) + (1 - actual) * math.log(1 - pp))
    log_loss = ll / n

    # Predicted-side hit rate (round to 0/1)
    hits = sum(1 for p in predictions if round(p["p_home_pregame"]) == p["actual_home_win"])
    hit_rate = hits / n

    # Bias: avg(p_home) vs actual_home_win_rate
    avg_pred = sum(p["p_home_pregame"] for p in predictions) / n
    avg_actual = sum(p["actual_home_win"] for p in predictions) / n
    bias = avg_pred - avg_actual    # positive = model OVER-confident in home

    # Per-bin reliability (10 bins)
    bins = []
    for i in range(10):
        lo = i / 10
        hi = (i + 1) / 10
        in_bin = [p for p in predictions if lo <= p["p_home_pregame"] < hi or (i == 9 and p["p_home_pregame"] >= 0.9)]
        if not in_bin: continue
        bins.append({
            "lo": lo, "hi": hi, "n": len(in_bin),
            "predicted_avg": round(sum(p["p_home_pregame"] for p in in_bin) / len(in_bin), 3),
            "actual_avg": round(sum(p["actual_home_win"] for p in in_bin) / len(in_bin), 3),
        })

    # Recommendation: tiered min-sample with shrinkage on small N
    # Below 15: zero confidence -- don't apply
    # 15-29: apply with shrinkage (half the recommended shift)
    # 30+: apply full shift (still cap at 10pp to avoid runaway corrections)
    MIN_SAMPLE = 15
    FULL_SAMPLE = 30
    BIAS_THRESHOLD_PP = 0.02   # 2pp = "well calibrated"
    MAX_SHIFT_PP = 0.10        # never shift > 10pp
    if abs(bias) < BIAS_THRESHOLD_PP:
        reco = {"applied": False, "note": "model is well-calibrated (<2pp bias)"}
    elif n < MIN_SAMPLE:
        reco = {"applied": False, "note": f"not enough sample size ({n} games); need >= {MIN_SAMPLE}"}
    else:
        # Linear shrinkage for partial samples
        if n >= FULL_SAMPLE:
            shrinkage = 1.0
        else:
            shrinkage = (n - MIN_SAMPLE) / (FULL_SAMPLE - MIN_SAMPLE)  # 0.0 at 15, 1.0 at 30
            shrinkage = max(0.3, min(1.0, shrinkage))  # floor at 30% so tiny samples still bend
        raw_shift = -bias * shrinkage
        # Cap at MAX_SHIFT_PP
        clamped_shift = max(-MAX_SHIFT_PP, min(MAX_SHIFT_PP, raw_shift))
        reco = {
            "applied": True,
            "bias_pp": round(bias * 100, 1),
            "shrinkage": round(shrinkage, 3),
            "recommended_shift": round(clamped_shift, 4),
            "note": (f"Model over-predicting home by {bias*100:.1f}pp; subtract "
                      f"{abs(clamped_shift)*100:.1f}pp from P(home) (shrinkage {shrinkage:.0%})"
                      if bias > 0 else
                      f"Model under-predicting home by {abs(bias)*100:.1f}pp; add "
                      f"{abs(clamped_shift)*100:.1f}pp to P(home) (shrinkage {shrinkage:.0%})"),
        }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sport": sport_key,
        "n_games": n,
        "hit_rate": round(hit_rate, 4),
        "brier_score": round(brier, 4),
        "log_loss": round(log_loss, 4),
        "avg_predicted_home_winprob": round(avg_pred, 4),
        "avg_actual_home_winrate": round(avg_actual, 4),
        "bias": round(bias, 4),
        "reliability_bins": bins,
        "recommendation": reco,
        "n_teams_tracked": len(team_records),
    }
    out_path = os.path.join(DATA_DIR, f"self_training_{sport_key}.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


def run() -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "by_sport": {},
    }
    for sport in SPORT_CONFIGS:
        try:
            p = backtest_sport(sport)
            summary["by_sport"][sport] = {
                "n_games": p.get("n_games", 0),
                "hit_rate": p.get("hit_rate"),
                "brier": p.get("brier_score"),
                "bias": p.get("bias"),
                "recommendation_applied": p.get("recommendation", {}).get("applied"),
            }
        except Exception as e:
            summary["by_sport"][sport] = {"error": str(e)}
    out_path = os.path.join(DATA_DIR, "self_training_summary.json")
    with open(out_path, "w") as f: json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    s = run()
    print("Self-training backtest per sport:")
    for sport, m in s["by_sport"].items():
        if "error" in m: print(f"  {sport:6}: ERROR {m['error']}"); continue
        hr = m.get("hit_rate")
        br = m.get("brier")
        bias = m.get("bias")
        applied = m.get("recommendation_applied")
        applied_str = " [reco applied]" if applied else ""
        print(f"  {sport:6}: n={m['n_games']:3} hit={hr or 0:.3f} brier={br or 0:.3f} bias={(bias or 0)*100:+.1f}pp{applied_str}")
