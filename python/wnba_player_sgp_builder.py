"""
EdgeStat -- WNBA player same-game parlay (SGP) builder.

WNBA counterpart to nba_player_sgp_builder. For each WNBA player with
confluence_score >= 6, builds the recommended SGP from their OVER
signals across PTS / REB+AST / 3PM / DD / 20+ PTS markets.

Apply 1.18x correlation boost (slightly higher than NBA's 1.15x since
WNBA scorers have tighter correlation across PTS / REB+AST / 20+ PTS).

Output: data/wnba_player_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_sgp_builder.json")


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
    confluence = _load(os.path.join(DATA_DIR, "wnba_player_confluence_score.json"))
    pts = _load(os.path.join(DATA_DIR, "wnba_player_pts_props.json"))
    reb_ast = _load(os.path.join(DATA_DIR, "wnba_player_reb_ast_props.json"))
    threes = _load(os.path.join(DATA_DIR, "wnba_player_threes_props.json"))
    pts_20 = _load(os.path.join(DATA_DIR, "wnba_player_20plus_pts_alt.json"))
    dd = _load(os.path.join(DATA_DIR, "wnba_player_double_double.json"))

    def _idx(src):
        return {_norm(r.get("player")): r for r in (src.get("rows") or []) if isinstance(r, dict)}

    pts_idx = _idx(pts)
    threes_idx = _idx(threes)

    reb_ast_by_player: Dict[str, Dict[str, str]] = {}
    for r in (reb_ast.get("rows") or []):
        if not isinstance(r, dict): continue
        name = _norm(r.get("player") or "")
        if not name: continue
        market = (r.get("market") or "").upper()
        ec = (r.get("edge_class") or "").upper()
        reb_ast_by_player.setdefault(name, {})[market] = ec

    pts20_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_20.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts20_idx:
                    pts20_idx[key] = _safe(r.get("p_20plus") or r.get("p"))

    dd_idx = {_norm(r.get("player")): _safe(r.get("p_dd") or r.get("p"))
              for r in (dd.get("rows") or []) if isinstance(r, dict)}

    parlays: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 6: continue

        player = r.get("player")
        name = _norm(player)
        legs: List[Dict[str, Any]] = []

        if _is_over(pts_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "PTS OVER", "p": 0.55})

        ra = reb_ast_by_player.get(name, {})
        if any("OVER" in v for k, v in ra.items() if "REB" in k):
            legs.append({"market": "REB OVER", "p": 0.54})
        if any("OVER" in v for k, v in ra.items() if "AST" in k or "ASSIST" in k):
            legs.append({"market": "AST OVER", "p": 0.54})

        if _is_over(threes_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "3PM OVER", "p": 0.53})

        p_20 = pts20_idx.get(name, 0)
        if p_20 >= 0.35:
            legs.append({"market": "20+ PTS YES", "p": round(p_20, 3)})

        p_dd = dd_idx.get(name, 0)
        if p_dd >= 0.40:
            legs.append({"market": "DD YES", "p": round(p_dd, 3)})

        if len(legs) < 2: continue

        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        parlay_p_corr = min(parlay_p_naive * 1.18, 0.99)

        parlays.append({
            "player": player,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "confluence_score": round(score, 2),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
            "advisory": "Same-player WNBA SGP. PTS / REB+AST / 20+ PTS are highly "
                        "correlated -> 1.18x boost.",
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "WNBA player SGP builder. Confluence >= 6 + OVER signals "
                       "across PTS/REB/AST/3PM + 20+ PTS + DD. 1.18x correlation "
                       "boost.",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[wnba-sgp] {o['n_parlays']} SGP builds -> {OUT}")
