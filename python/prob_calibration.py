"""
EdgeStat -- shared probability calibration & curation (real-outcome guards).

Any board that surfaces picks (high_confidence_board, props_parlay_builder, ...)
should route its probabilities through here so the displayed numbers are honest.
Both guards learn from the SAME settled pick ledger (all_picks_ledger.json) the
rest of the brain trains on -- no synthetic priors -- so the board moves
automatically as outcomes settle.

Guard 1 -- proven_negative_families():
    Market families that have LOST money over a real sample. A professional desk
    never publishes a -EV market no matter how high the raw hit rate -- e.g.
    k_1plus hits 60% but is priced so short it bled -189u over 1,349 settled
    bets. Boards HARD-EXCLUDE these.

Guard 2 -- empirical_calibrate(raw_prob, market):
    Bayesian-blend the model's raw probability toward the family's REALIZED hit
    rate from the ledger:

        cal = (PRIOR_K * raw + n * realized) / (PRIOR_K + n)      [n >= CAL_MIN_N]

    Families with a lot of settled data pull toward reality; thinly-sampled
    families keep the model's number. This crushes the overconfident rare-event
    OVERs (model says 55% a batter homers; realized 15.8%) while leaving the
    well-calibrated UNDERs (realized ~82-96%) essentially intact -- and even
    nudging an under-confident family UP toward its realized rate.

This is empirical recalibration on real historical outcomes, not a generic
shrink toward a flat baseline (which would wrongly punish the proven-profitable
under families). Family-level is a first-order calibration; per-probability-
bucket calibration is the next refinement once families carry more samples.
"""
from __future__ import annotations

import os
import re
import json
from typing import Any, Dict, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")

CURATE_MIN_N = 25       # need a real sample before calling a family a loser
CURATE_MAX_NET = -5.0   # lost > 5u over that sample => proven -EV, do not publish
CAL_MIN_N = 30          # settled bets required before empirical calibration kicks in
PRIOR_K = 25.0          # Bayesian prior strength: the model's raw prob counts as
                        # PRIOR_K pseudo-bets, so realized data outweighs it past ~n=25


def _load_ledger() -> Dict[str, Any]:
    if not os.path.exists(LEDGER):
        return {}
    try:
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def market_family(market) -> str:
    """Line-stripped family so HRR_under_3.5 / HRR_under_4.5 collapse. Mirrors
    all_picks_tracker._market_family so the key matches the ledger's families."""
    if not market:
        return "unknown"
    m = re.sub(r"_(?:over|under)?_?-?\d+(?:\.\d+)?$", "", str(market))
    m = re.sub(r"_(over|under)$", r"_\1", m)
    return m.lower() or "unknown"


def canon_market_family(market) -> str:
    """Canonical family (pools duplicate-named bets: 1_plus_hr / to_hit_hr_yes /
    pp_batter_home_runs -> mlb_hr_0.5_over) via market_taxonomy when recognized,
    else the line-stripped family."""
    try:
        from market_taxonomy import canonical_market
        c = canonical_market(market)
        if c:
            return c
    except Exception:
        pass
    return market_family(market)


_STATS_CACHE: Optional[Dict[str, Tuple[int, float, float]]] = None
_NEG_CACHE: Optional[set] = None


def _family_stats() -> Dict[str, Tuple[int, float, float]]:
    """{family_key: (n_settled, hit_rate, net_units)} merged from the ledger's
    by_canonical AND by_market_family blocks, so a lookup by either key hits."""
    global _STATS_CACHE
    if _STATS_CACHE is not None:
        return _STATS_CACHE
    d = _load_ledger()
    out: Dict[str, Tuple[int, float, float]] = {}
    # canonical first, then family -- so a family key present in both keeps the
    # (line-stripped) family aggregate, which is the coarser, better-sampled view.
    for block in ("by_canonical", "by_market_family"):
        for fam, v in (d.get(block) or {}).items():
            wins = v.get("wins") or 0
            losses = v.get("losses") or 0
            n = wins + losses
            if n <= 0:
                continue
            hr = v.get("hit_rate")
            if hr is None:
                hr = wins / n
            out[fam] = (n, float(hr), float(v.get("net_units") or 0.0))
    _STATS_CACHE = out
    return out


def proven_negative_families() -> set:
    """Families PROVEN to lose money over a real sample (n>=CURATE_MIN_N and
    net_units<=CURATE_MAX_NET). Boards hard-exclude these."""
    global _NEG_CACHE
    if _NEG_CACHE is not None:
        return _NEG_CACHE
    out = set()
    for fam, (n, hr, net) in _family_stats().items():
        if n >= CURATE_MIN_N and net <= CURATE_MAX_NET:
            out.add(fam)
    _NEG_CACHE = out
    return out


