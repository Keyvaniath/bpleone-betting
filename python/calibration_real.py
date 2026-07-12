"""
EdgeStat -- REAL overall calibration report from the settled ledger.

Overwrites the old data/calibration.json (which was a SYNTHETIC demo emitted by
calibration.py's __main__) with the genuine reliability diagram, Brier, log-loss
and ECE computed from every settled pick's model probability vs its ACTUAL
outcome. This powers the ML Lab reliability chart (js/ml-lab.js) -- so that chart
now shows the model's true calibration, not a demo.

Reuses calibration.py's scoring machinery; no synthetic data.

Output: data/calibration.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

import calibration as cal

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "calibration.json")


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run() -> Dict[str, Any]:
    picks = _load(LEDGER).get("picks") or []
    preds: List[float] = []
    y: List[int] = []
    for p in picks:
        if p.get("voided") or p.get("result") not in ("won", "lost"):
            continue
        pr = p.get("p_predicted")
        if pr is None:
            pr = p.get("prob")
        try:
            pr = float(pr)
        except (TypeError, ValueError):
            continue
        if pr <= 0.0 or pr >= 1.0:
            continue
        preds.append(pr)
        y.append(1 if p.get("result") == "won" else 0)

    if len(preds) < 20:
        # Not enough settled history to publish a real curve; leave any existing
        # file untouched rather than write something misleading.
        return {"n": len(preds), "skipped": "insufficient settled picks"}

    report = cal.calibration_report(preds, y)
    report["source"] = "settled pick ledger -- real model probabilities vs actual outcomes"
    report["generated_at"] = dt.datetime.utcnow().isoformat(timespec="seconds")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return report


if __name__ == "__main__":
    o = run()
    if "skipped" in o:
        print(f"[calibration-real] skipped: {o['skipped']} (n={o['n']})")
    else:
        print(f"[calibration-real] n={o['n']} brier={o['brier']} ece={o['ece']} acc={o['accuracy']} "
              f"-> {OUT}")
        print("  reliability (predicted -> observed):")
        for b in o["reliability"]:
            if b["n"]:
                print(f"    {b['bucket']}: pred={b['predicted']} obs={b['observed']} gap={b['gap']:+} n={b['n']}")
