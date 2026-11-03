"""
EdgeStat -- risk-adjusted Sharpe ranking.

EV alone undersells low-variance plays and oversells lottery-ticket plays.
This module re-ranks tonight's best_bets by Sharpe-like ratio:
   sharpe = expected_unit_return / sqrt(variance_unit_return)
where the unit return = +b (decimal-1) if win, -1 if loss, weighted by p.

For each qualifying bet:
   p = model_prob
   b = decimal payout - 1  (real book price only; no price -> not ranked)
   expected = p*b - (1-p)*1     (per $1 staked)
   variance = (b - expected)^2 * p + (-1 - expected)^2 * (1-p)
   sharpe   = expected / sqrt(variance)  if variance > 0 else 0

Output: data/sharpe_rankings.json
  {
    "generated_at": "...",
    "n_bets": 18,
    "rankings": [
      { rank, label, ev_per_dollar, std_dev, sharpe, sharpe_tier,
        source, quality_score, model_prob, edge_pct, url_anchor }
    ]
  }

Bets are placed into tiers:
  ELITE  sharpe >= 0.20
  STRONG sharpe >= 0.10
  THIN   sharpe < 0.10 (still positive EV but high variance)
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BB_PATH = os.path.join(DATA_DIR, "best_bets.json")
OUT_PATH = os.path.join(DATA_DIR, "sharpe_rankings.json")

DEFAULT_AMERICAN = None   # 2026-11-03: no default price -- real book price or not ranked


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _b(american: int) -> float:
    return (american / 100.0) if american >= 0 else (100.0 / abs(american))


def _sharpe_for_bet(p: float, american: int) -> Dict[str, float]:
    b = _b(american)
    ev = p * b - (1 - p) * 1
    # variance of unit return given Bernoulli outcome
    var = (b - ev) ** 2 * p + (-1 - ev) ** 2 * (1 - p)
    std = math.sqrt(var) if var > 0 else 0
    sharpe = ev / std if std > 0 else 0
    return {"ev": round(ev, 4), "std": round(std, 4), "sharpe": round(sharpe, 4)}


def _tier(s: float) -> str:
    if s >= 0.20: return "elite"
    if s >= 0.10: return "strong"
    if s >= 0.04: return "solid"
    return "thin"


def run() -> Dict[str, Any]:
    bb = _load(BB_PATH).get("bets") or []
    rankings: List[Dict[str, Any]] = []
    for b in bb:
        prob = b.get("model_prob")
        if prob is None or prob <= 0.50 or prob >= 0.99:
            continue
        # FAIL CLOSED (2026-11-03): rank only at a REAL book price. This used
        # to price every bet at -110 (and SGPs at their own fair price), so the
        # Sharpe ranking scored bets against a price no book offered.
        american = b.get("book_american")
        try:
            american = int(american)
        except (TypeError, ValueError):
            continue
        if abs(american) < 100:
            continue
        s = _sharpe_for_bet(prob, american)
        rankings.append({
            "rank": b.get("rank"),
            "label": b.get("label"),
            "source": b.get("source"),
            "player": b.get("player"),
            "player_id": b.get("player_id"),
            "market": b.get("market"),
            "line": b.get("line"),
            "play": b.get("play"),
            "model_prob": prob,
            "american_price_assumed": american,
            "ev_per_dollar": s["ev"],
            "std_dev": s["std"],
            "sharpe": s["sharpe"],
            "sharpe_tier": _tier(s["sharpe"]),
            "quality_score": b.get("quality_score"),
            "edge_pct": b.get("edge_pct"),
            "stars": b.get("stars"),
            "url_anchor": b.get("url_anchor"),
        })

    rankings.sort(key=lambda r: -r["sharpe"])
    for i, r in enumerate(rankings):
        r["sharpe_rank"] = i + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_bets": len(rankings),
        "by_tier_counts": {t: sum(1 for r in rankings if r["sharpe_tier"] == t)
                            for t in ("elite", "strong", "solid", "thin")},
        "rankings": rankings,
        "note": ("Sharpe = EV per $1 / std-dev of unit outcome. ELITE >=0.20, "
                  "STRONG >=0.10, SOLID >=0.04, THIN <0.04. Re-ranks best_bets "
                  "for risk-adjusted-best plays."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_bets']} bets")
    print(f"  Tier counts: {p['by_tier_counts']}")
    print(f"  Top 5 by Sharpe:")
    for r in p["rankings"][:5]:
        print(f"    [{r['sharpe_rank']}] sharpe={r['sharpe']:.3f} ({r['sharpe_tier']}) "
                f"ev=${r['ev_per_dollar']:+.3f} std=${r['std_dev']:.3f} :: {r['label']}")
