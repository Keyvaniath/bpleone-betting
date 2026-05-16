"""
EdgeStat -- per-prop confidence interval via bootstrap.

For each prop in best_bets with at least 10 historical samples on the
player, bootstrap-resamples those outcomes 1000 times to compute the
68% and 95% CI on the player's true hit rate. This adds an uncertainty
band on top of the point model probability.

Output: data/per_prop_ci.json
  {
    "generated_at": "...",
    "by_key": {
      "{pid}_{market}_{line}": {
        "model_prob": 0.62,
        "n_samples": 23,
        "bootstrap_mean": 0.61,
        "ci_68_low": 0.54, "ci_68_high": 0.68,
        "ci_95_low": 0.47, "ci_95_high": 0.75,
        "verdict": "high_conf" | "wide_band" | "thin_sample"
      }
    }
  }
"""
from __future__ import annotations
import os, json, random, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BB_PATH = os.path.join(DATA_DIR, "best_bets.json")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "per_prop_ci.json")

N_BOOTSTRAP = 1000


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _samples_for(pid, market, props):
    return [int(p.get("play_hit") is True) for p in props
            if p.get("player_id") == pid and p.get("market") == market
            and p.get("play_hit") in (True, False)]


def _bootstrap_ci(samples: List[int]) -> Dict[str, float]:
    if not samples:
        return {}
    means = []
    random.seed(42)
    n = len(samples)
    for _ in range(N_BOOTSTRAP):
        resample = [samples[random.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    return {
        "mean": round(sum(means) / len(means), 3),
        "ci_68_low":  round(means[int(N_BOOTSTRAP * 0.16)], 3),
        "ci_68_high": round(means[int(N_BOOTSTRAP * 0.84)], 3),
        "ci_95_low":  round(means[int(N_BOOTSTRAP * 0.025)], 3),
        "ci_95_high": round(means[int(N_BOOTSTRAP * 0.975)], 3),
    }


def run() -> Dict[str, Any]:
    bets = _load(BB_PATH).get("bets") or []
    props = _load(TR_PATH).get("props") or []
    by_key: Dict[str, Dict[str, Any]] = {}
    for b in bets:
        pid = b.get("player_id")
        market = b.get("market")
        line = b.get("line")
        if pid is None or market is None:
            continue
        samples = _samples_for(pid, market, props)
        if len(samples) < 10:
            by_key[f"{pid}_{market}_{line}"] = {
                "model_prob": b.get("model_prob"),
                "n_samples": len(samples),
                "verdict": "thin_sample",
            }
            continue
        ci = _bootstrap_ci(samples)
        band_width = ci["ci_95_high"] - ci["ci_95_low"]
        verdict = "high_conf" if band_width < 0.15 else "moderate" if band_width < 0.25 else "wide_band"
        by_key[f"{pid}_{market}_{line}"] = {
            "model_prob": b.get("model_prob"),
            "n_samples": len(samples),
            "bootstrap_mean": ci["mean"],
            "ci_68_low": ci["ci_68_low"], "ci_68_high": ci["ci_68_high"],
            "ci_95_low": ci["ci_95_low"], "ci_95_high": ci["ci_95_high"],
            "band_width_95": round(band_width, 3),
            "verdict": verdict,
        }
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_props": len(by_key),
        "n_high_conf": sum(1 for v in by_key.values() if v.get("verdict") == "high_conf"),
        "n_wide": sum(1 for v in by_key.values() if v.get("verdict") == "wide_band"),
        "n_thin": sum(1 for v in by_key.values() if v.get("verdict") == "thin_sample"),
        "by_key": by_key,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_props']} props")
    print(f"  high-conf: {p['n_high_conf']}  moderate: {p['n_props']-p['n_high_conf']-p['n_wide']-p['n_thin']}  wide-band: {p['n_wide']}  thin-sample: {p['n_thin']}")
