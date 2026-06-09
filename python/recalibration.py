"""
EdgeStat -- generator-level recalibration.

The raw model probabilities are overconfident (ECE ~11% over the settled ledger).
The display boards already curate + calibrate before showing a number, but the
RAW probs the generators emit -- and that the self-learning ledger trains on --
are still miscalibrated. This module learns an honest probability transform from
the settled outcomes so the calibrated prob can be applied UPSTREAM (at the slate
pots / ledger), making the model's numbers true at the source.

Method: per canonical market family, fit a MONOTONIC calibration curve mapping
model-predicted prob -> realized hit rate, using
  - prediction-bucketed realized rates (preserves within-family RANKING, unlike a
    single family-average blend),
  - Bayesian shrinkage of each bucket toward the identity (raw prob) by sample
    count (thin buckets stay near the model),
  - pool-adjacent-violators (isotonic regression) to enforce monotonicity,
  - graceful fallback: a family-average Bayesian blend for mid-sample families,
    identity for families with too little settled history.

Honest note: this does NOT manufacture ROI. Pricing at your own (calibrated) fair
odds is 0-EV by construction; real edge needs a market price (the odds feed). What
recalibration buys is TRUTH -- a displayed 72% actually hits ~72% (ECE collapses)
-- and once the odds feed returns, model-vs-book edges are real instead of inflated
by the model's overconfidence. It also gives the self-learning loop an honest
probability to train on.

Output: data/recalibration_map.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import prob_calibration as pc
import calibration as _cal

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "recalibration_map.json")

MIN_N_BUCKETED = 80    # fit a bucketed isotonic curve at/above this many settled bets
MIN_N_FAMILY = 30      # else a single family-average Bayesian blend
PRIOR_K = 12.0         # shrinkage of each bucket/family toward the raw (identity) prior


def _clamp(p: float) -> float:
    return max(0.01, min(0.99, p))


def _load_ledger() -> Dict[str, Any]:
    if not os.path.exists(LEDGER):
        return {}
    try:
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _pairs_by_family() -> Dict[str, List[Tuple[float, int]]]:
    """{canonical_family: [(predicted_prob, outcome 0/1), ...]} from settled picks."""
    out: Dict[str, List[Tuple[float, int]]] = {}
    for p in (_load_ledger().get("picks") or []):
        if p.get("result") not in ("won", "lost"):
            continue
        pr = p.get("p_predicted")
        if pr is None:
            pr = p.get("prob")
        try:
            pr = float(pr)
        except (TypeError, ValueError):
            continue
        if not (0.0 < pr < 1.0):
            continue
        y = 1 if p.get("result") == "won" else 0
        out.setdefault(pc.canon_market_family(p.get("market")), []).append((pr, y))
    return out


def _pava(ys: List[float], ws: List[float]) -> List[float]:
    """Weighted pool-adjacent-violators -> non-decreasing isotonic fit of ys."""
    blocks: List[List[float]] = []   # [value, weight, count]
    for v, w in zip(ys, ws):
        blocks.append([v, w, 1])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            nv = (v1 * w1 + v2 * w2) / (w1 + w2)
            blocks.append([nv, w1 + w2, c1 + c2])
    out: List[float] = []
    for v, w, c in blocks:
        out.extend([v] * int(c))
    return out


def _fit_family(pairs: List[Tuple[float, int]]) -> Optional[Dict[str, Any]]:
    n = len(pairs)
    if n < MIN_N_FAMILY:
        return None  # too little history -> identity (trust the model)
    if n < MIN_N_BUCKETED:
        realized = sum(y for _, y in pairs) / n
        return {"method": "family_avg", "n": n, "realized": round(realized, 4)}
    # bucketed isotonic
    pairs = sorted(pairs, key=lambda t: t[0])
    k = max(3, min(8, n // 25))
    size = n / k
    mps: List[float] = []
    cals: List[float] = []
    ws: List[float] = []
    for b in range(k):
        lo = int(round(b * size))
        hi = int(round((b + 1) * size)) if b < k - 1 else n
        seg = pairs[lo:hi]
        if not seg:
            continue
        nb = len(seg)
        mp = sum(p for p, _ in seg) / nb
        realized = sum(y for _, y in seg) / nb
        cal = (PRIOR_K * mp + nb * realized) / (PRIOR_K + nb)  # shrink toward identity
        mps.append(mp)
        cals.append(cal)
        ws.append(nb)
    iso = _pava(cals, ws)
    anchors = [[round(mp, 4), round(_clamp(c), 4)] for mp, c in zip(mps, iso)]
    return {"method": "bucketed", "n": n, "anchors": anchors}


def _interp(x: float, anchors: List[List[float]]) -> float:
    xs = [a[0] for a in anchors]
    ys = [a[1] for a in anchors]
    if not xs:
        return x
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return ys[-1]


def _apply(fit: Dict[str, Any], raw: float) -> float:
    if fit["method"] == "family_avg":
        n, r = fit["n"], fit["realized"]
        return _clamp((PRIOR_K * raw + n * r) / (PRIOR_K + n))
    return _clamp(_interp(raw, fit["anchors"]))


_MAP_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def _maps() -> Dict[str, Dict[str, Any]]:
    global _MAP_CACHE
    if _MAP_CACHE is None:
        _MAP_CACHE = {}
        for fam, pairs in _pairs_by_family().items():
            fit = _fit_family(pairs)
            if fit:
                _MAP_CACHE[fam] = fit
    return _MAP_CACHE


def recalibrate(raw_prob, market) -> float:
    """Public transform: model-predicted prob -> calibrated prob for `market`.
    Identity if the market's family has too little settled history."""
    try:
        raw = float(raw_prob)
    except (TypeError, ValueError):
        return raw_prob
    if not (0.0 < raw < 1.0):
        return raw_prob
    fit = _maps().get(pc.canon_market_family(market)) or _maps().get(pc.market_family(market))
    return _apply(fit, raw) if fit else raw


