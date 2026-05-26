"""
EdgeStat -- NBA player ceiling stack alerts.

Aggregates per-player edges across NBA prop modules to surface players
with 3+ market signals aligned OVER:
  - PTS OVER
  - AST OVER
  - REB OVER
  - 3PM OVER
  - PRA OVER
  - 30+ PTS ALT YES
  - DD YES
  - TD YES

When a player has 3+ aligned OVERs across distinct markets, they're a
DFS / parlay anchor candidate. CEILING_ELITE = 6+ aligned signals;
CEILING_STRONG = 4-5; CEILING_LEAN = 3.

Output: data/nba_player_ceiling_stack.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_ceiling_stack.json")


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


def _norm_name(s: str) -> str:
    return (s or "").strip().lower()


def _is_over(edge_class: str) -> bool:
    return "OVER" in (edge_class or "").upper()


def _is_strong(edge_class: str) -> bool:
    ec = (edge_class or "").upper()
    return "STRONG" in ec or "OVER" in ec


def run() -> Dict[str, Any]:
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    ast = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    reb = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    threes = _load(os.path.join(DATA_DIR, "nba_player_threes_props.json"))
    pra = _load(os.path.join(DATA_DIR, "nba_player_pra_props.json"))
    pts_30 = _load(os.path.join(DATA_DIR, "nba_player_30plus_pts_alt.json"))
    dd = _load(os.path.join(DATA_DIR, "nba_double_double_props.json"))
    td = _load(os.path.join(DATA_DIR, "nba_triple_double_props.json"))

    # Aggregate by player -> signals dict
    players: Dict[str, Dict[str, Any]] = {}

    def _ingest(src: Dict[str, Any], signal_key: str,
                check_fn=_is_over, score_field: str = "p_over") -> None:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            player_name = r.get("player") or ""
            key = _norm_name(player_name)
            if not key: continue
            ec = r.get("edge_class") or ""
            entry = players.setdefault(key, {
                "player": player_name,
                "team": r.get("team"),
                "matchup": r.get("matchup"),
                "signals": {},
                "scores": {},
            })
            if not entry.get("team") and r.get("team"):
                entry["team"] = r.get("team")
            if not entry.get("matchup") and r.get("matchup"):
                entry["matchup"] = r.get("matchup")
            entry["signals"][signal_key] = 1 if check_fn(ec) else 0
            score_val = _safe(r.get(score_field) or r.get("p"))
            if score_val:
                entry["scores"][signal_key] = round(score_val, 3)

    _ingest(pts, "PTS_OVER")
    _ingest(ast, "AST_OVER")
    _ingest(reb, "REB_OVER")
    _ingest(threes, "3PM_OVER")
    _ingest(pra, "PRA_OVER")

    # 30+ PTS alt is special -- use top_15_by_p or strong_edges
    for r in (pts_30.get("strong_edges") or pts_30.get("rows") or []):
        if not isinstance(r, dict): continue
        key = _norm_name(r.get("player"))
        if not key: continue
        entry = players.setdefault(key, {
            "player": r.get("player"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "signals": {},
            "scores": {},
        })
        p_30 = _safe(r.get("p_30plus") or r.get("p"))
        entry["signals"]["30PLUS_PTS"] = 1 if p_30 >= 0.40 else 0
        entry["scores"]["30PLUS_PTS"] = round(p_30, 3)

    # DD and TD
    for src, signal_key, p_field in [
        (dd, "DD_YES", "p_dd"),
        (td, "TD_YES", "p_td"),
    ]:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            key = _norm_name(r.get("player"))
            if not key: continue
            entry = players.setdefault(key, {
                "player": r.get("player"),
                "team": r.get("team"),
                "matchup": r.get("matchup"),
                "signals": {},
                "scores": {},
            })
            p_val = _safe(r.get(p_field) or r.get("p"))
            threshold = 0.40 if signal_key == "DD_YES" else 0.18
            entry["signals"][signal_key] = 1 if p_val >= threshold else 0
            entry["scores"][signal_key] = round(p_val, 3)

    # Score each player by aligned OVERs
    alerts: List[Dict[str, Any]] = []
    for key, entry in players.items():
        n_positive = sum(1 for v in entry["signals"].values() if v == 1)
        if n_positive < 3: continue

        if n_positive >= 6:
            tier = "CEILING_ELITE"
        elif n_positive >= 4:
            tier = "CEILING_STRONG"
        else:
            tier = "CEILING_LEAN"

        alerts.append({
            "player": entry["player"],
            "team": entry["team"],
            "matchup": entry["matchup"],
            "n_aligned_overs": n_positive,
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
        "method_note": "Aggregates per-player edges across PTS/AST/REB/3PM/PRA/30+ "
                       "PTS/DD/TD markets. Surfaces players with 3+ aligned OVER "
                       "signals as DFS/parlay anchor candidates. ELITE = 6+; "
                       "STRONG = 4-5; LEAN = 3.",
        "alerts": alerts,
        "elite_ceilings": [a for a in alerts if a["tier"] == "CEILING_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-ceiling] {o['n_alerts']} alerts "
          f"({o['n_elite']} ELITE, {o['n_strong']} STRONG) -> {OUT}")
