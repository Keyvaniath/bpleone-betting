"""
EdgeStat -- Learning Integrity audit.

Answers the question: "is the model actually learning skill, or fitting noise?"

For each source, computes:
  - Wilson 95% CI on hit rate (NOT naive p-hat -- handles small samples honestly)
  - (2026-11-03) CALIBRATION test: realized wins vs the model's own predicted
    probabilities (sum of p), two-sided z / p-value. Significant = the
    probabilities are WRONG (something to learn), not an edge. The old test vs
    50% chance said nothing: a 75%-predicted prop that hits 70% "beats chance"
    and still loses money at its own price.
  - (2026-11-03) EDGE test: ROI at a REAL sportsbook price -- class A/B rows only
    (price_provenance.class), one-sample t on per-pick units. Class C rows
    (model fair odds / PrizePicks break-even) never count toward an edge.
  - Brier score (calibration quality, lower = better) -- requires p_predicted
  - ECE proxy (predicted vs actual hit rate in 0.05 buckets)
  - CLV proxy (entry odds vs closing odds, from all_picks_ledger)
  - Sample-size grade (A/B/C/D/F based on n_settled)
  - Concept drift flag (this-month hit rate vs prior-month significantly different?)

Each source gets a LEARNING_GRADE (2026-11-03 rewrite):
  A: >=50 class A/B picks, ROI > 0 with edge p<0.05, brier<0.24, calibration
     not rejected, CLV not negative                  -- TRUSTED (edge at a real price)
  B: n>=30, brier<0.24, calibration not rejected     -- CALIBRATED (probs honest; no edge proven)
  C: n>=30 but miscalibrated (calibration p<0.05)    -- MISCALIBRATED
     n 20-29                                         -- WATCH / EMERGING
  D: n>=10                                           -- TOO EARLY
  F: n<10                                            -- INSUFFICIENT DATA, ignoring
STRONG_SIGNAL (aggregate) requires A grades. Universe: working ledger, settled
AND NOT voided, result won/lost.

Output: data/learning_integrity.json + data/learning_guards.json
"""
from __future__ import annotations

import os
import math
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "learning_integrity.json")
GUARDS_OUT = os.path.join(DATA_DIR, "learning_guards.json")

MIN_N_FOR_LEARNING = 20          # Below this, NO weight changes from learning
MAX_WEIGHT_DELTA_PER_CYCLE = 0.05  # Cap learning velocity
SIGNIFICANCE_THRESHOLD = 0.05      # p-value for "real signal"
WILSON_Z = 1.96                    # 95% confidence


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _wilson_ci(hits: int, n: int) -> Tuple[float, float, float]:
    """Wilson score interval for binomial proportion. Returns (lo, p_hat, hi)."""
    if n == 0: return (0.0, 0.0, 1.0)
    z = WILSON_Z
    p = hits / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    spread = z * math.sqrt(p*(1-p)/n + z**2/(4*n*n)) / denom
    return (max(0.0, center - spread), p, min(1.0, center + spread))


