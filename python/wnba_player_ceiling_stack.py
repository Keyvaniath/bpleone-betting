"""
EdgeStat -- WNBA player ceiling stack alerts.

WNBA counterpart to nba_player_ceiling_stack. Aggregates per-player edges
across WNBA prop modules:
  - PTS OVER
  - REB OVER
  - AST OVER
  - 3PM OVER
  - 20+ PTS YES (>=35%)
  - DD YES (>=40%)
  - BLOCKS+STEALS OVER

CEILING_ELITE = 5+ aligned; STRONG = 3-4; LEAN = 2.

Output: data/wnba_player_ceiling_stack.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_ceiling_stack.json")


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
    pts = _load(os.path.join(DATA_DIR, "wnba_player_pts_props.json"))
    pts_20 = _load(os.path.join(DATA_DIR, "wnba_player_20plus_pts_alt.json"))
    reb_ast = _load(os.path.join(DATA_DIR, "wnba_player_reb_ast_props.json"))
    threes = _load(os.path.join(DATA_DIR, "wnba_player_threes_props.json"))
    dd = _load(os.path.join(DATA_DIR, "wnba_player_double_double.json"))
    blocks_steals = _load(os.path.join(DATA_DIR, "wnba_player_blocks_steals_props.json"))

    players: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return players.setdefault(key, {
            "player": name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "signals": {},
            "scores": {},
        })

    # Points OVER
    for r in (pts.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["signals"]["PTS_OVER"] = 1 if _is_over(r.get("edge_class") or "") else 0

    # 20+ pts alt
    for k in ("rows", "strong_edges"):
        seen: set = set()
        for r in (pts_20.get(k) or []):
            if not isinstance(r, dict): continue
            name = r.get("player") or ""
            if _norm(name) in seen: continue
            seen.add(_norm(name))
            entry = _entry(name, r)
            if not entry: continue
            p_20 = _safe(r.get("p_20plus") or r.get("p"))
            entry["signals"]["20PLUS_PTS"] = 1 if p_20 >= 0.35 else 0
            entry["scores"]["20PLUS_PTS"] = round(p_20, 3)

    # Reb+Ast (split: this module typically has separate reb and ast rows)
    for r in (reb_ast.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        market = (r.get("market") or "").upper()
        ec = (r.get("edge_class") or "").upper()
        if "REB" in market:
            entry["signals"]["REB_OVER"] = 1 if "OVER" in ec else 0
        elif "AST" in market or "ASSIST" in market:
            entry["signals"]["AST_OVER"] = 1 if "OVER" in ec else 0
        else:
            # Fallback: generic
            entry["signals"]["REBAST_OVER"] = 1 if "OVER" in ec else 0

    # Threes
    for r in (threes.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["signals"]["3PM_OVER"] = 1 if _is_over(r.get("edge_class") or "") else 0

    # DD
    for r in (dd.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        p_dd = _safe(r.get("p_dd") or r.get("p"))
        entry["signals"]["DD_YES"] = 1 if p_dd >= 0.40 else 0
        entry["scores"]["DD_YES"] = round(p_dd, 3)

    # Blocks+steals OVER
    for r in (blocks_steals.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        entry["signals"]["BLK_STL_OVER"] = 1 if _is_over(r.get("edge_class") or "") else 0

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
        "method_note": "WNBA counterpart to nba_player_ceiling_stack. Aggregates "
                       "per-player OVERs across PTS/REB/AST/3PM/20+_PTS/DD/BLK+STL. "
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
    print(f"[wnba-ceiling] {o['n_alerts']} alerts ({o['n_elite']} ELITE, "
          f"{o['n_strong']} STRONG) -> {OUT}")
