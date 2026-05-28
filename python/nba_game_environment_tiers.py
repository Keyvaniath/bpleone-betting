"""
EdgeStat -- NBA game-environment tier classifier.

Pure-model (no odds needed). Consumes the pace+points projection and
classifies each game's scoring environment + game-script archetype:

  total tier:  SHOOTOUT >=235, HIGH >=225, MODERATE >=215,
               LOW >=205, ROCK_FIGHT <205
  script:      margin >=12 -> BLOWOUT_RISK (fade late OVERs, garbage-time
               variance); margin <=6 -> COMPETITIVE (clutch minutes,
               late free-throw inflation favors OVER)

Surfaces which games favor OVER vs UNDER environments before book lines.

Output: data/nba_game_environment_tiers.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_game_environment_tiers.json")


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


def _total_tier(total: float) -> str:
    if total >= 235: return "SHOOTOUT"
    if total >= 225: return "HIGH"
    if total >= 215: return "MODERATE"
    if total >= 205: return "LOW"
    return "ROCK_FIGHT"


def _script(margin_abs: float) -> str:
    if margin_abs >= 12: return "BLOWOUT_RISK"
    if margin_abs <= 6: return "COMPETITIVE"
    return "NEUTRAL_SCRIPT"


def run() -> Dict[str, Any]:
    proj = _load(os.path.join(DATA_DIR, "nba_team_pace_points_projection.json"))

    rows: List[Dict[str, Any]] = []
    for g in (proj.get("rows") or []):
        if not isinstance(g, dict): continue
        total = _safe(g.get("projected_game_total"))
        if total <= 0: continue
        pace = _safe(g.get("projected_pace"))
        margin = _safe(g.get("projected_margin"))
        margin_abs = abs(margin)

        t_tier = _total_tier(total)
        scr = _script(margin_abs)

        # Environment lean: high-total + competitive -> OVER friendly;
        # low-total + blowout -> UNDER friendly (garbage-time bench units).
        over_signals = 0
        if t_tier in ("SHOOTOUT", "HIGH"): over_signals += 1
        if scr == "COMPETITIVE": over_signals += 1
        if pace >= 101: over_signals += 1

        under_signals = 0
        if t_tier in ("ROCK_FIGHT", "LOW"): under_signals += 1
        if scr == "BLOWOUT_RISK": under_signals += 1
        if pace <= 98: under_signals += 1

        if over_signals >= 2 and over_signals > under_signals:
            env_lean = "OVER_FRIENDLY"
        elif under_signals >= 2 and under_signals > over_signals:
            env_lean = "UNDER_FRIENDLY"
        else:
            env_lean = "NEUTRAL"

        rows.append({
            "matchup": g.get("matchup") or "?",
            "projected_pace": round(pace, 1),
            "projected_game_total": round(total, 1),
            "projected_margin": round(margin, 1),
            "total_tier": t_tier,
            "game_script": scr,
            "over_signals": over_signals,
            "under_signals": under_signals,
            "environment_lean": env_lean,
            "recommended_markets": (
                ["game total OVER", "1Q/1H OVER", "pace-up player PRA OVER"]
                if env_lean == "OVER_FRIENDLY" else
                ["game total UNDER", "2H UNDER (blowout)", "star minutes UNDER"]
                if env_lean == "UNDER_FRIENDLY" else
                ["no strong environment lean"]
            ),
        })

    # Sort highest projected total first
    rows.sort(key=lambda r: -r["projected_game_total"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_over_friendly": sum(1 for r in rows if r["environment_lean"] == "OVER_FRIENDLY"),
        "n_under_friendly": sum(1 for r in rows if r["environment_lean"] == "UNDER_FRIENDLY"),
        "method_note": "NBA game-environment tiers from pace+points projection. "
                       "total_tier: SHOOTOUT>=235, HIGH>=225, MODERATE>=215, "
                       "LOW>=205, ROCK_FIGHT<205. script from |margin|: "
                       "BLOWOUT_RISK>=12, COMPETITIVE<=6. env_lean from "
                       "total/script/pace signal confluence (2+ to lean).",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-env-tiers] {o['n_games']} games "
          f"({o['n_over_friendly']} OVER-friendly, "
          f"{o['n_under_friendly']} UNDER-friendly) -> {OUT}")