def _binomial_p_value(hits: int, n: int, p0: float = 0.5) -> float:
    """Two-sided binomial test against null p0=50% via normal approximation
    (good for n>=20). For tiny n, returns a conservative 1.0."""
    if n < 5: return 1.0
    mean = n * p0
    var = n * p0 * (1 - p0)
    if var <= 0: return 1.0
    z = abs(hits - mean) / math.sqrt(var)
    # two-sided p-value via standard normal complement
    def _norm_cdf(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return 2 * (1 - _norm_cdf(z))


def _y(p: Dict[str, Any]) -> Optional[int]:
    """(2026-11-03) 1 won / 0 lost / None otherwise. The ledger's `outcome` is a
    DICT (stat/actual/line), so the old str(outcome).upper() test scored every
    pick as a loss and the Brier collapsed to mean(p^2)."""
    r = p.get("result")
    return 1 if r == "won" else (0 if r == "lost" else None)


def _prob(p: Dict[str, Any]) -> Optional[float]:
    v = p.get("p_predicted")
    if v is None:
        v = p.get("prob")
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if 0.0 < v < 1.0 else None


def _norm_sf2(z: float) -> float:
    return 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def _calibration_test(picks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """(2026-11-03) Wins vs the sum of predicted probabilities (Poisson-binomial,
    normal approx). Two-sided: a small p means the probabilities are off."""
    n = 0; wins = 0; mu = 0.0; var = 0.0
    for p in picks:
        y, q = _y(p), _prob(p)
        if y is None or q is None:
            continue
        n += 1; wins += y; mu += q; var += q * (1 - q)
    if n < 5 or var <= 0:
        return {"n": n, "p_value": 1.0, "z": None, "mean_pred": (mu / n if n else None),
                "hit_rate": (wins / n if n else None)}
    z = (wins - mu) / math.sqrt(var)
    return {"n": n, "z": round(z, 2), "p_value": round(_norm_sf2(z), 4),
            "mean_pred": round(mu / n, 4), "hit_rate": round(wins / n, 4)}


def _edge_test(picks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """(2026-11-03) ROI at a real sportsbook price: class A/B rows with a recorded
    payout. One-sample t on per-pick units (normal approx). Class C never counts."""
    us = []
    for p in picks:
        cls = ((p.get("price_provenance") or {}).get("class") or "C").upper()
        if cls not in ("A", "B") or _y(p) is None:
            continue
        u = p.get("payout_units")
        if not isinstance(u, (int, float)):
            continue
        us.append(float(u))
    n = len(us)
    if n < 10:   # too few book-priced picks for any test
        return {"n_book": n, "roi_book_pct": (round(100 * us[0], 2) if n == 1 else None), "p_value": 1.0, "t": None}
    m = sum(us) / n
    sd = math.sqrt(sum((u - m) ** 2 for u in us) / (n - 1))
    t = m / (sd / math.sqrt(n)) if sd > 0 else 0.0
    return {"n_book": n, "roi_book_pct": round(100 * m, 2), "t": round(t, 2),
            "p_value": round(_norm_sf2(t), 4)}


def _brier_score(picks: List[Dict[str, Any]]) -> Optional[float]:
    """Brier score on settled picks where we have a model probability at pick time.
       Brier = mean( (p_predicted - outcome_01)^2 ). Lower is better. 0.25 = chance."""
    if not picks: return None
    n_valid = 0
    total = 0.0
    for p in picks:
        prob, outcome_01 = _prob(p), _y(p)   # (2026-11-03) real result field
        if prob is None or outcome_01 is None: continue
        total += (prob - outcome_01) ** 2
        n_valid += 1
    if n_valid == 0: return None
    return total / n_valid


def _calibration_buckets(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bucket settled picks by predicted-probability bin, return per-bucket actual hit rate."""
    buckets = {  # 0.0-0.1, 0.1-0.2, ..., 0.9-1.0
        i / 10: {"lo": i/10, "hi": (i+1)/10, "n": 0, "hits": 0} for i in range(10)
    }
    for p in picks:
        prob, outcome_01 = _prob(p), _y(p)   # (2026-11-03) real result field
        if prob is None or outcome_01 is None: continue
        bin_key = min(0.9, math.floor(prob * 10) / 10)
        buckets[bin_key]["n"] += 1
        buckets[bin_key]["hits"] += outcome_01
    out = []
    for k in sorted(buckets.keys()):
        b = buckets[k]
        out.append({
            "predicted_range": f"{b['lo']:.1f}-{b['hi']:.1f}",
            "n": b["n"],
            "actual_hit_rate": (b["hits"] / b["n"]) if b["n"] > 0 else None,
            "predicted_midpoint": (b["lo"] + b["hi"]) / 2,
        })
    return out


def _ece(picks: List[Dict[str, Any]]) -> Optional[float]:
    """Expected Calibration Error: weighted gap between predicted and actual per bucket."""
    buckets = _calibration_buckets(picks)
    total_n = sum(b["n"] for b in buckets)
    if total_n == 0: return None
    ece = 0.0
    for b in buckets:
        if b["n"] == 0 or b["actual_hit_rate"] is None: continue
        gap = abs(b["predicted_midpoint"] - b["actual_hit_rate"])
        ece += (b["n"] / total_n) * gap
    return ece


def _grade(n: int, calib: Dict[str, Any], edge: Dict[str, Any], brier: Optional[float],
           clv_pp: Optional[float]) -> Tuple[str, str]:
    """(2026-11-03) Sample-size + calibration + edge-at-a-real-price grade."""
    if n < 10:
        return "F", "INSUFFICIENT_DATA"
    if n < MIN_N_FOR_LEARNING:
        return "D", "TOO_EARLY"
    if n < 30:
        if calib.get("p_value", 1.0) < SIGNIFICANCE_THRESHOLD * 2:
            return "C", "EMERGING_SIGNAL"
        return "C", "WATCH"
    # n >= 30
    calibrated = (brier is not None and brier < 0.24
                  and calib.get("p_value", 1.0) >= SIGNIFICANCE_THRESHOLD)
    edge_proven = ((edge.get("n_book") or 0) >= 50
                   and (edge.get("roi_book_pct") or 0) > 0
                   and edge.get("p_value", 1.0) < SIGNIFICANCE_THRESHOLD)
    clv_ok = clv_pp is None or clv_pp >= 0
    if edge_proven and calibrated and clv_ok:
        return "A", "TRUSTED"
    if calibrated:
        return "B", "CALIBRATED"
    return "C", "MISCALIBRATED"


def _drift(picks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Concept drift: compare last 30d hit rate vs prior 30d. Statistically different?"""
    if len(picks) < 20: return {"insufficient_data": True}
    now = dt.datetime.utcnow()
    recent, prior = [], []
    for p in picks:
        ds = p.get("settled_at") or p.get("date") or p.get("created_at")
        if not ds: continue
        try:
            d = dt.datetime.fromisoformat(str(ds).replace("Z", "")[:19])
        except Exception:
            continue
        age = (now - d).days
        outcome_01 = _y(p)   # (2026-11-03) real result field
        if outcome_01 is None: continue
        if age <= 30: recent.append(outcome_01)
        elif age <= 60: prior.append(outcome_01)
    if len(recent) < 5 or len(prior) < 5:
        return {"insufficient_data": True, "n_recent": len(recent), "n_prior": len(prior)}
    p_recent = sum(recent) / len(recent)
    p_prior = sum(prior) / len(prior)
    # Two-proportion Z-test
    n1, n2 = len(recent), len(prior)
    p_pool = (sum(recent) + sum(prior)) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
    if se <= 0: return {"insufficient_data": True}
    z = (p_recent - p_prior) / se
    def _norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    p_value = 2 * (1 - _norm_cdf(abs(z)))
    return {
        "n_recent": n1, "n_prior": n2,
        "recent_hit_rate": round(p_recent, 3),
        "prior_hit_rate": round(p_prior, 3),
        "delta_pp": round((p_recent - p_prior) * 100, 1),
        "z_score": round(z, 2),
        "p_value": round(p_value, 4),
        "is_drifting": bool(p_value < 0.10 and abs(p_recent - p_prior) > 0.10),
    }


def _cross_source_overlap(by_source_picks: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Jaccard overlap of pick sets across sources -- sources >70% overlap are not independent."""
    out = []
    keys = list(by_source_picks.keys())
    for i, a in enumerate(keys):
        for b in keys[i+1:]:
            s1 = set(by_source_picks.get(a, []))
            s2 = set(by_source_picks.get(b, []))
            if not s1 or not s2: continue
            inter = len(s1 & s2)
            union = len(s1 | s2)
            jacc = inter / union if union > 0 else 0
            if jacc >= 0.30:
                out.append({
                    "source_a": a, "source_b": b,
                    "jaccard": round(jacc, 3),
                    "overlap_count": inter,
                    "warning": "HIGH_OVERLAP" if jacc >= 0.7 else "MODERATE_OVERLAP",
                })
    return sorted(out, key=lambda x: -x["jaccard"])


def run() -> Dict[str, Any]:
    ledger = _load(os.path.join(DATA_DIR, "all_picks_ledger.json"))
    by_source = ledger.get("by_source") or {}
    picks = ledger.get("picks") or ledger.get("rows") or []

    # Index picks by source for Brier/ECE/drift calcs
    picks_by_source: Dict[str, List[Dict[str, Any]]] = {}
    pick_ids_by_source: Dict[str, List[str]] = {}
    for p in picks:
        if p.get("voided"):
            continue  # duplicate-collapsed copies must not enter training/metrics
        # (2026-11-03) settled AND NOT voided, decided only -- pending picks had
        # been scored as losses in the Brier/ECE/drift calcs
        if not p.get("settled") or _y(p) is None:
            continue
        src = p.get("source") or "unknown"
        picks_by_source.setdefault(src, []).append(p)
        pid = p.get("pick_id") or p.get("id") or f"{src}|{p.get('player')}|{p.get('market')}|{p.get('date')}"
        pick_ids_by_source.setdefault(src, []).append(pid)

    rows: List[Dict[str, Any]] = []
    guards: Dict[str, Dict[str, Any]] = {}
    # (2026-11-03) counts come from the same filtered picks as every other metric
    # (by_source is all-time incl. the archive; the picks are the working ledger)
    for source in sorted(set(by_source) | set(picks_by_source)):
        _sp = picks_by_source.get(source, [])
        hits = sum(1 for p in _sp if _y(p) == 1)
        losses = sum(1 for p in _sp if _y(p) == 0)
        n = hits + losses
        if n == 0:
            rows.append({
                "source": source, "n_settled": 0, "grade": "F",
                "status": "NO_SETTLED_PICKS", "trustworthy": False,
            })
            guards[source] = {"trustworthy": False, "max_weight_delta": 0.0,
                              "reason": "no_settled_picks"}
            continue

        wilson_lo, p_hat, wilson_hi = _wilson_ci(hits, n)
        src_picks = picks_by_source.get(source, [])
        # (2026-11-03) tests vs the predicted probability and at a real price
        calib = _calibration_test(src_picks)
        edge = _edge_test(src_picks)
        # primary p-value for the learning-velocity guard: the edge test where
        # the source has book-priced picks, else the calibration test
        p_value = edge["p_value"] if (edge.get("n_book") or 0) >= MIN_N_FOR_LEARNING else calib["p_value"]
        unverified = any(p.get("sport") == "MLB-PP" for p in src_picks)
        brier = _brier_score(src_picks)
        ece = _ece(src_picks)
        drift = _drift(src_picks)

        # CLV from settled picks (entry_odds vs closing_odds)
        clv_values = []
        for p in src_picks:
            entry = p.get("entry_odds") or p.get("open_odds")
            close = p.get("closing_odds") or p.get("close_odds")
            if entry is None or close is None: continue
            try:
                def _imp(o):
                    o = float(o)
                    return abs(o)/(abs(o)+100)*100 if o < 0 else 100/(o+100)*100
                clv_values.append(_imp(entry) - _imp(close))
            except Exception:
                continue
        clv_pp = (sum(clv_values) / len(clv_values)) if clv_values else None

        grade, status = _grade(n, calib, edge, brier, clv_pp)
        trustworthy = grade in ("A", "B")

        rows.append({
            "source": source,
            "n_settled": n,
            "n_hits": hits,
            "n_misses": losses,
            "hit_rate": round(p_hat, 3),
            "wilson_lo_95": round(wilson_lo, 3),
            "wilson_hi_95": round(wilson_hi, 3),
            # (2026-11-03) replaced z/p vs 50% chance
            "mean_predicted": calib.get("mean_pred"),
            "z_vs_predicted": calib.get("z"),
            "p_value_calibration": calib.get("p_value"),
            "is_miscalibrated": bool(calib.get("p_value", 1.0) < SIGNIFICANCE_THRESHOLD),
            "n_book_priced": edge.get("n_book"),
            "roi_book_pct": edge.get("roi_book_pct"),
            "p_value_edge": edge.get("p_value"),
            "is_significant": bool((edge.get("n_book") or 0) >= 30 and (edge.get("roi_book_pct") or 0) > 0
                                   and edge.get("p_value", 1.0) < SIGNIFICANCE_THRESHOLD),
            "p_value": round(p_value, 4),
            "unverified": unverified,
            "brier_score": round(brier, 4) if brier is not None else None,
            "ece": round(ece, 4) if ece is not None else None,
            "clv_pp": round(clv_pp, 2) if clv_pp is not None else None,
            "drift": drift,
            "grade": grade,
            "status": status,
            "trustworthy": trustworthy,
        })

        # Build guards: how much can this source's weight move per cycle?
        if n < MIN_N_FOR_LEARNING:
            max_delta = 0.0  # NO learning until we have data
            reason = f"need {MIN_N_FOR_LEARNING - n} more settled picks"
        else:
            # Scale velocity by significance + sample
            confidence_factor = min(1.0, n / 100) * (1 - min(1.0, p_value * 10))
            max_delta = MAX_WEIGHT_DELTA_PER_CYCLE * confidence_factor
            reason = f"velocity capped at {round(max_delta,3)} (n={n}, p={round(p_value,3)})"

        guards[source] = {
            "trustworthy": trustworthy,
            "max_weight_delta": round(max_delta, 4),
            "use_wilson_lo": grade in ("D", "F", "C"),  # below B = use conservative lo bound
            "reason": reason,
            "grade": grade,
        }

    # Cross-source overlap analysis
    overlaps = _cross_source_overlap(pick_ids_by_source)

    rows.sort(key=lambda r: (-(r["n_settled"]), r["source"]))

    # Compute aggregate learning quality score 0-100
    total = sum(r["n_settled"] for r in rows)
    trustworthy_n = sum(r["n_settled"] for r in rows if r.get("trustworthy"))
    a_grade_n = sum(r["n_settled"] for r in rows if r.get("grade") == "A")
    if total == 0:
        learning_quality_score = 0
        verdict = "NO_DATA_YET"
    elif total < 50:
        learning_quality_score = max(5, min(35, int(total)))
        verdict = "BOOTSTRAPPING"
    elif trustworthy_n / total < 0.30:
        learning_quality_score = 40 + int(20 * trustworthy_n / total)
        verdict = "LOW_SIGNAL"
    else:
        base = 50 + int(30 * trustworthy_n / total)
        bonus = int(20 * a_grade_n / total)
        learning_quality_score = min(95, base + bonus)
        verdict = "LEARNING" if learning_quality_score < 75 else "STRONG_SIGNAL"
        # (2026-11-03) STRONG_SIGNAL needs A grades (edge at a real price). Calibrated
        # probabilities alone are not an edge -- cap the score below the bar.
        if a_grade_n == 0:
            learning_quality_score = min(learning_quality_score, 74)
            verdict = "CALIBRATION_ONLY"

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "learning_quality_score": learning_quality_score,
        "verdict": verdict,
        "n_total_settled_picks": total,
        "n_sources": len(rows),
        "n_trustworthy_sources": sum(1 for r in rows if r.get("trustworthy")),
        "n_insufficient_sources": sum(1 for r in rows if r.get("grade") in ("D", "F")),
        "min_n_for_learning": MIN_N_FOR_LEARNING,
        "significance_threshold": SIGNIFICANCE_THRESHOLD,
        "n_a_grade_sources": sum(1 for r in rows if r.get("grade") == "A"),
        "universe": "working ledger, settled AND NOT voided, won/lost (2026-11-03)",
        "max_weight_delta_per_cycle": MAX_WEIGHT_DELTA_PER_CYCLE,
        "rows": rows,
        "cross_source_overlaps": overlaps,
        "interpretation": (
            "F = insufficient data (<10 picks), ignoring this source's signal. "
            "D = too early (10-19). C = watch (20-29), or miscalibrated (30+, wins differ from the "
            "model's predicted probabilities at p<0.05). B = calibrated (30+, brier<0.24, predictions "
            "consistent with outcomes) -- honest probabilities, NO edge proven. "
            "A = trusted: 50+ picks at a real sportsbook price (class A/B) with ROI > 0 at p<0.05, "
            "calibrated, CLV not negative. Hit rate vs 50% is not a test of skill and is no longer used. "
            "Only A/B sources have weight changes applied. Wilson lower bound used for C+ if available."
        ),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    with open(GUARDS_OUT, "w") as f: json.dump(guards, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[integrity] LQS={o['learning_quality_score']}/100 ({o['verdict']}) "
          f"-- {o['n_trustworthy_sources']}/{o['n_sources']} sources trustworthy "
          f"({o['n_total_settled_picks']} total settled picks)")
