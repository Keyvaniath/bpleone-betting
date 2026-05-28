"""
EdgeStat -- MLB pitcher same-game (SGP) stack builder.

Pure-model (no book line). Builds a correlation-aware same-pitcher stack
from the projection + K-distribution feeds. A pitcher's own props are
strongly POSITIVELY correlated (one dominant outing drives K, outs, QS
and a low ER together), so a naive independent parlay UNDER-prices the
true joint. We pull the joint up toward the weakest leg:

  naive_joint      = product(leg_probs)         (independence assumption)
  correlated_joint = naive + RHO*(min_leg - naive)   RHO=0.45 (same-game)
  fair_american    from correlated_joint

Legs considered (kept only if individually >= 0.45):
  K OVER (confident_line-0.5) · Quality Start YES · Outs OVER 17.5

Output: data/mlb_pitcher_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_sgp_builder.json")

RHO = 0.45            # same-game positive-correlation pull
MIN_LEG_PROB = 0.45   # don't stack a leg worse than this


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _american(p: float) -> int:
    p = max(0.01, min(0.99, p))
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _pois_le(lam: float, n: int) -> float:
    """P(X <= n) for Poisson(lam)."""
    if lam <= 0: return 1.0
    return max(0.0, min(1.0, sum(
        math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))
        for k in range(0, n + 1))))


def run() -> Dict[str, Any]:
    proj = _load(os.path.join(DATA_DIR, "mlb_pitcher_matchup_projection.json"))
    kdist = _load(os.path.join(DATA_DIR, "mlb_pitcher_k_distribution_bands.json"))

    proj_idx = {_norm(r.get("pitcher")): r
                for r in (proj.get("rows") or []) if isinstance(r, dict)}
    kdist_idx = {_norm(r.get("pitcher")): r
                 for r in (kdist.get("rows") or []) if isinstance(r, dict)}

    rows: List[Dict[str, Any]] = []
    for name, k in kdist_idx.items():
        p = proj_idx.get(name, {})
        pitcher = k.get("pitcher") or p.get("pitcher") or name.title()
        matchup = k.get("matchup") or p.get("matchup") or "?"
        team = k.get("team") or p.get("team")

        legs: List[Dict[str, Any]] = []

        # K leg from the distribution ladder at the confident line
        conf_line = int(_safe(k.get("confident_line")))
        ladder = k.get("alt_ladder") if isinstance(k.get("alt_ladder"), dict) else {}
        if conf_line >= 4:
            k_prob = _safe(ladder.get(f"p_{conf_line}plus"))
            if k_prob >= MIN_LEG_PROB:
                legs.append({"market": f"K OVER {conf_line - 0.5}",
                             "prob": round(k_prob, 3)})

        # ER-under leg from projected ER (Poisson). Low projected ER on a
        # sharp arm makes this a strong, positively-correlated leg.
        proj_er = _safe(p.get("proj_er"))
        if proj_er > 0:
            er_prob = _pois_le(proj_er, 3)   # P(ER <= 3) -> ER UNDER 3.5
            if er_prob >= MIN_LEG_PROB:
                legs.append({"market": "ER UNDER 3.5", "prob": round(er_prob, 3)})

        # Outs leg (P >= 5.0 IP -> Outs OVER 14.5) from projected innings
        proj_ip = _safe(p.get("proj_ip"))
        if proj_ip >= 4.8:
            outs_prob = max(0.2, min(0.85, 0.55 + (proj_ip - 5.0) * 0.22))
            if outs_prob >= MIN_LEG_PROB:
                legs.append({"market": "Outs OVER 14.5", "prob": round(outs_prob, 3)})

        # Quality-start leg (only if the feed's p_qs is actually strong)
        p_qs = _safe(p.get("p_quality_start"))
        if p_qs >= MIN_LEG_PROB:
            legs.append({"market": "Quality Start YES", "prob": round(p_qs, 3)})

        if len(legs) < 2:
            continue

        probs = [l["prob"] for l in legs]
        naive = 1.0
        for pr in probs:
            naive *= pr
        min_leg = min(probs)
        correlated = naive + RHO * (min_leg - naive)
        correlated = max(0.0, min(0.99, correlated))
        boost_pct = round((correlated / naive - 1.0) * 100, 1) if naive > 0 else 0.0

        if correlated >= 0.45:
            tier = "PRIME_STACK"
        elif correlated >= 0.32:
            tier = "STRONG_STACK"
        elif correlated >= 0.22:
            tier = "VALUE_STACK"
        else:
            tier = "LONGSHOT_STACK"

        rows.append({
            "pitcher": pitcher,
            "team": team,
            "matchup": matchup,
            "n_legs": len(legs),
            "legs": legs,
            "naive_joint": round(naive, 3),
            "correlated_joint": round(correlated, 3),
            "correlation_boost_pct": boost_pct,
            "fair_american": _american(correlated),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["correlated_joint"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_stacks": len(rows),
        "n_prime": sum(1 for r in rows if r["tier"] == "PRIME_STACK"),
        "rho": RHO,
        "method_note": "Pitcher same-game stack. Legs (K OVER confident line, "
                       "ER UNDER 3.5 via Poisson(proj_er), Outs OVER 14.5, "
                       "Quality Start YES) kept if each >= 0.45. naive_joint="
                       "product; correlated_joint=naive+RHO*(min_leg-naive), "
                       "RHO=0.45 captures same-game positive correlation (naive "
                       "parlay under-prices these). Tiers PRIME>=.45, STRONG>=.32, "
                       "VALUE>=.22.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-pitcher-sgp] {o['n_stacks']} stacks built "
          f"({o['n_prime']} PRIME) -> {OUT}")
