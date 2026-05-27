"""
EdgeStat -- NBA player UNDER fade alerts.

Counterpart to nba_player_ceiling_stack but on the DOWNSIDE. Surfaces
players with 3+ aligned UNDER signals across:
  - PTS UNDER
  - AST UNDER
  - REB UNDER
  - 3PM UNDER
  - PRA UNDER
  - LOW MINUTES (projected minutes below baseline)
  - DD NO (probability < 18%)

When a player has 3+ aligned UNDERs, they're a multi-prop fade / "0-stat
trap" candidate. FADE_ELITE = 5+; STRONG = 4; LEAN = 3.

Output: data/nba_player_under_fade.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_under_fade.json")


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


def _is_under(ec: str) -> bool:
    return "UNDER" in (ec or "").upper()


def run() -> Dict[str, Any]:
    pts = _load(os.path.join(DATA_DIR, "nba_player_points_props.json"))
    ast = _load(os.path.join(DATA_DIR, "nba_player_assists_props.json"))
    reb = _load(os.path.join(DATA_DIR, "nba_player_rebounds_props.json"))
    threes = _load(os.path.join(DATA_DIR, "nba_player_threes_props.json"))
    pra = _load(os.path.join(DATA_DIR, "nba_player_pra_props.json"))
    mins = _load(os.path.join(DATA_DIR, "nba_player_minutes_props.json"))
    dd = _load(os.path.join(DATA_DIR, "nba_double_double_props.json"))

    players: Dict[str, Dict[str, Any]] = {}

    def _entry(name: str, r: Dict[str, Any]) -> Dict[str, Any]:
        key = _norm(name)
        if not key: return {}
        return players.setdefault(key, {
            "player": name,
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "signals": {},
        })

    def _ingest_under(src: Dict[str, Any], signal_key: str) -> None:
        for r in (src.get("rows") or []):
            if not isinstance(r, dict): continue
            entry = _entry(r.get("player") or "", r)
            if not entry: continue
            entry["signals"][signal_key] = 1 if _is_under(r.get("edge_class") or "") else 0

    _ingest_under(pts, "PTS_UNDER")
    _ingest_under(ast, "AST_UNDER")
    _ingest_under(reb, "REB_UNDER")
    _ingest_under(threes, "3PM_UNDER")
    _ingest_under(pra, "PRA_UNDER")
    _ingest_under(mins, "MIN_UNDER")

    # DD NO (low DD probability is downside signal)
    for r in (dd.get("rows") or []):
        if not isinstance(r, dict): continue
        entry = _entry(r.get("player") or "", r)
        if not entry: continue
        p_dd = _safe(r.get("p_dd") or r.get("p"))
        entry["signals"]["DD_NO"] = 1 if 0 < p_dd <= 0.18 else 0

    alerts: List[Dict[str, Any]] = []
    for key, entry in players.items():
        n = sum(1 for v in entry["signals"].values() if v == 1)
        if n < 3: continue
        if n >= 5:
            tier = "FADE_ELITE"
        elif n == 4:
            tier = "FADE_STRONG"
        else:
            tier = "FADE_LEAN"
        alerts.append({
            "player": entry["player"],
            "team": entry["team"],
            "matchup": entry["matchup"],
            "n_aligned_unders": n,
            "signals": entry["signals"],
            "tier": tier,
        })

    alerts.sort(key=lambda a: -a["n_aligned_unders"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "n_elite": sum(1 for a in alerts if a["tier"] == "FADE_ELITE"),
        "method_note": "NBA player UNDER fade alerts. Counterpart to ceiling "
                       "stack. Surfaces players with 3+ aligned UNDERs across "
                       "PTS / AST / REB / 3PM / PRA / MIN / DD_NO markets. "
                       "FADE_ELITE = 5+; STRONG = 4; LEAN = 3.",
        "alerts": alerts,
        "elite_fades": [a for a in alerts if a["tier"] == "FADE_ELITE"],
        "top_15": alerts[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-under-fade] {o['n_alerts']} alerts ({o['n_elite']} ELITE) -> {OUT}")
