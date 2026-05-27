"""
EdgeStat -- NHL grinder skater SGP builder.

For defensive-style skaters (high hits/blocks volume), builds the
"grinder SGP":
  - Hits+Blocks OVER (signaled)
  - 3+ Hits YES (p >= 40%)
  - 4+ Hits YES (p >= 25%)
  - Blocks alt YES (signaled)

Apply 1.10x correlation boost. Useful for plus-payout defensive prop
parlays.

Output: data/nhl_grinder_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_grinder_sgp_builder.json")


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


def _is_over(ec: str) -> bool:
    return "OVER" in (ec or "").upper()


def run() -> Dict[str, Any]:
    hits_blocks = _load(os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json"))
    hits_3 = _load(os.path.join(DATA_DIR, "nhl_skater_3plus_hits.json"))
    hits_4 = _load(os.path.join(DATA_DIR, "nhl_skater_4plus_hits.json"))
    blocks_alt = _load(os.path.join(DATA_DIR, "nhl_skater_blocks_alt.json"))

    hb_idx = {_norm(r.get("player") or r.get("skater")): r
              for r in (hits_blocks.get("rows") or []) if isinstance(r, dict)}

    h3_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (hits_3.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in h3_idx:
                    h3_idx[key] = _safe(r.get("p_3plus_hits") or r.get("p"))

    h4_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges", "top_15_by_p"):
        for r in (hits_4.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in h4_idx:
                    h4_idx[key] = _safe(r.get("p_4plus_hits") or r.get("p"))

    blocks_idx: Dict[str, Dict[str, Any]] = {}
    for k in ("rows", "strong_edges"):
        for r in (blocks_alt.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or r.get("skater") or "")
                if key and key not in blocks_idx:
                    blocks_idx[key] = r

    all_skaters = set(hb_idx) | set(h3_idx) | set(h4_idx) | set(blocks_idx)

    parlays: List[Dict[str, Any]] = []
    for name in all_skaters:
        hb_data = hb_idx.get(name, {})
        h3_p = h3_idx.get(name, 0)
        h4_p = h4_idx.get(name, 0)
        bl_data = blocks_idx.get(name, {})

        legs: List[Dict[str, Any]] = []

        hb_ec = (hb_data.get("edge_class") or "").upper()
        if "OVER" in hb_ec:
            legs.append({"market": "Hits+Blocks OVER", "p": 0.55})

        if h3_p >= 0.40:
            legs.append({"market": "3+ Hits YES", "p": round(h3_p, 3)})

        if h4_p >= 0.25:
            legs.append({"market": "4+ Hits YES", "p": round(h4_p, 3)})

        bl_ec = (bl_data.get("edge_class") or "").upper()
        if "STRONG_ALT" in bl_ec or "OVER" in bl_ec:
            legs.append({"market": "Blocks Alt YES", "p": 0.52})

        if len(legs) < 2: continue

        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        parlay_p_corr = min(parlay_p_naive * 1.10, 0.99)

        skater = (hb_data.get("player") or hb_data.get("skater")
                  or bl_data.get("player") or name.title())

        parlays.append({
            "skater": skater,
            "team": hb_data.get("team") or bl_data.get("team"),
            "matchup": hb_data.get("matchup") or bl_data.get("matchup"),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "NHL grinder defensive-skater SGP. Hits+Blocks OVER + "
                       "3+ Hits (p>=40%) + 4+ Hits (p>=25%) + Blocks alt. "
                       "1.10x correlation boost. Plus-payout defensive parlay.",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-grinder-sgp] {o['n_parlays']} grinder SGP builds -> {OUT}")
