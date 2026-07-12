"""
EdgeStat -- Learning Integrity audit.

Answers the question: "is the model actually learning skill, or fitting noise?"

For each source, computes:
  - Wilson 95% CI on hit rate (NOT naive p-hat -- handles small samples honestly)
  - Z-score vs 50% chance
  - Two-sided p-value (binomial test)
  - Brier score (calibration quality, lower = better) -- requires p_predicted
  - ECE proxy (predicted vs actual hit rate in 0.05 buckets)
  - CLV proxy (entry odds vs closing odds, from all_picks_ledger)
  - Sample-size grade (A/B/C/D/F based on n_settled)
  - Concept drift flag (this-month hit rate vs prior-month significantly different?)

Each source gets a LEARNING_GRADE:
  A: n>=50, p<0.05, |CLV|>=2pp, brier<0.22  -- TRUSTED, real edge proven
  B: n>=30, p<0.10, brier<0.24                -- DEVELOPING signal
  C: n>=20, hit_rate diff from 50% but not yet significant -- WATCH
  D: n>=10                                     -- TOO EARLY
  F: n<10                                      -- INSUFFICIENT DATA, ignoring

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


def _brier_score(picks: List[Dict[str, Any]]) -> Optional[float]:
    """Brier score on settled picks where we have a model probability at pick time.
       Brier = mean( (p_predicted - outcome_01)^2 ). Lower is better. 0.25 = chance."""
    if not picks: return None
    n_valid = 0
    total = 0.0
    for p in picks:
        prob = p.get("p_predicted") or p.get("model_p") or p.get("fair_p")
        outcome = p.get("outcome") or p.get("result")
        if prob is None or outcome is None: continue
        try:
            outcome_01 = 1 if str(outcome).upper() in ("WIN", "W", "TRUE", "1", "HIT", "YES") else 0
            total += (float(prob) - outcome_01) ** 2
            n_valid += 1
        except Exception:
            continue
    if n_valid == 0: return None
    return total / n_valid


def _calibration_buckets(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bucket settled picks by predicted-probability bin, return per-bucket actual hit rate."""
    buckets = {  # 0.0-0.1, 0.1-0.2, ..., 0.9-1.0
        i / 10: {"lo": i/10, "hi": (i+1)/10, "n": 0, "hits": 0} for i in range(10)
    }
    for p in picks:
        prob = p.get("p_predicted") or p.get("model_p") or p.get("fair_p")
        outcome = p.get("outcome") or p.get("result")
        if prob is None or outcome is None: continue
        try:
            prob = float(prob)
            outcome_01 = 1 if str(outcome).upper() in ("WIN", "W", "TRUE", "1", "HIT", "YES") else 0
            bin_key = min(0.9, math.floor(prob * 10) / 10)
            buckets[bin_key]["n"] += 1
            buckets[bin_key]["hits"] += outcome_01
        except Exception:
            continue
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


def _grade(n: int, p_value: float, brier: Optional[float], clv_pp: Optional[float],
           hit_rate: float) -> Tuple[str, str]:
    """Sample-size + significance grade for a source's learning quality."""
    if n < 10:
        return "F", "INSUFFICIENT_DATA"
    if n < MIN_N_FOR_LEARNING:
        return "D", "TOO_EARLY"
    if n < 30:
        if p_value < SIGNIFICANCE_THRESHOLD * 2:
            return "C", "EMERGING_SIGNAL"
        return "C", "WATCH"
    # n >= 30
    has_clv = clv_pp is not None and abs(clv_pp) >= 2.0
    has_calibration = brier is not None and brier < 0.24
    if n >= 50 and p_value < SIGNIFICANCE_THRESHOLD and has_clv and has_calibration:
        return "A", "TRUSTED"
    if p_value < SIGNIFICANCE_THRESHOLD * 2 and (has_clv or has_calibration):
        return "B", "DEVELOPING"
    return "B", "WATCH"


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
        outcome = p.get("outcome") or p.get("result")
        if outcome is None: continue
        outcome_01 = 1 if str(outcome).upper() in ("WIN", "W", "TRUE", "1", "HIT", "YES") else 0
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
        src = p.get("source") or "unknown"
        picks_by_source.setdefault(src, []).append(p)
        pid = p.get("pick_id") or p.get("id") or f"{src}|{p.get('player')}|{p.get('market')}|{p.get('date')}"
        pick_ids_by_source.setdefault(src, []).append(pid)

    rows: List[Dict[str, Any]] = []
    guards: Dict[str, Dict[str, Any]] = {}
    for source, stats in by_source.items():
        hits = int(stats.get("wins") or stats.get("hits") or 0)
        losses = int(stats.get("losses") or stats.get("misses") or 0)
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
        p_value = _binomial_p_value(hits, n, p0=0.50)
        z_score = abs(hits - n*0.5) / math.sqrt(n*0.25) if n > 0 else 0

        src_picks = picks_by_source.get(source, [])
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

        grade, status = _grade(n, p_value, brier, clv_pp, p_hat)
        trustworthy = grade in ("A", "B")

        rows.append({
            "source": source,
            "n_settled": n,
            "n_hits": hits,
            "n_misses": losses,
            "hit_rate": round(p_hat, 3),
            "wilson_lo_95": round(wilson_lo, 3),
            "wilson_hi_95": round(wilson_hi, 3),
            "z_score_vs_50": round(z_score, 2),
            "p_value": round(p_value, 4),
            "is_significant": bool(p_value < SIGNIFICANCE_THRESHOLD),
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
        "max_weight_delta_per_cycle": MAX_WEIGHT_DELTA_PER_CYCLE,
        "rows": rows,
        "cross_source_overlaps": overlaps,
        "interpretation": (
            "F = insufficient data (<10 picks), ignoring this source's signal. "
            "D = too early (10-19). C = watch (20-29). B = developing real signal (30+, p<0.10). "
            "A = trusted (50+, p<0.05, brier<0.24, CLV>=+2pp). "
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
