"""
EdgeStat -- 'Today's Top Plays' aggregator.

Reads all of today's artifacts (today.json, props.json, parlays.json,
pickem.json) and surfaces the top-N best opportunities across every market,
sorted by a quality score that balances:

  - Model conviction (model_prob)
  - Edge magnitude (capped to avoid pre-calibration noise dominating)
  - Sample-size confidence
  - PP advantage when applicable

Writes data/top_plays.json -- the dashboard and brief consume this.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "top_plays.json")


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _quality_score(prob: float, edge: float, low_conf: bool = False) -> float:
    """Score balances conviction and edge while penalizing pre-calibration noise.

    A 60% model prob with +5% edge scores higher than 75% model prob with +35%
    edge (the latter is likely phantom noise).
    """
    if low_conf:
        return 0
    # Cap edge at 15 -- anything higher likely pre-calibration noise
    edge_capped = max(0, min(edge, 15))
    # Distance-from-coin-flip term: rewards both very-confident and confidently-NO
    conviction = max(prob, 1 - prob)
    return round(conviction * 100 + edge_capped * 2, 2)


def collect_top_plays(n: int = 12) -> Dict[str, Any]:
    today = _load("today.json")
    props = _load("props.json")
    parlays = _load("parlays.json")
    pickem = _load("pickem.json")

    plays: List[Dict[str, Any]] = []

    # 1. Game-line recommendations from today.json
    for g in today.get("games", []):
        for r in g.get("recommendations", []) or []:
            edge = r.get("edge_pct") or 0
            if edge < 2:
                continue
            prob = r.get("model_prob") or 0.5
            plays.append({
                "kind": "game_line",
                "book": (g.get("market") or {}).get("book", "draftkings"),
                "matchup": g.get("matchup"),
                "label": r.get("label"),
                "market_price": r.get("market_price"),
                "model_prob": prob,
                "edge_pct": edge,
                "quality_score": _quality_score(prob, edge, edge >= 25),
                "is_precal": edge >= 15,
                "kelly_units": r.get("kelly_units"),
            })

    # 2. DraftKings props from props.json
    for r in (props.get("top_edges") or []):
        edge = r.get("best_edge_pct") or 0
        if edge < 2 or r.get("play") == "SKIP":
            continue
        prob_over = r.get("model_prob_over") or 0.5
        prob = prob_over if r.get("play") == "OVER" else 1 - prob_over
        plays.append({
            "kind": "prop_dk",
            "book": "draftkings",
            "matchup": r.get("matchup"),
            "player": r.get("player"),
            "market": r.get("market"),
            "side": r.get("play"),
            "line": r.get("line"),
            "market_price": r.get("dk_over") if r.get("play") == "OVER" else r.get("dk_under"),
            "model_prob": prob,
            "model_projection": r.get("model_projection"),
            "projection_vs_line": r.get("projection_vs_line"),
            "edge_pct": edge,
            "quality_score": _quality_score(prob, edge, r.get("low_confidence", False)),
            "is_precal": edge >= 15,
        })

    # 3. Top parlays (cap to top 5 to avoid spamming)
    for c in (parlays.get("parlays") or [])[:5]:
        edge = c.get("edge_pct") or 0
        if edge < 5:
            continue
        prob = c.get("parlay_prob") or 0
        plays.append({
            "kind": "parlay",
            "book": "draftkings",
            "matchup": " + ".join(l.get("label", "?")[:30] for l in c.get("legs", [])[:3]),
            "label": f"{c.get('n_legs')}-leg parlay",
            "market_price": c.get("parlay_price"),
            "model_prob": prob,
            "edge_pct": edge,
            "quality_score": _quality_score(prob, edge),
            "is_precal": edge >= 30,    # parlays compound noise
            "sgp": c.get("sgp", False),
        })

    # 4. PrizePicks softer-than-DK opportunities
    for p in (pickem.get("props") or []):
        if not p.get("pp_advantage"):
            continue
        best_prob = max(p.get("model_prob_over") or 0.5, p.get("model_prob_under") or 0.5)
        if best_prob < 0.6:    # PP power-play breakeven floor
            continue
        plays.append({
            "kind": "prop_pp",
            "book": "prizepicks",
            "matchup": "",
            "player": p.get("player"),
            "market": p.get("market"),
            "stat_type": p.get("stat_type"),
            "side": p.get("pp_softer_for"),
            "pp_line": p.get("pp_line"),
            "dk_line": p.get("dk_line"),
            "delta": p.get("delta"),
            "model_prob": best_prob,
            "quality_score": _quality_score(best_prob, p.get("pp_advantage", 0) * 5),
        })

    plays.sort(key=lambda p: p.get("quality_score", 0), reverse=True)
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_evaluated": len(plays),
        "plays": plays[:n],
    }


def write_top_plays(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote top_plays -> {path}")
    print(f"  Total plays evaluated: {payload.get('total_evaluated', 0)}")
    print(f"  Top {len(payload.get('plays', []))} surfaced")
    for p in payload.get("plays", [])[:5]:
        precal = " (pre-cal)" if p.get("is_precal") else ""
        target = p.get("player") or p.get("matchup", "?")
        print(f"  {p['kind']:9} {p.get('book',''):10} {target[:30]:30} | "
              f"score {p.get('quality_score')} | "
              f"edge {p.get('edge_pct') and ('+' + str(p['edge_pct']) + '%')}{precal}")


if __name__ == "__main__":
    write_top_plays(collect_top_plays())
