"""
EdgeStat -- NBA triple-double watchlist.

Surfaces top triple-double candidates with extreme stat line potential:
  - Triple-double probability >= 15%
  - High minutes (>=34)
  - Multiple stat OVER signals (PTS + REB + AST + 30+ PTS + DD)
  - Confluence_score >= 6

NBA triple-doubles are rare (~1.5% of games) so any p_td >= 10% is a
genuine value alert.

Output: data/nba_triple_double_watchlist.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_triple_double_watchlist.json")


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


def run() -> Dict[str, Any]:
    td = _load(os.path.join(DATA_DIR, "nba_triple_double_props.json"))
    confluence = _load(os.path.join(DATA_DIR, "nba_player_confluence_score.json"))
    minutes = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))
    dd = _load(os.path.join(DATA_DIR, "nba_double_double_props.json"))

    td_idx = {_norm(r.get("player")): _safe(r.get("p_td") or r.get("p"))
              for r in (td.get("rows") or []) if isinstance(r, dict)}
    conf_idx = {_norm(r.get("player")): r
                for r in (confluence.get("rows") or []) if isinstance(r, dict)}
    min_idx = {_norm(r.get("player")): _safe(
                   r.get("projected_minutes") or r.get("expected_minutes"))
               for r in (minutes.get("rows") or []) if isinstance(r, dict)}

    pts30_idx: Dict[str, float] = {}
    for k in ("rows", "strong_edges"):
        for r in (pts_30.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("player") or "")
                if key and key not in pts30_idx:
                    pts30_idx[key] = _safe(r.get("p_30plus") or r.get("p"))

    dd_idx = {_norm(r.get("player")): _safe(r.get("p_dd") or r.get("p"))
              for r in (dd.get("rows") or []) if isinstance(r, dict)}

    watchlist: List[Dict[str, Any]] = []
    for name, p_td in td_idx.items():
        if p_td < 0.15: continue

        conf = conf_idx.get(name, {})
        score = _safe(conf.get("composite_score"))
        if score < 6: continue

        proj_min = min_idx.get(name, 0)
        if proj_min < 34: continue

        p_30 = pts30_idx.get(name, 0)
        p_dd = dd_idx.get(name, 0)

        watchlist.append({
            "player": conf.get("player") or name.title(),
            "team": conf.get("team"),
            "matchup": conf.get("matchup"),
            "p_td": round(p_td, 3),
            "p_dd": round(p_dd, 3),
            "p_30plus_pts": round(p_30, 3),
            "projected_minutes": round(proj_min, 1),
            "confluence_score": round(score, 2),
            "advisory": "Top triple-double candidate. Recommended bets: TD YES "
                        "(typical 4-1 to 8-1), DD YES + 30+ PTS (correlated "
                        "side bet), PRA OVER (volume).",
            "recommended_markets": [
                "Triple-Double YES",
                "Double-Double YES + PRA OVER (parlay)",
                "30+ PTS YES",
                "10+ AST YES",
                "10+ REB YES",
            ],
        })

    watchlist.sort(key=lambda w: -w["p_td"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_watchlist": len(watchlist),
        "method_note": "NBA triple-double watchlist. p_td >= 15% + "
                       "confluence_score >= 6 + projected_minutes >= 34. "
                       "NBA TDs ~1.5% baseline historical so 15%+ is a "
                       "strong value lean.",
        "watchlist": watchlist,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-td] {o['n_watchlist']} on watchlist -> {OUT}")
