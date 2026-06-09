"""
EdgeStat -- Model Calibration Map (real outcomes; show-your-work transparency).

For every market family, compares what the MODEL predicted against what ACTUALLY
happened -- straight from the settled pick ledger, no synthetic data. This is the
evidence behind the High Confidence Board's two guards:

  - avg model-predicted prob vs realized hit rate  (the overconfidence gap)
  - net units / ROI over the sample
  - status:
      curated_out -- proven money-loser; HARD-EXCLUDED from the boards
      calibrated  -- >= CAL_MIN_N settled; board blends prob toward realized rate
      model_only  -- too few settled; board shows the raw model number (honest)

A professional desk publishes its calibration. If the model says 55% and 16%
actually happens, you should see that -- and see that we stopped betting it.

Output: data/calibration_map.json  ->  calibration-map.html
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

import prob_calibration as pc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "calibration_map.json")

MIN_N_RANK = 10   # only let well-sampled families drive the "most miscalibrated" sort


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    pc.reset_caches()
    picks = _load(LEDGER).get("picks") or []
    neg = pc.proven_negative_families()
    overconf = pc.overconfident_families()

    agg: Dict[str, Dict[str, float]] = {}
    for p in picks:
        if p.get("result") not in ("won", "lost"):   # ledger uses won/lost/push/pending
            continue
        fam = pc.canon_market_family(p.get("market"))
        pred = p.get("p_predicted")
        if pred is None:
            pred = p.get("prob")
        try:
            pred = float(pred)
        except (TypeError, ValueError):
            pred = None
        a = agg.setdefault(fam, {"n": 0, "wins": 0, "pred_sum": 0.0, "pred_n": 0, "net": 0.0})
        a["n"] += 1
        a["wins"] += 1 if p.get("result") == "won" else 0
        if pred is not None:
            a["pred_sum"] += pred
            a["pred_n"] += 1
        try:
            a["net"] += float(p.get("payout_units"))
        except (TypeError, ValueError):
            pass

    rows: List[Dict[str, Any]] = []
    tot_n = tot_pred = tot_wins = 0.0
    for fam, a in agg.items():
        n = int(a["n"])
        if n <= 0:
            continue
        realized = a["wins"] / n
        avg_pred = (a["pred_sum"] / a["pred_n"]) if a["pred_n"] else None
        status = "curated_out" if fam in neg else ("calibrated" if n >= pc.CAL_MIN_N else "model_only")
        # WHY a family is curated, the honest distinction:
        #   overconfident -- the model's probability itself is broken (realized far
        #                    below predicted); the "edge" is fake at ANY price.
        #   priced_short  -- the probability is ~right but the bet loses at our fair
        #                    price (could still be +EV at a soft book line).
        if fam in overconf:
            miscalibration = "overconfident"
        elif status == "curated_out":
            miscalibration = "priced_short"
        else:
            miscalibration = "ok"
        rows.append({
            "family": fam,
            "n_settled": n,
            "avg_model_pred": round(avg_pred, 4) if avg_pred is not None else None,
            "realized_hit_rate": round(realized, 4),
            "overconfidence_gap": round(avg_pred - realized, 4) if avg_pred is not None else None,
            "net_units": round(a["net"], 2),
            "roi_pct": round(100 * a["net"] / n, 1),
            "status": status,
            "miscalibration": miscalibration,
        })
        if avg_pred is not None:
            tot_n += n
            tot_pred += a["pred_sum"]
            tot_wins += a["wins"]

    # Most-miscalibrated first (well-sampled families only drive the ranking).
    rows.sort(key=lambda r: -((abs(r["overconfidence_gap"]) if r["overconfidence_gap"] is not None else 0)
                              if r["n_settled"] >= MIN_N_RANK else -1))

    n_cur = sum(1 for r in rows if r["status"] == "curated_out")
    n_cal = sum(1 for r in rows if r["status"] == "calibrated")
    n_mod = sum(1 for r in rows if r["status"] == "model_only")
    n_overconf = sum(1 for r in rows if r["miscalibration"] == "overconfident")
    net_protected = round(sum(r["net_units"] for r in rows if r["status"] == "curated_out"), 1)
    overall_pred = round(tot_pred / tot_n, 4) if tot_n else None
    overall_real = round(tot_wins / tot_n, 4) if tot_n else None

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_families": len(rows),
        "n_curated_out": n_cur,
        "n_calibrated": n_cal,
        "n_model_only": n_mod,
        "n_overconfident": n_overconf,
        "units_protected_by_curation": net_protected,
        "overall_avg_model_pred": overall_pred,
        "overall_realized_hit_rate": overall_real,
        "overall_overconfidence_gap": round(overall_pred - overall_real, 4) if overall_pred and overall_real else None,
        "method_note": "Per market family, the model's average predicted probability vs the "
                       "realized hit rate over all settled bets in that family. Positive "
                       "overconfidence_gap = the model was too high. Families proven to lose "
                       "money are curated out of the boards; well-sampled families have their "
                       "displayed probabilities calibrated toward the realized rate.",
        "families": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[calibration-map] {o['n_families']} families | {o['n_curated_out']} curated out "
          f"({o['units_protected_by_curation']}u of losses avoided) | {o['n_calibrated']} calibrated | "
          f"{o['n_model_only']} model-only")
    gap = o.get("overall_overconfidence_gap")
    print(f"  overall: model predicts {o['overall_avg_model_pred']}, realized {o['overall_realized_hit_rate']} "
          f"(gap {gap:+})" if gap is not None else "  overall: insufficient data")
    print("  most miscalibrated (well-sampled):")
    for r in [x for x in o["families"] if x["n_settled"] >= 10][:6]:
        print(f"    {r['family']:24s} n={r['n_settled']:4d} model={r['avg_model_pred']} "
              f"real={r['realized_hit_rate']} gap={r['overconfidence_gap']:+} [{r['status']}]")
