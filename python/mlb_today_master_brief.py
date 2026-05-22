"""
EdgeStat -- MLB Today's Master Brief.

Generates a single short-paragraph natural-language brief of tonight's MLB
slate, combining the most-actionable signals from all aggregator outputs.

Designed for:
  - Push notification body
  - Bet slate header summary
  - Morning daily digest

Reads:
  - mlb_today_top_batter_props (BATTER PoD)
  - mlb_today_top_pitcher_props (PITCHER PoD)
  - mlb_todays_alerts (priority signals)
  - mlb_today_lean_consensus (consensus directional bets)

Output: data/mlb_today_master_brief.json
  {
    "headline": "Tonight: 3 games, Aaron Judge BATTER PoD, NYY home stack elite",
    "paragraph": "Tonight's MLB slate has 3 games. Aaron Judge leads as our BATTER
       Play of the Day with composite score 1.31...",
    "actionable_bullets": [...]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_today_master_brief.json")


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


def run() -> Dict[str, Any]:
    top_batter = _load(os.path.join(DATA_DIR, "mlb_today_top_batter_props.json"))
    top_pitcher = _load(os.path.join(DATA_DIR, "mlb_today_top_pitcher_props.json"))
    alerts = _load(os.path.join(DATA_DIR, "mlb_todays_alerts.json"))
    lean_consensus = _load(os.path.join(DATA_DIR, "mlb_today_lean_consensus.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    stack = _load(os.path.join(DATA_DIR, "mlb_stack_builder.json"))

    n_games = len(matchups.get("games") or [])
    batter_pod = top_batter.get("BATTER_PLAY_OF_THE_DAY") or {}
    pitcher_pod = top_pitcher.get("PITCHER_PLAY_OF_THE_DAY") or {}
    top_stacks = stack.get("top_5_stacks") or []
    elite_stacks = stack.get("elite_stacks") or []

    headline_parts = [f"Tonight: {n_games} MLB games"]
    if batter_pod.get("batter"):
        headline_parts.append(
            f"BATTER PoD {batter_pod['batter']} ({batter_pod.get('n_strong_edges',0)} signals)")
    if pitcher_pod.get("pitcher"):
        headline_parts.append(
            f"PITCHER PoD {pitcher_pod['pitcher']}")
    if elite_stacks:
        headline_parts.append(f"{len(elite_stacks)} elite stacks")
    headline = " · ".join(headline_parts)

    # Build paragraph
    para_parts = [f"Tonight's MLB slate features {n_games} games."]
    if batter_pod.get("batter"):
        net = batter_pod.get("net_direction", "MIXED")
        n_strong = batter_pod.get("n_strong_edges", 0)
        composite = batter_pod.get("composite_score", 0)
        para_parts.append(
            f"BATTER Play of the Day is {batter_pod['batter']} "
            f"with {n_strong} STRONG signals across our props "
            f"({net.lower()}, composite {composite}). "
        )
    if pitcher_pod.get("pitcher"):
        net = pitcher_pod.get("net_direction", "MIXED")
        n_strong = pitcher_pod.get("n_strong_edges", 0)
        para_parts.append(
            f"PITCHER Play of the Day is {pitcher_pod['pitcher']} "
            f"({n_strong} signals, {net.lower()}). "
        )
    if elite_stacks:
        labels = [f"{s['team']} {s['stack_label']}" for s in elite_stacks[:2]]
        para_parts.append(f"Elite DFS stacks: {', '.join(labels)}. ")

    n_alerts = alerts.get("n_alerts_total", 0)
    if n_alerts > 0:
        n_high = alerts.get("n_high_priority", 0)
        para_parts.append(
            f"{n_alerts} synthesized alerts ({n_high} high-priority) across "
            "pitcher edge, bullpen fatigue, park weather, and team total signals."
        )

    paragraph = "".join(para_parts).strip()

    # Actionable bullets
    bullets: List[str] = []
    if batter_pod.get("batter"):
        edges = batter_pod.get("edges") or []
        for e in edges[:3]:
            bullets.append(
                f"BATTER: {batter_pod['batter']} - {e.get('market')} "
                f"(p={e.get('p'):.2f}, fair {e.get('fair_odds')})"
            )
    if pitcher_pod.get("pitcher"):
        edges = pitcher_pod.get("edges") or []
        for e in edges[:3]:
            bullets.append(
                f"PITCHER: {pitcher_pod['pitcher']} - {e.get('market')} "
                f"({e.get('direction')})"
            )

    top_alerts = (alerts.get("top_5_action") or [])
    for a in top_alerts[:3]:
        bullets.append(f"ALERT P{a.get('priority')}: {a.get('message')}")

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": n_games,
        "headline": headline,
        "paragraph": paragraph,
        "actionable_bullets": bullets,
        "method_note": "Natural-language master brief combining top_batter + "
                       "top_pitcher + alerts + stack_builder for daily digest.",
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[brief] {o['n_games']} games. {o['headline'][:80]}... -> {OUT}")
