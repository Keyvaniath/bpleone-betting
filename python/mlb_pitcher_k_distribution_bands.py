"""
EdgeStat -- MLB pitcher strikeout distribution bands.

Pure-model (no book line). Takes each starter's projected K mean (from the
matchup projection, else the opp/park-adjusted expected_k) and builds the
full alt-line probability ladder via a Poisson count model:

  P(K >= n) for n = 4..10   -> price every alt K line at once
  floor / median / ceiling  -> 25th / 50th / 85th pctile of the K distro
  coin_flip_line            -> highest n with P(K>=n) >= 0.50
  confident_line            -> highest n with P(K>=n) >= 0.65

Surfaces the sharpest alt-K spots independent of what the book hangs.

Output: data/mlb_pitcher_k_distribution_bands.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_k_distribution_bands.json")

ALT_LINES = [4, 5, 6, 7, 8, 9, 10]


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


def _pmf(lam: float, k: int) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def _ge(lam: float, n: int) -> float:
    """P(K >= n) for Poisson(lam)."""
    if n <= 0: return 1.0
    cdf_below = sum(_pmf(lam, k) for k in range(0, n))
    return max(0.0, min(1.0, 1.0 - cdf_below))


def _pctile(lam: float, q: float) -> int:
    """Smallest k with CDF(k) >= q."""
    cum = 0.0
    for k in range(0, 25):
        cum += _pmf(lam, k)
        if cum >= q:
            return k
    return 24


def run() -> Dict[str, Any]:
    matchup = _load(os.path.join(DATA_DIR, "mlb_pitcher_matchup_projection.json"))
    kprop = _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json"))

    kprop_idx = {_norm(r.get("pitcher")): r
                 for r in (kprop.get("rows") or []) if isinstance(r, dict)}

    rows: List[Dict[str, Any]] = []
    seen = set()
    # Prefer matchup projection's proj_k (lineup-adjusted), fall back to props.
    sources = list(matchup.get("rows") or []) + list(kprop.get("rows") or [])
    for r in sources:
        if not isinstance(r, dict): continue
        key = _norm(r.get("pitcher"))
        if not key or key in seen: continue

        lam = _safe(r.get("proj_k"))
        if lam <= 0:
            lam = _safe(kprop_idx.get(key, {}).get("expected_k"))
        if lam <= 0: continue
        seen.add(key)

        ladder = {f"p_{n}plus": round(_ge(lam, n), 3) for n in ALT_LINES}

        coin_flip = 0
        confident = 0
        for n in ALT_LINES:
            p = _ge(lam, n)
            if p >= 0.50: coin_flip = n
            if p >= 0.65: confident = n

        rows.append({
            "pitcher": r.get("pitcher"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "proj_k_mean": round(lam, 2),
            "floor_k": _pctile(lam, 0.25),
            "median_k": _pctile(lam, 0.50),
            "ceiling_k": _pctile(lam, 0.85),
            "alt_ladder": ladder,
            "coin_flip_line": coin_flip,
            "confident_line": confident,
            "lean": (
                f"K OVER {coin_flip - 0.5}" if coin_flip else "no K edge"
            ),
        })

    rows.sort(key=lambda r: -r["proj_k_mean"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_with_confident_8plus": sum(1 for r in rows if r["confident_line"] >= 8),
        "alt_lines": ALT_LINES,
        "method_note": "Poisson(lambda=proj_k) strikeout count model. Prefers "
                       "matchup proj_k (lineup-adjusted), falls back to "
                       "opp/park-adj expected_k. Emits P(K>=n) ladder for "
                       "n=4..10, floor/median/ceiling (25/50/85 pctile), "
                       "coin_flip_line (P>=.50) and confident_line (P>=.65).",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-k-distro] {o['n_pitchers']} pitchers laddered "
          f"({o['n_with_confident_8plus']} with confident 8+ K) -> {OUT}")
