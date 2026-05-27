"""
EdgeStat -- NHL skater ceiling stack alerts.

NHL counterpart to nba_player_ceiling_stack. Aggregates per-skater edges
across NHL prop modules to surface multi-market OVER alignment:
  - SOG OVER
  - 3+ SOG YES
  - POINTS OVER
  - 2+ POINTS YES
  - ANYTIME GOAL YES (>=22% baseline)
  - 2+ GOALS YES (rare; >=10%)
  - HITS+BLOCKS OVER
  - 3+ HITS YES

CEILING_ELITE = 5+ aligned; STRONG = 3-4; LEAN = 2 (DFS anchor candidate).

Output: data/nhl_skater_ceiling_stack.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_ceiling_stack.json")


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
    sog = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    sog_3 = _load(os.path.join(DATA_DIR, "nhl_skater_3plus_sog.json"))
    pts = _load(os.path.join(DATA_DIR, "nhl_skater_points_props.json"))
    pts_2 = _load(os.path.join(DATA_DIR, "nhl_skater_2plus_points.json"))
    goal = _load(os.path.join(DATA_DIR, "nhl_anytime_goal_props.json"))
    goal_2 = _load(os.path.join(DATA_DIR, "nhl_skater_2plus_goals.json"))
    hits_blocks = _load(os.path.join(DATA_DIR, "nhl_skater_hits_blocks_props.json"))
    hits_3 = _load(os.path.join(DATA_DIR, "nhl_skater_3plus_hits.json"))

    players: Dict[str, Dict[str, Any]] = {}

    def _entry(player_name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(player_name)
        if not key: return {}
        return players.setdefault(key, {
            "player": player_name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "signals": {},
            "scores": {},
        })

    def _ingest_over(src: Dict[str, Any], signal_key: str) -> None:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or r.get("skater") or ""
            entry = _entry(name, r)
            if not entry: continue
            entry["signals"][signal_key] = 1 if _is_over(r.get("edge_class") or "") else 0

    def _ingest_threshold(src: Dict[str, Any], signal_key: str,
                          p_field: str, threshold: float) -> None:
        seen: set = set()
        for k in ("rows", "strong_edges", "top_15_by_p"):
            for r in (src.get(k) or []):
                if not isinstance(r, dict): continue
                name = r.get("player") or r.get("skater") or ""
                key = _norm(name)
                if key in seen: continue
                seen.add(key)
                entry = _entry(name, r)
                if not entry: continue
                p_val = _safe(r.get(p_field) or r.get("p"))
                entry["signals"][signal_key] = 1 if p_val >= threshold else 0
                entry["scores"][signal_key] = round(p_val, 3)

    _ingest_over(sog, "SOG_OVER")
    _ingest_over(pts, "POINTS_OVER")
    _ingest_over(hits_blocks, "HITS_BLOCKS_OVER")
    _ingest_threshold(sog_3, "3PLUS_SOG", "p_3plus_sog", 0.45)
    _ingest_threshold(pts_2, "2PLUS_POINTS", "p_2plus_points", 0.32)
    _ingest_threshold(goal, "ANYTIME_GOAL", "p_atg", 0.22)
    _ingest_threshold(goal_2, "2PLUS_GOALS", "p_2plus_goals", 0.10)
    _ingest_threshold(hits_3, "3PLUS_HITS", "p_3plus_hits", 0.40)

    alerts: List[Dict[str, Any]] = []
    for key, entry in players.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 2: continue
        if n >= 5:
            tier = "CEILING_ELITE"
        elif n >= 3:
            tier = "CEILING_STRONG"
        else:
            tier = "CEILING_LEAN"
        alerts.append({
            "player": entry["player"],
            "team": entry["team"],
            "matchup": entry["matchup"],
            "n_aligned_overs": n,
            "signals": entry["signals"],
            "scores": entry["scores"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_aligned_overs"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "CEILING_ELITE"),
        "n_strong": sum(1 for a in alerts if a["tier"] == "CEILING_STRONG"),
        "method_note": "NHL counterpart to nba_player_ceiling_stack. Aggregates "
                       "per-skater OVERs across SOG/Points/Goal/Hits markets. "
                       "ELITE = 5+ aligned; STRONG = 3-4; LEAN = 2.",
        "alerts": alerts,
        "elite_ceilings": [a for a in alerts if a["tier"] == "CEILING_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-ceiling] {o['n_alerts']} alerts ({o['n_elite']} ELITE, "
          f"{o['n_strong']} STRONG) -> {OUT}")
