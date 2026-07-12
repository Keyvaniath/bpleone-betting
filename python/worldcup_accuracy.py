"""
EdgeStat -- World Cup model report card.

Reads the settled wc_model_* picks from the unified ledger (the RAW model's
predictions -- p_predicted is the model prob, untouched by the display-time book
shading) and scores them against real results: record, Brier score, calibration
by predicted-probability bucket, and a per-market breakdown. This is the honest,
growing answer to "is the model any good" -- thin at first (a handful of group
games) and sharper every matchday.

Brier and calibration use the RAW model prob on purpose: that's what the
recalibration loop learns from, so the report card tracks the LEARNER. (The
displayed pick is book-shaded; that's a separate display layer.)

Output: data/worldcup_accuracy.json  ->  worldcup.html "Model Report Card"
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "worldcup_accuracy.json")

BUCKETS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 1.01)]


def _settled_wc() -> List[Dict[str, Any]]:
    try:
        with open(LEDGER, encoding="utf-8") as f:
            picks = json.load(f).get("picks") or []
    except Exception:
        picks = []
    out = []
    for p in picks:
        if (p.get("sport") or "") != "WORLDCUP":
            continue
        if not str(p.get("source") or "").startswith("wc_model"):
            continue
        if p.get("voided") or p.get("result") not in ("won", "lost"):
            continue
        pr = p.get("p_predicted")
        if pr is None:
            pr = p.get("prob")
        try:
            pr = float(pr)
        except (TypeError, ValueError):
            continue
        out.append({"prob": pr, "won": p["result"] == "won",
                    "market": p.get("market") or "?", "matchup": p.get("player_or_matchup"),
                    "date": p.get("date")})
    return out


def run() -> Dict[str, Any]:
    rows = _settled_wc()
    n = len(rows)
    wins = sum(1 for r in rows if r["won"])
    brier = round(sum((r["prob"] - (1.0 if r["won"] else 0.0)) ** 2 for r in rows) / n, 4) if n else None

    # Calibration: predicted-prob bucket -> realized hit rate.
    calib = []
    for lo, hi in BUCKETS:
        b = [r for r in rows if lo <= r["prob"] < hi]
        if b:
            calib.append({
                "bucket": f"{int(lo*100)}-{int(hi*100) if hi <= 1 else 100}%",
                "n": len(b),
                "predicted": round(sum(r["prob"] for r in b) / len(b), 3),
                "realized": round(sum(1 for r in b if r["won"]) / len(b), 3),
            })

    # Per-market record.
    by_market: Dict[str, Dict[str, int]] = {}
    for r in rows:
        m = by_market.setdefault(r["market"], {"n": 0, "won": 0})
        m["n"] += 1
        m["won"] += 1 if r["won"] else 0
    markets = [{"market": k, "n": v["n"], "won": v["won"],
                "hit_rate": round(v["won"] / v["n"], 3)} for k, v in by_market.items()]
    markets.sort(key=lambda x: -x["n"])

    # Honest read: is the model over/under-confident overall?
    avg_pred = round(sum(r["prob"] for r in rows) / n, 3) if n else None
    realized = round(wins / n, 3) if n else None
    verdict = "accruing"
    if n >= 20 and avg_pred is not None:
        gap = avg_pred - realized
        verdict = ("well-calibrated" if abs(gap) < 0.05 else
                   ("over-confident" if gap > 0 else "under-confident"))

    result = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "n_settled": n,
        "record": f"{wins}-{n - wins}",
        "hit_rate": realized,
        "avg_predicted": avg_pred,
        "brier": brier,
        "verdict": verdict,
        "calibration": calib,
        "by_market": markets,
        "note": ("The RAW model's record vs real results (the learner; the displayed pick is "
                 "book-shaded separately). Brier lower = sharper; calibration compares the "
                 "model's predicted % to how often it actually happened, per probability "
                 "bucket. Thin early, sharper each matchday."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[wc-accuracy] {o['n_settled']} settled | {o['record']} ({o['hit_rate']}) | "
          f"Brier {o['brier']} | avg pred {o['avg_predicted']} -> {o['verdict']}")
    for c in o["calibration"]:
        print(f"    {c['bucket']:8s} n={c['n']:3d} predicted {c['predicted']} -> realized {c['realized']}")
    for m in o["by_market"]:
        print(f"    {m['market']:12s} {m['won']}/{m['n']} ({m['hit_rate']})")
