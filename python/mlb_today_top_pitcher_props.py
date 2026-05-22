"""
EdgeStat -- MLB Today's Top Pitcher Props.

Per-pitcher aggregator: surfaces the day's top pitcher prop edges across all
pitcher-prop modules, sorted by composite conviction score.

Sources:
  - mlb_pitcher_strikeouts_props (K market)
  - mlb_pitcher_outs_props (recorded outs / IP)
  - mlb_pitcher_quality_start_props (QS yes/no)
  - mlb_pitcher_walks_props (BB market)
  - mlb_pitcher_hits_allowed_props (H allowed)
  - mlb_pitcher_er_props (earned runs allowed)
  - mlb_pitcher_win_props (pitcher win yes/no)
  - mlb_pitcher_1st_inning_er (1st-inning ER yes/no)
  - mlb_pitcher_edge_composite (edge tier)
  - mlb_pitcher_form_tracker (heating up / cooling down)
  - mlb_starter_pitch_count_alerts (RED / EMERGENCY workload)

For each starter:
  - Collect all STRONG edges across sources
  - Compute composite score = sum of (each market's edge_amount * source_weight)
  - Generate "PITCHER PLAY OF THE DAY" candidate from highest composite

Output: data/mlb_today_top_pitcher_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_top_pitcher_props.json")

SOURCE_WEIGHTS = {
    # Weight each source by historical accuracy
    "strikeouts": 1.0,
    "outs": 0.9,
    "qs": 0.85,
    "walks": 0.8,
    "hits_allowed": 0.75,
    "er": 0.8,
    "win": 0.85,
    "1st_inning_er": 0.7,
    "edge_composite": 1.1,
    "form_tracker": 0.9,
    "pitch_count": 0.7,
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


def _add_edge(by_pitcher: Dict[str, List[Dict[str, Any]]],
              pitcher: str, source: str, market: str,
              direction: str, p: float, fair_odds: int, edge_class: str):
    if not pitcher: return
    by_pitcher.setdefault(pitcher, []).append({
        "source": source,
        "market": market,
        "direction": direction,
        "p": round(p, 3),
        "fair_odds": fair_odds,
        "edge_class": edge_class,
        "weight": SOURCE_WEIGHTS.get(source, 0.7),
    })


def _extract_strong_edges(rows, source, by_pitcher):
    """Generic extractor: pulls best_market info per row when STRONG."""
    for r in (rows or []):
        if not isinstance(r, dict): continue
        ec = r.get("edge_class") or ""
        if not ec.startswith("STRONG"): continue
        bm = r.get("best_market") or {}
        if not bm: continue
        pitcher = r.get("pitcher") or r.get("name")
        market = bm.get("market") or ec
        direction = "OVER" if "OVER" in ec or "YES" in ec else (
            "UNDER" if "UNDER" in ec or "NO" in ec else "?")
        _add_edge(by_pitcher, pitcher, source, market, direction,
                  _safe(bm.get("p")), bm.get("fair_odds"), ec)


def run() -> Dict[str, Any]:
    sources = {
        "strikeouts":   _load(os.path.join(DATA_DIR, "mlb_pitcher_strikeouts_props.json")),
        "outs":         _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json")),
        "qs":           _load(os.path.join(DATA_DIR, "mlb_pitcher_quality_start_props.json")),
        "walks":        _load(os.path.join(DATA_DIR, "mlb_pitcher_walks_props.json")),
        "hits_allowed": _load(os.path.join(DATA_DIR, "mlb_pitcher_hits_allowed_props.json")),
        "er":           _load(os.path.join(DATA_DIR, "mlb_pitcher_er_props.json")),
        "win":          _load(os.path.join(DATA_DIR, "mlb_pitcher_win_props.json")),
        "1st_inning_er":_load(os.path.join(DATA_DIR, "mlb_pitcher_1st_inning_er.json")),
        "edge_composite":_load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json")),
        "form_tracker": _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json")),
        "pitch_count":  _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json")),
    }

    by_pitcher: Dict[str, List[Dict[str, Any]]] = {}

    # Standard prop modules with rows + best_market
    for src in ("strikeouts", "outs", "qs", "walks", "hits_allowed", "er",
                "win", "1st_inning_er"):
        rows = sources[src].get("rows") or []
        if not rows:
            for k in ("strong_edges", "top_25_by_p_qs", "top_25_by_xK"):
                if k in sources[src] and isinstance(sources[src][k], list):
                    rows = sources[src][k]; break
        _extract_strong_edges(rows, src, by_pitcher)

    # Edge composite — pulls tier directly
    for r in (sources["edge_composite"].get("rows") or []):
        if not isinstance(r, dict): continue
        if r.get("tier") in ("ELITE_MATCHUP", "STRONG"):
            pitcher = r.get("pitcher")
            for lean in (r.get("directional_lean") or []):
                _add_edge(by_pitcher, pitcher, "edge_composite", lean, "OVER",
                          0.60, None, "STRONG_DIR")
        elif r.get("tier") in ("BAD_SPOT", "SOFT"):
            pitcher = r.get("pitcher")
            for lean in (r.get("directional_lean") or []):
                _add_edge(by_pitcher, pitcher, "edge_composite", lean, "UNDER",
                          0.60, None, "STRONG_DIR")

    # Form tracker
    for r in (sources["form_tracker"].get("rows") or []):
        if not isinstance(r, dict): continue
        status = r.get("status")
        if status in ("HEATING_UP", "COOLING_DOWN", "HOT_K", "COLD_K"):
            pitcher = r.get("pitcher")
            direction = "OVER" if status in ("HEATING_UP", "HOT_K") else "UNDER"
            for lean in (r.get("leans") or []):
                _add_edge(by_pitcher, pitcher, "form_tracker", lean, direction,
                          0.58, None, status)

    # Pitch count
    for r in (sources["pitch_count"].get("rows") or []):
        if not isinstance(r, dict): continue
        if r.get("status") in ("RED", "EMERGENCY"):
            pitcher = r.get("pitcher")
            for lean in (r.get("leans") or []):
                _add_edge(by_pitcher, pitcher, "pitch_count", lean, "UNDER",
                          0.58, None, r["status"])

    # Compute composite per pitcher
    aggregated: List[Dict[str, Any]] = []
    for pitcher, edges in by_pitcher.items():
        # Composite score: sum of edge_pct * source_weight
        composite = 0.0
        directions_OVER = 0
        directions_UNDER = 0
        for e in edges:
            edge_amt = abs(e.get("p", 0.5) - 0.5)
            composite += edge_amt * e.get("weight", 0.7)
            if e["direction"] == "OVER": directions_OVER += 1
            elif e["direction"] == "UNDER": directions_UNDER += 1

        # Convergence: net direction
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
            "pitcher": pitcher,
            "composite_score": round(composite, 3),
            "n_strong_edges": len(edges),
            "net_direction": net_dir,
            "directions_OVER": directions_OVER,
            "directions_UNDER": directions_UNDER,
            "edges": edges,
        })

    aggregated.sort(key=lambda r: -r["composite_score"])
    top_pitcher_play = aggregated[0] if aggregated else None

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers_with_edges": len(aggregated),
        "PITCHER_PLAY_OF_THE_DAY": top_pitcher_play,
        "method_note": "Aggregates STRONG edges across 11 pitcher prop modules. "
                       "Composite = sum(edge_pct * source_weight) per starter. "
                       "Net direction = STRONG_OVER/UNDER if 2x majority OVER/UNDER, "
                       "LEAN_OVER/UNDER if simple majority, MIXED otherwise.",
        "top_15_pitchers": aggregated[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    pod = o.get("PITCHER_PLAY_OF_THE_DAY") or {}
    print(f"[top-pitcher] {o['n_pitchers_with_edges']} pitchers with edges, "
          f"PoD: {pod.get('pitcher','none')} ({pod.get('composite_score',0)}) -> {OUT}")
