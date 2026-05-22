"""
EdgeStat -- MLB Today's Top Batter Props.

Companion to mlb_today_top_pitcher_props.py — aggregates batter prop edges
across all batter modules into a single ranked list.

Sources:
  - mlb_to_record_hit_yn (1+ hit yes/no)
  - mlb_to_hit_hr_yn (HR yes/no)
  - mlb_to_score_run_yn (run scored)
  - mlb_total_bases_props (TB)
  - mlb_doubles_props (XBH 1+)
  - mlb_batter_rbi_props (1+ RBI)
  - mlb_batter_2plus_hits_props (2+ hits)
  - mlb_batter_3plus_tb_props (3+ TB power)
  - mlb_hrr_props (Hit-Run-RBI parlay)
  - mlb_batter_walks_props (1+ walk)
  - mlb_batter_strikeout_props (1+ K)

Per batter:
  - Collect STRONG edges
  - Composite score = sum(edge_amt * source_weight)
  - "BATTER PLAY OF THE DAY" = highest composite

Output: data/mlb_today_top_batter_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_top_batter_props.json")


SOURCE_WEIGHTS = {
    "hit_yn": 1.0,        # Most reliable historically
    "hr_yn": 0.95,
    "rbi": 0.95,
    "2plus_hits": 1.05,
    "3plus_tb": 0.9,
    "tb": 1.0,
    "doubles_xbh": 0.85,
    "run_yn": 0.8,
    "hrr": 0.75,
    "walks": 0.75,
    "strikeouts": 0.7,
}


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


def _add_edge(by_batter: Dict[str, List[Dict[str, Any]]],
              batter: str, source: str, market: str,
              direction: str, p: float, fair_odds: int, edge_class: str):
    if not batter: return
    by_batter.setdefault(batter, []).append({
        "source": source,
        "market": market,
        "direction": direction,
        "p": round(p, 3),
        "fair_odds": fair_odds,
        "edge_class": edge_class,
        "weight": SOURCE_WEIGHTS.get(source, 0.7),
    })


def _extract_strong(rows, source, by_batter):
    for r in (rows or []):
        if not isinstance(r, dict): continue
        ec = r.get("edge_class") or ""
        if not ec.startswith("STRONG"): continue
        bm = r.get("best_market") or {}
        if not bm: continue
        batter = r.get("batter") or r.get("name") or r.get("player")
        market = bm.get("market") or ec
        direction = "OVER" if "OVER" in ec or "YES" in ec else (
            "UNDER" if "UNDER" in ec or "NO" in ec else "?")
        _add_edge(by_batter, batter, source, market, direction,
                  _safe(bm.get("p")), bm.get("fair_odds"), ec)


def run() -> Dict[str, Any]:
    sources = {
        "hit_yn":       _load(os.path.join(DATA_DIR, "mlb_to_record_hit_yn.json")),
        "hr_yn":        _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json")),
        "rbi":          _load(os.path.join(DATA_DIR, "mlb_batter_rbi_props.json")),
        "2plus_hits":   _load(os.path.join(DATA_DIR, "mlb_batter_2plus_hits_props.json")),
        "3plus_tb":     _load(os.path.join(DATA_DIR, "mlb_batter_3plus_tb_props.json")),
        "tb":           _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json")),
        "doubles_xbh":  _load(os.path.join(DATA_DIR, "mlb_doubles_props.json")),
        "run_yn":       _load(os.path.join(DATA_DIR, "mlb_to_score_run_yn.json")),
        "hrr":          _load(os.path.join(DATA_DIR, "mlb_hrr_props.json")),
        "walks":        _load(os.path.join(DATA_DIR, "mlb_batter_walks_props.json")),
        "strikeouts":   _load(os.path.join(DATA_DIR, "mlb_batter_strikeout_props.json")),
    }

    by_batter: Dict[str, List[Dict[str, Any]]] = {}

    for src, data in sources.items():
        rows = data.get("rows") or data.get("strong_edges") or []
        if not rows:
            for k in ("top_25_by_p_hit", "top_25_by_p_hr", "top_25_by_p_rbi",
                      "top_25_by_p_2plus", "top_25_by_p_tb3", "top_25_by_xTB",
                      "top_25_by_p_scores", "top_25_by_xHRR", "top_25_by_xXBH"):
                if k in data and isinstance(data[k], list):
                    rows = data[k]; break
        _extract_strong(rows, src, by_batter)

    aggregated: List[Dict[str, Any]] = []
    for batter, edges in by_batter.items():
        composite = 0.0
        directions_OVER = 0
        directions_UNDER = 0
        for e in edges:
            edge_amt = abs(e.get("p", 0.5) - 0.5)
            composite += edge_amt * e.get("weight", 0.7)
            if e["direction"] == "OVER": directions_OVER += 1
            elif e["direction"] == "UNDER": directions_UNDER += 1

        if directions_OVER > directions_UNDER * 2:
            net_dir = "STRONG_OVER"
        elif directions_UNDER > directions_OVER * 2:
            net_dir = "STRONG_UNDER"
        elif directions_OVER > directions_UNDER:
            net_dir = "LEAN_OVER"
        elif directions_UNDER > directions_OVER:
            net_dir = "LEAN_UNDER"
        else:
            net_dir = "MIXED"

        aggregated.append({
            "batter": batter,
            "composite_score": round(composite, 3),
            "n_strong_edges": len(edges),
            "net_direction": net_dir,
            "directions_OVER": directions_OVER,
            "directions_UNDER": directions_UNDER,
            "edges": edges,
        })

    aggregated.sort(key=lambda r: -r["composite_score"])
    top_play = aggregated[0] if aggregated else None

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters_with_edges": len(aggregated),
        "BATTER_PLAY_OF_THE_DAY": top_play,
        "method_note": "Aggregates STRONG edges across 11 batter prop modules. "
                       "Composite = sum(edge_pct * source_weight) per batter. "
                       "STRONG_OVER/UNDER if 2x majority direction, LEAN otherwise.",
        "top_25_batters": aggregated[:25],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    pod = o.get("BATTER_PLAY_OF_THE_DAY") or {}
    print(f"[top-batter] {o['n_batters_with_edges']} batters with edges, "
          f"PoD: {pod.get('batter','none')} ({pod.get('composite_score',0)}) -> {OUT}")
