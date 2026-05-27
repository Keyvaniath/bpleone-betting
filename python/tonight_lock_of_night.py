"""
EdgeStat -- Tonight's lock of the night (single highest-conviction pick).

Single-pick selector. Combines signals from:
  - elite_alerts_board (entity-level 5+ signal alerts)
  - mlb_confluence_triple (triple-source confluences)
  - alpha_pick_of_day (highest model edge pick)
  - mlb_today_top_pitcher_props + top_batter_props (top per-prop edges)

Ranks all candidates by a composite score:
  score = signal_count * source_weight
  source_weights:
    TRIPLE_LOCK      = 5.0
    TRIPLE_STRONG    = 4.0
    MATCHUP_CONF_E   = 3.5
    ELITE_BOARD      = 3.0
    ALPHA_POD        = 2.5
    TOP_PROP         = 2.0

Single "lock" = highest composite score with explanation chain.

Output: data/tonight_lock_of_night.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_lock_of_night.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    eb = _load(os.path.join(DATA_DIR, "elite_alerts_board.json"))
    triple = _load(os.path.join(DATA_DIR, "mlb_confluence_triple.json"))
    pod = _load(os.path.join(DATA_DIR, "alpha_pick_of_day.json"))
    top_p = _load(os.path.join(DATA_DIR, "mlb_today_top_pitcher_props.json"))
    top_b = _load(os.path.join(DATA_DIR, "mlb_today_top_batter_props.json"))

    candidates: List[Dict[str, Any]] = []

    # Triples
    for t in (triple.get("triples") or []):
        if not isinstance(t, dict): continue
        weight = 5.0 if t.get("tier") == "TRIPLE_LOCK" else (
            4.0 if t.get("tier") == "TRIPLE_STRONG" else 2.0)
        candidates.append({
            "source": "MLB_CONFLUENCE_TRIPLE",
            "tier": t.get("tier"),
            "subject": t.get("matchup") or "?",
            "sport": "MLB",
            "signals": t.get("n_sources", 0),
            "weight": weight,
            "score": (t.get("n_sources", 0) or 0) * weight,
            "details": {
                "fade_pitcher": t.get("fade_pitcher"),
                "explosion_teams": t.get("explosion_teams"),
                "stack_score": t.get("stack_score"),
            },
        })

    # Elite board entries (>= 5 signals)
    for e in (eb.get("elites") or []):
        if not isinstance(e, dict): continue
        n = e.get("n_signals", 0) or 0
        if n < 5: continue
        weight = 3.0
        candidates.append({
            "source": "ELITE_BOARD",
            "tier": e.get("tier"),
            "subject": e.get("entity") or "?",
            "sport": e.get("sport"),
            "signals": n,
            "weight": weight,
            "score": n * weight,
            "details": {
                "matchup": e.get("matchup"),
                "source_synthesizer": e.get("source"),
                "extras": e.get("extras"),
            },
        })

    # Alpha pick of day
    pod_pick = pod.get("pick") or {}
    if pod_pick:
        candidates.append({
            "source": "ALPHA_POD",
            "tier": pod_pick.get("tier") or "POD",
            "subject": pod_pick.get("market") or pod_pick.get("subject") or "?",
            "sport": pod_pick.get("sport") or "MLB",
            "signals": 1,
            "weight": 2.5,
            "score": (pod_pick.get("edge_pp", 0) or 0) * 0.5,
            "details": pod_pick,
        })

    # Top pitcher / batter props
    for src, weight, subject_field in [
        (top_p, 2.0, "pitcher"),
        (top_b, 2.0, "batter"),
    ]:
        for r in (src.get("top_5") or src.get("rows") or [])[:5]:
            if not isinstance(r, dict): continue
            candidates.append({
                "source": "TOP_PROP",
                "tier": r.get("edge_class") or r.get("tier"),
                "subject": r.get(subject_field) or r.get("player") or "?",
                "sport": "MLB",
                "signals": 1,
                "weight": weight,
                "score": (r.get("edge_pp") or r.get("edge") or 0) * weight,
                "details": r,
            })

    # Pick the highest-scoring
    candidates.sort(key=lambda c: -c["score"])
    lock = candidates[0] if candidates else None

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_candidates": len(candidates),
        "lock": lock,
        "top_5_runner_ups": candidates[1:6],
        "method_note": "Composite score = signal_count * source_weight. "
                       "Weights: TRIPLE_LOCK=5.0, TRIPLE_STRONG=4.0, "
                       "ELITE_BOARD=3.0, ALPHA_POD=2.5, TOP_PROP=2.0.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    lock = o.get("lock") or {}
    print(f"[lock-of-night] {o['n_candidates']} candidates, "
          f"lock = {lock.get('subject')} ({lock.get('source')}, "
          f"score={lock.get('score')}) -> {OUT}")
