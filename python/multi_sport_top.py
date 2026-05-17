"""
EdgeStat -- Multi-Sport Top Picks aggregator.

Pulls the top bet from each sport's bestbet file + the unified best_bets ranking,
and assembles a single "Today's Best Across All Sports" feed.

For each sport, surfaces:
  - Top pick + confidence
  - Runner-up
  - Fair odds
  - Bet key (for one-click TRACK)

Output: data/multi_sport_top.json
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "multi_sport_top.json")

SPORT_FILES = [
    # (display, bestbet file, page link, color)
    ("MLB",  "today.json",         "play-of-day.html",  "#1e5db8"),   # use POD field
    ("GOLF", "golf_bestbet.json",  "golf.html",         "#d4a04a"),
    ("LOL",  "lol_bestbet.json",   "lol.html",          "#b450dc"),
    ("CS",   "cs_bestbet.json",    "cs.html",           "#ffa51e"),
    ("KBO",  "kbo_bestbet.json",   "kbo.html",          "#cf3939"),
]


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _extract_pick(sport: str, blob: Dict[str, Any], page: str) -> Dict[str, Any]:
    """Normalize each sport's top pick into a common shape."""
    if sport == "MLB":
        pod = blob.get("play_of_day") or {}
        if not pod:
            return None
        return {
            "sport": sport,
            "label": pod.get("label") or f"{pod.get('matchup','?')} -- {pod.get('play','?')}",
            "matchup": pod.get("matchup"),
            "play": pod.get("play"),
            "model_prob": pod.get("model_prob"),
            "fair_american": pod.get("model_price"),
            "market_american": pod.get("market_price"),
            "edge_pct": pod.get("edge_pct"),
            "kelly_units": pod.get("kelly_units"),
            "confidence": pod.get("confidence"),
            "page": page,
            "bet_key": f"MLB|{pod.get('matchup','')}|{pod.get('play','')}|{pod.get('model_price','?')}",
        }
    pot = blob.get("top_bet")
    if not pot:
        return None
    return {
        "sport": sport,
        "label": pot.get("label") or f"{pot.get('player') or pot.get('team','?')} {pot.get('type') or pot.get('kind','?')}",
        "player_or_team": pot.get("player") or pot.get("team"),
        "opponent": pot.get("opponent"),
        "play": pot.get("type") or pot.get("kind", "ML"),
        "model_prob": pot.get("model_prob") or pot.get("prob"),
        "fair_american": pot.get("fair_american"),
        "confidence": pot.get("confidence"),
        "reasoning": pot.get("reasoning"),
        "page": page,
        "bet_key": pot.get("bet_key"),
    }


def run() -> Dict[str, Any]:
    picks = []
    for sport, filename, page, color in SPORT_FILES:
        blob = _load(os.path.join(DATA_DIR, filename))
        pick = _extract_pick(sport, blob, page)
        if pick:
            pick["color"] = color
            picks.append(pick)

    # Also try NBA + NHL (from best_bets ranking)
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    seen_sports = {p["sport"] for p in picks}
    for c in (bb.get("bets") or []):
        if c.get("source") in ("NBA", "NHL") and c.get("source") not in seen_sports:
            picks.append({
                "sport": c["source"],
                "label": c["label"],
                "model_prob": c.get("model_prob"),
                "fair_american": c.get("line"),
                "confidence": "MED",
                "page": c.get("url_anchor") or f"{c['source'].lower()}.html",
                "bet_key": f"{c['source']}|{c.get('team','')}|{c.get('play','')}|{c.get('line','?')}",
                "color": "#c43e3e" if c["source"] == "NBA" else "#0080a3",
            })
            seen_sports.add(c["source"])

    # Sort: confidence first (HIGH > MED > LOW), then by sport in display order
    conf_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    picks.sort(key=lambda p: (conf_order.get(p.get("confidence", "MED"), 1), p["sport"]))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_sports": len(picks),
        "picks": picks,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Multi-sport top picks: {p['n_sports']} sports surfaced")
    for pk in p["picks"]:
        prob = pk.get("model_prob") or 0
        print(f"  {pk['sport']:5} ({pk.get('confidence','MED'):4}) -- {pk.get('label','?')[:70]} -- "
              f"{prob*100:.1f}% @ {pk.get('fair_american','?')}")
