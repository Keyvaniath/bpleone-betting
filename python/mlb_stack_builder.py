"""
EdgeStat -- MLB DFS/SGP stack builder.

For each game on tonight's slate, identifies the best 3-batter stack from the
SAME team using:
  - Top-of-order PA leverage (1-5 hitters get 4.0+ PAs)
  - Lineup quality score (from mlb_lineup_quality_index)
  - Hot/cold streak alerts (from hot_streaks.json)
  - Park HR factor (HOMER_FRIENDLY parks boost stacks)
  - Pitcher edge composite tier (opposing pitcher BAD_SPOT = stack opportunity)

Combined stack_score per stack (0-100):
  base = avg_batter_quality
  + park_bonus (HOMER_FRIENDLY = +10, GRAVEYARD = -10)
  + pitcher_bonus (opp pitcher BAD_SPOT = +12, ELITE = -8)
  + heat_bonus (hot streak batters in stack +3 each, cold -3)
  + lineup_continuity (top-3 stacks get +5 for PA leverage)

Surfaces top-5 best stacks across the slate, plus dedicated DFS-style
"correlated stack" labels (HR-leverage / contact / pure-power).

Output: data/mlb_stack_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_stack_builder.json")


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


def _stack_label(stack: List[Dict[str, Any]], park_tier: str) -> str:
    """Label the stack by its character."""
    avg_pwr = sum(b.get("power_bonus", 0) for b in stack) / max(len(stack), 1)
    if park_tier == "HOMER_FRIENDLY" and avg_pwr >= 5:
        return "POWER_STACK"
    if avg_pwr >= 7:
        return "PURE_POWER"
    if all(b.get("score", 50) >= 60 for b in stack):
        return "CONTACT_QUALITY"
    return "BALANCED"


def run() -> Dict[str, Any]:
    lineup_q = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    park_hr = _load(os.path.join(DATA_DIR, "mlb_park_weather_hr_index.json"))
    pitcher_edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    hot_streaks = _load(os.path.join(DATA_DIR, "hot_streaks.json"))

    # Index pitcher edge by matchup + side
    pe_idx: Dict[str, Dict[str, Any]] = {}
    for r in (pitcher_edge.get("rows") or []):
        k = f"{r.get('matchup','')}|{r.get('side','')}"
        pe_idx[k] = r

    # Index park HR by matchup
    park_idx = {g.get("matchup"): g for g in (park_hr.get("games") or [])}

    # Hot/cold sets
    hot_set = {(b.get("name") or "").lower() for b in (hot_streaks.get("hot_batters") or [])}
    cold_set = {(b.get("name") or "").lower() for b in (hot_streaks.get("cold_batters") or [])}

    all_stacks: List[Dict[str, Any]] = []

    for g in (lineup_q.get("games") or []):
        matchup = g.get("matchup") or ""
        park_info = park_idx.get(matchup, {})
        park_tier = park_info.get("tier") or "NEUTRAL"

        for side in ("home", "away"):
            side_info = g.get(side) or {}
            top3 = side_info.get("top_3_batters") or []
            if len(top3) < 3: continue

            # Build 3-batter stack from top-3 of lineup
            stack = []
            for b in top3:
                name = (b.get("name") or "").lower()
                stack.append({
                    "name": b.get("name"),
                    "score": _safe(b.get("score"), 50),
                    "power_bonus": _safe(b.get("power_bonus"), 0),
                    "is_hot": name in hot_set,
                    "is_cold": name in cold_set,
                })

            # Stack score calc
            base = sum(b["score"] for b in stack) / 3.0
            park_bonus = 10 if park_tier == "HOMER_FRIENDLY" else \
                         (-10 if park_tier == "PITCHER_GRAVEYARD" else
                          (5 if park_tier == "HITTER_FRIENDLY" else 0))

            # Opposing pitcher tier
            opp_side = "AWAY" if side == "home" else "HOME"
            opp_pitcher = pe_idx.get(f"{matchup}|{opp_side}", {})
            opp_tier = opp_pitcher.get("tier") or "NEUTRAL"
            pitcher_bonus = {"BAD_SPOT": 12, "SOFT": 6, "NEUTRAL": 0,
                             "STRONG": -5, "ELITE_MATCHUP": -10}.get(opp_tier, 0)

            heat_bonus = sum(3 if b["is_hot"] else (-3 if b["is_cold"] else 0)
                             for b in stack)
            lineup_continuity = 5  # Top-3 stack always gets PA leverage

            stack_score = base + park_bonus + pitcher_bonus + heat_bonus + lineup_continuity
            stack_score = max(20.0, min(100.0, stack_score))
            label = _stack_label(stack, park_tier)

            all_stacks.append({
                "matchup": matchup,
                "team": side_info.get("team"),
                "side": side.upper(),
                "stack_label": label,
                "park_tier": park_tier,
                "opp_pitcher": opp_pitcher.get("pitcher"),
                "opp_pitcher_tier": opp_tier,
                "stack_score": round(stack_score, 1),
                "factors": {
                    "base": round(base, 1),
                    "park_bonus": park_bonus,
                    "pitcher_bonus": pitcher_bonus,
                    "heat_bonus": heat_bonus,
                    "lineup_continuity": lineup_continuity,
                },
                "batters": stack,
            })

    all_stacks.sort(key=lambda s: -s["stack_score"])
    elite = [s for s in all_stacks if s["stack_score"] >= 70]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_stacks": len(all_stacks),
        "n_elite_stacks": len(elite),
        "method_note": "Top-3 batter stack per game-side. Score = avg_quality + park "
                       "bonus + opp_pitcher bonus + heat bonus + PA leverage. "
                       "Elite stack 70+; labels POWER_STACK / PURE_POWER / "
                       "CONTACT_QUALITY / BALANCED.",
        "top_5_stacks": all_stacks[:5],
        "elite_stacks": elite,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[stack] {o['n_stacks']} stacks, {o['n_elite_stacks']} elite -> {OUT}")