def recalibrate_family(family_key, raw_prob) -> float:
    """Apply the fitted isotonic transform for an ALREADY-canonical family key
    (e.g. one reconstructed from market+play+line). Identity if no fit / bad input.
    This is the upstream entry prob_calibration routes its calibration through, so
    every board gets the bucketed isotonic curve instead of a flat family average."""
    try:
        raw = float(raw_prob)
    except (TypeError, ValueError):
        return raw_prob
    if not (0.0 < raw < 1.0):
        return raw_prob
    fit = _maps().get(family_key)
    return _apply(fit, raw) if fit else raw


def reset_caches() -> None:
    global _MAP_CACHE
    _MAP_CACHE = None


def run() -> Dict[str, Any]:
    pc.reset_caches()
    reset_caches()
    fam_pairs = _pairs_by_family()
    maps = _maps()

    all_raw: List[float] = []
    all_y: List[int] = []
    all_cal: List[float] = []
    families: List[Dict[str, Any]] = []

    for fam, pairs in fam_pairs.items():
        ps = [p for p, _ in pairs]
        ys = [y for _, y in pairs]
        fit = maps.get(fam)
        cps = [(_apply(fit, p) if fit else p) for p in ps]
        all_raw += ps
        all_y += ys
        all_cal += cps
        n = len(pairs)
        nb = min(10, max(2, n // 20))
        ece_raw = _cal.expected_calibration_error(ps, ys, nb)
        ece_cal = _cal.expected_calibration_error(cps, ys, nb)
        families.append({
            "family": fam,
            "n": n,
            "method": fit["method"] if fit else "identity",
            "avg_pred_raw": round(sum(ps) / n, 4),
            "avg_pred_calibrated": round(sum(cps) / n, 4),
            "realized": round(sum(ys) / n, 4),
            "ece_raw": round(ece_raw, 4),
            "ece_calibrated": round(ece_cal, 4),
            "transform": ({"anchors": fit["anchors"]} if fit and fit["method"] == "bucketed"
                          else ({"realized": fit["realized"]} if fit else None)),
        })

    families.sort(key=lambda f: -(f["ece_raw"] - f["ece_calibrated"]))
    N = len(all_raw)
    ece_before = _cal.expected_calibration_error(all_raw, all_y, 10) if N else 0.0
    ece_after = _cal.expected_calibration_error(all_cal, all_y, 10) if N else 0.0
    brier_before = _cal.brier_score(all_raw, all_y) if N else 0.0
    brier_after = _cal.brier_score(all_cal, all_y) if N else 0.0

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_settled": N,
        "n_families_transformed": sum(1 for f in families if f["method"] != "identity"),
        "n_families_bucketed": sum(1 for f in families if f["method"] == "bucketed"),
        "ece_before": round(ece_before, 4),
        "ece_after": round(ece_after, 4),
        "ece_improvement": round(ece_before - ece_after, 4),
        "brier_before": round(brier_before, 5),
        "brier_after": round(brier_after, 5),
        "method_note": "Per market family, a monotonic (isotonic) curve maps the model's "
                       "predicted probability to the realized hit rate, learned from settled "
                       "outcomes. Bucketed for well-sampled families (preserves ranking), a "
                       "family-average Bayesian blend for mid-sample, identity below that. "
                       "ECE = expected calibration error (lower = the displayed % is truer). "
                       "This makes the model honest at the source; it does not create edge "
                       "(that needs a market price).",
        "families": families,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    _append_history(result)
    return result


HISTORY = os.path.join(DATA_DIR, "recalibration_history.json")
HISTORY_KEEP = 90  # daily points


def _append_history(res: Dict[str, Any]) -> None:
    """One calibration-health point per day -> data/recalibration_history.json.
    Lets the front-end chart ECE/Brier drift as outcomes accrue (is the honesty
    layer holding, improving, or degrading). Last write of the day wins."""
    try:
        hist = []
        if os.path.exists(HISTORY):
            with open(HISTORY, encoding="utf-8") as f:
                hist = json.load(f).get("points") or []
        day = res["generated_at"][:10]
        point = {"date": day, "n_settled": res["n_settled"],
                 "ece_raw": res["ece_before"], "ece_calibrated": res["ece_after"],
                 "brier_raw": res["brier_before"], "brier_calibrated": res["brier_after"],
                 "n_families_transformed": res["n_families_transformed"]}
        hist = [p for p in hist if p.get("date") != day] + [point]
        hist = sorted(hist, key=lambda p: p["date"])[-HISTORY_KEEP:]
        with open(HISTORY, "w", encoding="utf-8") as f:
            json.dump({"updated_at": res["generated_at"], "points": hist,
                       "note": ("Daily calibration-health trail: ECE/Brier of the raw model "
                                "probs vs the isotonic-calibrated probs over all settled picks "
                                "(in-sample, recomputed as outcomes accrue).")}, f, indent=2)
    except Exception:
        pass  # the history trail must never break the recalibration run


if __name__ == "__main__":
    o = run()
    print(f"[recalibration] {o['n_settled']} settled | {o['n_families_transformed']} families "
          f"transformed ({o['n_families_bucketed']} bucketed)")
    print(f"  ECE   {o['ece_before']} -> {o['ece_after']}  (improvement {o['ece_improvement']:+})")
    print(f"  Brier {o['brier_before']} -> {o['brier_after']}")
    print("  biggest calibration gains:")
    for f in o["families"][:8]:
        if f["method"] != "identity":
            print(f"    {f['family']:22s} n={f['n']:4d} [{f['method']:10s}] "
                  f"model {f['avg_pred_raw']} -> cal {f['avg_pred_calibrated']} (real {f['realized']}) "
                  f"ECE {f['ece_raw']}->{f['ece_calibrated']}")