def is_proven_negative(market) -> bool:
    """True if this market's family (canonical OR line-stripped) is a proven loser."""
    neg = proven_negative_families()
    if not neg:
        return False
    return canon_market_family(market) in neg or market_family(market) in neg


def empirical_calibrate(raw_prob, market) -> Tuple[Optional[float], Dict[str, Any]]:
    """Bayesian-blend raw_prob toward the family's realized hit rate.

    Returns (calibrated_prob, meta). meta['method'] is:
      'empirical'  -- blended toward realized rate over n>=CAL_MIN_N settled bets
      'model_only' -- family has too little settled history; raw prob unchanged
    """
    if raw_prob is None:
        return None, {"method": "none"}
    try:
        raw = float(raw_prob)
    except (TypeError, ValueError):
        return None, {"method": "none"}
    stats = _family_stats()
    # prefer the canonical family (better-pooled), then the line-stripped family
    for key in (canon_market_family(market), market_family(market)):
        s = stats.get(key)
        if s and s[0] >= CAL_MIN_N:
            n, realized, _net = s
            cal = (PRIOR_K * raw + n * realized) / (PRIOR_K + n)
            cal = max(0.01, min(0.99, cal))
            return cal, {
                "method": "empirical", "family": key, "n": n,
                "realized": round(realized, 4), "raw": round(raw, 4),
                "shift": round(cal - raw, 4),
            }
    return max(0.01, min(0.99, raw)), {"method": "model_only", "raw": round(raw, 4)}


def prob_to_american(p) -> Optional[int]:
    """Fair American odds implied by a probability (no margin)."""
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return -int(round(100 * p / (1 - p)))
    return int(round(100 * (1 - p) / p))


_OVERCONF_CACHE: Optional[set] = None
OVERCONF_MIN_GAP = 0.12   # avg predicted exceeds realized by >=12pp => model prob is wrong
OVERCONF_MIN_N = 30       # over a real sample


def overconfident_families(min_gap: float = OVERCONF_MIN_GAP, min_n: int = OVERCONF_MIN_N) -> set:
    """Families where the model's AVERAGE PREDICTED probability exceeds the
    realized hit rate by >= min_gap over >= min_n settled bets (computed from the
    ledger picks[]). Here the model's probability itself is wrong, so ANY claimed
    edge is fake regardless of the book line -- model-edge boards (best_bets, etc.)
    must not surface these.

    This is NARROWER than proven_negative_families(): a family can lose money at
    fair pricing yet have a correct probability (k_1plus hits 60% as predicted but
    is priced too short). Such families are NOT flagged here, because at a soft
    book line they can still be +EV. Only provably-overconfident families are.
    """
    global _OVERCONF_CACHE
    if _OVERCONF_CACHE is not None:
        return _OVERCONF_CACHE
    d = _load_ledger()
    agg: Dict[str, Dict[str, float]] = {}
    for p in (d.get("picks") or []):
        if p.get("result") not in ("won", "lost"):
            continue
        fam = canon_market_family(p.get("market"))
        pred = p.get("p_predicted")
        if pred is None:
            pred = p.get("prob")
        try:
            pred = float(pred)
        except (TypeError, ValueError):
            pred = None
        a = agg.setdefault(fam, {"n": 0, "wins": 0, "ps": 0.0, "pn": 0})
        a["n"] += 1
        a["wins"] += 1 if p.get("result") == "won" else 0
        if pred is not None:
            a["ps"] += pred
            a["pn"] += 1
    out = set()
    for fam, a in agg.items():
        if a["n"] >= min_n and a["pn"] > 0:
            if (a["ps"] / a["pn"]) - (a["wins"] / a["n"]) >= min_gap:
                out.add(fam)
    _OVERCONF_CACHE = out
    return out


def is_overconfident(market) -> bool:
    """True if this market's family is provably overconfident (fake edge at any line)."""
    oc = overconfident_families()
    if not oc:
        return False
    return canon_market_family(market) in oc or market_family(market) in oc


def reset_caches() -> None:
    """Drop memoized ledger reads (after the ledger is regenerated in-process)."""
    global _STATS_CACHE, _NEG_CACHE, _OVERCONF_CACHE
    _STATS_CACHE = None
    _NEG_CACHE = None
    _OVERCONF_CACHE = None


if __name__ == "__main__":
    neg = proven_negative_families()
    print(f"[prob_calibration] {len(neg)} proven-negative families excluded:")
    for f in sorted(neg):
        print(f"   - {f}")
    print("\nSample calibrations (raw 0.70 in each family):")
    for mkt in ("to_hit_hr_yes", "HRR_under_4.5", "QUALITY_START_NO", "k_1plus_yes"):
        cal, meta = empirical_calibrate(0.70, mkt)
        tag = f"{meta['method']}"
        if meta["method"] == "empirical":
            tag += f" n={meta['n']} realized={meta['realized']}"
        print(f"   {mkt:20s} 0.70 -> {cal:.3f}  ({tag})")
