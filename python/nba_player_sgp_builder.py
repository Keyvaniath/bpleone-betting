"""
EdgeStat -- NBA player same-game parlay (SGP) builder.

For each NBA player with confluence_score >= 5 (STRONG+), builds the
recommended single-player SGP from their OVER signals:
  - PTS OVER (if signaled)
  - REB OVER (if signaled)
  - AST OVER (if signaled)
  - 3PM OVER (if signaled)
  - PRA OVER (if signaled)
  - 30+ PTS YES (if p_30 >= 0.40)
  - DD YES (if p_dd >= 0.45)

Correlated SGP often gets boosted odds because legs are NOT independent
(if you score 30 you likely hit PTS OVER + PRA OVER + 30+ PTS). Apply
correlation discount of 0.85 to estimated parlay_p.

Output: data/nba_player_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_sgp_builder.json")


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
    confluence = _load(os.path.join(DATA_DIR, "nba_player_confluence_score.json"))
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    reb = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    ast = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    threes = _load(os.path.join(DATA_DIR, "nba_player_threes_props.json"))
    pra = _load(os.path.join(DATA_DIR, "nba_player_pra_props.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))
    dd = _load(os.path.join(DATA_DIR, "nba_double_double_props.json"))

    # Build idx by player
    def _idx(src):
        return {_norm(r.get("player")): r for r in (src.get("rows") or []) if isinstance(r, dict)}

    pts_idx = _idx(pts)
    reb_idx = _idx(reb)
    ast_idx = _idx(ast)
    threes_idx = _idx(threes)
    pra_idx = _idx(pra)

    pts30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts30_idx:
                    pts30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    dd_idx = {_norm(r.get("player")): r for r in (dd.get("rows") or []) if isinstance(r, dict)}

    parlays: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 5: continue

        player = r.get("player")
        name = _norm(player)
        legs: List[Dict[str, Any]] = []

        for mkt_name, idx, baseline_p in [
            ("PTS OVER", pts_idx, 0.55),
            ("REB OVER", reb_idx, 0.54),
            ("AST OVER", ast_idx, 0.54),
            ("3PM OVER", threes_idx, 0.53),
            ("PRA OVER", pra_idx, 0.55),
        ]:
            row = idx.get(name, {})
            if _is_over(row.get("edge_class") or ""):
                legs.append({
                    "market": mkt_name,
                    "p": baseline_p,
                })

        p_30 = pts30_idx.get(name, 0)
        if p_30 >= 0.40:
            legs.append({
                "market": "30+ PTS YES",
                "p": round(p_30, 3),
            })

        dd_data = dd_idx.get(name, {})
        p_dd = _safe(dd_data.get("p_dd") or dd_data.get("p"))
        if p_dd >= 0.45:
            legs.append({
                "market": "DD YES",
                "p": round(p_dd, 3),
            })

        if len(legs) < 2: continue

        # Naive parlay p (assumes independence; SGP correlation gives discount)
        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        # Correlation boost — same-player props are positively correlated
        correlation_boost = 1.15  # naively assume 15% boost
        parlay_p_corr = min(parlay_p_naive * correlation_boost, 0.99)

        parlays.append({
            "player": player,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "confluence_score": round(score, 2),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
            "advisory": "Same-player SGP legs are positively correlated; "
                        "actual parlay payout is better than naive product.",
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "NBA player SGP builder. Confluence_score >= 5 + OVER "
                       "signals across PTS/REB/AST/3PM/PRA + 30+ PTS + DD. "
                       "Naive parlay_p (independent) and correlation_boosted "
                       "parlay_p (1.15x for same-player positive correlation).",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-sgp] {o['n_parlays']} SGP builds -> {OUT}")
