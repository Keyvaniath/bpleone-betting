"""
EdgeStat -- F1 driver podium finish (top 3) prop.

DK F1 market: 'Driver to finish on podium yes/no'. Typical pricing:
  - Top 3 drivers (Verstappen / Norris / Leclerc): -110 to +150 YES
  - Top 5: +180 to +350
  - Mid pack: +500+

Method:
  Pull qualifying probability + track-specific edge from f1_qualifying_predictor
  + f1_track_specific. P(podium) ≈ p_quali_top5 * race_pace_factor * 0.65
  (~65% of top-5 qualifiers convert to podium).

  STRONG_YES at p in [0.30, 0.48] (vs +200 book = 33.3% breakeven)

Output: data/f1_podium_finish_props.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "f1_podium_finish_props.json")


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    quali = _load(os.path.join(DATA_DIR, "f1_qualifying_predictor.json"))
    track = _load(os.path.join(DATA_DIR, "f1_track_specific.json"))

    drivers_src = quali.get("drivers") or quali.get("rows") or []
    # Track-specific adjustments (pace_factor per driver)
    track_adj = {}
    for r in (track.get("drivers") or track.get("rows") or []):
        if isinstance(r, dict):
            name = (r.get("driver") or r.get("name") or "").lower()
            if name:
                track_adj[name] = _safe(r.get("track_pace_factor"), 1.0)

    rows: List[Dict[str, Any]] = []
    for d in drivers_src:
        if not isinstance(d, dict): continue
        name = d.get("driver") or d.get("name")
        if not name: continue
        # Qualifying probability of top-5
        p_top5 = _safe(d.get("p_top5") or d.get("p_quali_top5"))
        if p_top5 <= 0:
            # Fallback: use qualifying position projection
            quali_pos = _safe(d.get("predicted_qualifying_pos") or d.get("predicted_grid_pos"), 12)
            # Convert position to top-5 prob (rough)
            if quali_pos <= 3: p_top5 = 0.75
            elif quali_pos <= 5: p_top5 = 0.55
            elif quali_pos <= 8: p_top5 = 0.30
            elif quali_pos <= 12: p_top5 = 0.12
            else: p_top5 = 0.04

        pace_factor = track_adj.get(name.lower(), 1.0)
        # ~65% of top-5 qualifiers convert to podium, adjusted by track-pace
        p_podium = p_top5 * 0.65 * pace_factor
        p_podium = max(0.005, min(0.85, p_podium))
        p_no_podium = 1 - p_podium

        edge_class = "NONE"
        best_market = None
        if 0.30 <= p_podium <= 0.48:
            edge_class = "STRONG_YES"
            best_market = {"market": "PODIUM_YES", "p": round(p_podium, 3),
                           "fair_odds": _american(p_podium)}
        elif 0.62 <= p_no_podium <= 0.78:
            edge_class = "STRONG_NO"
            best_market = {"market": "PODIUM_NO", "p": round(p_no_podium, 3),
                           "fair_odds": _american(p_no_podium)}

        rows.append({
            "driver": name,
            "team": d.get("team"),
            "p_quali_top5": round(p_top5, 3),
            "track_pace_factor": round(pace_factor, 3),
            "p_podium": round(p_podium, 3),
            "p_no_podium": round(p_no_podium, 3),
            "fair_yes": _american(p_podium),
            "fair_no": _american(p_no_podium),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["p_podium"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_drivers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(podium) = p_quali_top5 * 0.65 (top-5-to-podium conversion) "
                       "* track_pace_factor. STRONG_YES p in [0.30, 0.48] vs +200 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f1-podium] {o['n_drivers']} drivers, {o['n_strong_edges']} strong -> {OUT}")
