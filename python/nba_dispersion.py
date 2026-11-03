"""
EdgeStat -- NBA stat dispersion (2026-11-03), shared by the prop modules.

SD = a * mean^b per stat, fitted on last season's real box scores
(tools/build_nba_dispersion.py -> data/nba_dispersion.json). The modules used
to assume 22-30% of the projection, which is roughly half the real spread for
rebounds/assists and made every prop overconfident.
"""
from __future__ import annotations

import json
import math
import os
from typing import Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_FIT: Dict[str, Dict[str, float]] = {}
# Fallback = the 2026-11-03 fit, so a missing file never reverts to the old sigmas.
_DEFAULT = {"pts": (1.896, 0.46), "reb": (1.02, 0.568), "ast": (1.058, 0.526), "fg3m": (1.052, 0.508),
            "to": (1.001, 0.481), "stl": (1.013, 0.48), "blk": (1.037, 0.538), "fta": (1.435, 0.51),
            "pra": (2.347, 0.397), "pr": (2.118, 0.426), "pa": (2.013, 0.437), "ra": (1.211, 0.504)}


def _fit(stat: str):
    if not _FIT:
        try:
            with open(os.path.join(DATA_DIR, "nba_dispersion.json"), encoding="utf-8") as f:
                _FIT.update(json.load(f).get("fit") or {})
        except Exception:
            pass
    f = _FIT.get(stat)
    return (f["a"], f["b"]) if f else _DEFAULT[stat]


def sd(stat: str, mean: float) -> float:
    a, b = _fit(stat)
    return a * max(mean, 0.3) ** b


def p_at_least(stat: str, k: int, mean: float) -> float:
    """P(X >= k) for a count stat: negative binomial with the fitted variance
    (falls back to Poisson when the fit is not overdispersed)."""
    if mean <= 0:
        return 0.0 if k > 0 else 1.0
    var = sd(stat, mean) ** 2
    if var <= mean * 1.02:
        cdf = sum(math.exp(i * math.log(mean) - mean - math.lgamma(i + 1)) for i in range(k))
    else:
        r = mean * mean / (var - mean)
        p = r / (r + mean)
        cdf = sum(math.exp(math.lgamma(i + r) - math.lgamma(r) - math.lgamma(i + 1)
                           + r * math.log(p) + i * math.log(1 - p)) for i in range(k))
    return max(0.0, min(1.0, 1.0 - cdf))
