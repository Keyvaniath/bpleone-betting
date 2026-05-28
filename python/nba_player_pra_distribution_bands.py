"""
EdgeStat -- NBA player PRA (pts+reb+ast) distribution bands.

Pure-model (no book line). Companion to the points distribution module,
for the popular PRA combo market. Normal(projected_pra, sigma) model
from nba_player_pra_props:

  P(PRA >= line) ladder over half-point lines around the projection
  floor / median / ceiling = 15th / 50th / 85th percentile
  confident_over_line = highest .5 line with P(over) >= 0.65

Output: data/nba_player_pra_distribution_bands.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_pra_distribution_bands.json")

# z-scores for the 15th / 85th percentiles of a Normal
Z15 = 1.0364334


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


def _p_over(line: float, mu: float, sigma: float) -> float:
    """P(X >= line) for Normal(mu, sigma)."""
    if sigma <= 0: return 1.0 if mu >= line else 0.0
    z = (line - mu) / (sigma * math.sqrt(2.0))
    return max(0.0, min(1.0, 0.5 * (1.0 - math.erf(z))))


def run() -> Dict[str, Any]:
    pra = _load(os.path.join(DATA_DIR, "nba_player_pra_props.json"))

    rows: List[Dict[str, Any]] = []
    for r in (pra.get("rows") or []):
        if not isinstance(r, dict): continue
        mu = _safe(r.get("projected_pra"))
        sigma = _safe(r.get("sigma"))
        if mu <= 0 or sigma <= 0: continue

        base = round(mu)
        lines = [base - 9.5, base - 6.5, base - 3.5, base - 0.5,
                 base + 2.5, base + 5.5, base + 8.5]
        ladder = {f"over_{ln}": round(_p_over(ln, mu, sigma), 3)
                  for ln in lines if ln > 0}

        confident = 0.0
        ln = base - 12.5
        while ln <= base + 12.5:
            if ln > 0 and _p_over(ln, mu, sigma) >= 0.65:
                confident = ln
            ln += 1.0

        rows.append({
            "player": r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "projected_pra": round(mu, 1),
            "sigma": round(sigma, 2),
            "floor_pra": round(mu - Z15 * sigma, 1),
            "median_pra": round(mu, 1),
            "ceiling_pra": round(mu + Z15 * sigma, 1),
            "alt_ladder": ladder,
            "confident_over_line": confident,
            "lean": f"PRA OVER {confident}" if confident else "no confident PRA edge",
        })

    rows.sort(key=lambda r: -r["projected_pra"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "method_note": "Normal(projected_pra, sigma) PRA model from "
                       "nba_player_pra_props. P(PRA>=line) ladder, floor/median/"
                       "ceiling (15/50/85 pctile via fixed z), confident_over_line "
                       "(P>=.65). Companion to the points distribution bands.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-pra-distro] {o['n_players']} players laddered -> {OUT}")
