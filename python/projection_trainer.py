"""
EdgeStat -- LIVE projection trainer (free-feed stat-scale report card).

The paid-feed training loop (multiplier_tuner / model_trainer) trains off
track_record records, which stalled when the DK odds key lapsed. This module
trains off what is ALIVE: the unified ledger. Graders already stamp the real
box-score number onto settled picks (outcome.actual); collectors now carry the
generator's stat-scale projection (expected_k / expected_walks / expected_runs /
expected_h / projected_pts). Pairing the two gives a daily-growing training set
of (projection, actual) per market family -- accruing from the free feeds NOW,
not when the paid key returns.

For each canonical family with enough pairs:
  - rmse           projection accuracy (the score the tuners minimize)
  - bias           mean (projection - actual): + = model projects too high
  - correction     Bayesian-shrunk additive bias fix, k=20 (a 30-pair family
                   applies 60% of its observed bias) -- generators can subtract
                   this from their projection (ADDITIVE adoption, opt-in)
  - rmse_corrected what RMSE would have been with the correction applied
                   (in-sample -- treat as an upper bound on the gain)

Output: data/projection_report.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Tuple

import prob_calibration as pc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "projection_report.json")

MIN_PAIRS = 15      # report a family at/above this many (projection, actual) pairs
SHRINK_K = 20.0     # bias correction shrinkage toward 0


def _pairs_by_family() -> Dict[str, List[Tuple[float, float]]]:
    try:
        with open(LEDGER, encoding="utf-8") as f:
            picks = json.load(f).get("picks") or []
    except Exception:
        picks = []
    out: Dict[str, List[Tuple[float, float]]] = {}
    for p in picks:
        if p.get("result") not in ("won", "lost", "push"):
            continue
        proj = p.get("projection")
        actual = (p.get("outcome") or {}).get("actual")
        if not isinstance(proj, (int, float)) or not isinstance(actual, (int, float)):
            continue
        fam = pc.canon_market_family(p.get("market"))
        out.setdefault(fam, []).append((float(proj), float(actual)))
    return out


def run() -> Dict[str, Any]:
    fams = _pairs_by_family()
    rows: List[Dict[str, Any]] = []
    total_pairs = 0
    for fam, pairs in fams.items():
        n = len(pairs)
        total_pairs += n
        if n < MIN_PAIRS:
            rows.append({"family": fam, "n": n, "status": f"accruing (need {MIN_PAIRS})"})
            continue
        bias = sum(pr - ac for pr, ac in pairs) / n
        rmse = math.sqrt(sum((pr - ac) ** 2 for pr, ac in pairs) / n)
        corr = bias * (n / (n + SHRINK_K))
        rmse_c = math.sqrt(sum((pr - corr - ac) ** 2 for pr, ac in pairs) / n)
        rows.append({
            "family": fam, "n": n,
            "rmse": round(rmse, 3),
            "bias": round(bias, 3),
            "correction": round(corr, 3),
            "rmse_corrected": round(rmse_c, 3),
            "improvement": round(rmse - rmse_c, 4),
            "status": "trained",
        })
    rows.sort(key=lambda r: -(r.get("n") or 0))

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_families": len(rows),
        "n_trained": sum(1 for r in rows if r.get("status") == "trained"),
        "n_pairs_total": total_pairs,
        "min_pairs": MIN_PAIRS,
        "shrink_k": SHRINK_K,
        "note": ("Stat-scale projection report card from the LIVE ledger: the generator's "
                 "projection (carried onto each pick at collection) vs the real box-score "
                 "number the grader settled it with (outcome.actual). bias > 0 = the model "
                 "projects too high. correction = shrunk additive fix generators may adopt; "
                 "rmse_corrected is in-sample (upper bound on the gain). Grows daily from "
                 "the free feeds -- independent of the lapsed paid odds key."),
        "families": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[projection-trainer] {o['n_pairs_total']} pairs across {o['n_families']} families "
          f"({o['n_trained']} trained) -> {OUT}")
    for r in o["families"][:8]:
        if r.get("status") == "trained":
            print(f"    {r['family']:24s} n={r['n']:4d} rmse {r['rmse']:.3f} bias {r['bias']:+.3f} "
                  f"-> corrected rmse {r['rmse_corrected']:.3f}")
        else:
            print(f"    {r['family']:24s} n={r['n']:4d} {r['status']}")
