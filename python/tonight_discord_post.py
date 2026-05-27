"""
EdgeStat -- Tonight's Discord post generator.

Auto-generates a Discord-format post combining:
  - Slate quality tier
  - Top 3 picks (singles)
  - Top 2 parlays
  - 1 long shot from extreme outcomes board
  - Slate quality + advisory
  - Brief tagline

Output: data/tonight_discord_post.md
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_discord_post.md")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    brief = _load(os.path.join(DATA_DIR, "slate_master_brief.json"))
    parlays = _load(os.path.join(DATA_DIR, "cross_sport_best_parlays_board.json"))
    extreme = _load(os.path.join(DATA_DIR, "cross_sport_extreme_outcomes_board.json"))

    headline = brief.get("headline") or {}
    quality = headline.get("slate_quality_tier") or "MODEST_NIGHT"
    top_5 = brief.get("top_5_picks") or []
    lock = brief.get("lock_of_night") or {}

    parlay_top = (parlays.get("top_10_diverse") or [])[:2]
    extreme_top = (extreme.get("extreme_picks") or [])[:1]

    lines = []
    lines.append("**EdgeStat -- Tonight's Slate**")
    lines.append(f"_{quality}_ | "
                 f"L:{headline.get('total_locks', 0)} "
                 f"S:{headline.get('total_strong', 0)} "
                 f"F:{headline.get('total_fades', 0)}")
    lines.append("")

    if lock and lock.get("subject"):
        lines.append(f":lock: **LOCK:** {lock.get('subject')} ({lock.get('sport')})")
        lines.append("")

    if top_5:
        lines.append(":dart: **Top Picks:**")
        for i, p in enumerate(top_5[:3], 1):
            sport = p.get("sport") or "?"
            subject = p.get("subject") or "?"
            play = p.get("play") or ""
            lines.append(f"{i}. [{sport}] {subject} -- {play}")
        lines.append("")

    if parlay_top:
        lines.append(":chains: **Top Parlays:**")
        for p in parlay_top:
            sport = p.get("sport") or "?"
            subject = p.get("subject") or "?"
            n_legs = p.get("n_legs", 0)
            parlay_p = p.get("parlay_p", 0)
            lines.append(f"- [{sport}] {subject} ({n_legs} legs, p={parlay_p})")
        lines.append("")

    if extreme_top:
        e = extreme_top[0]
        lines.append(":dizzy: **Long Shot:** "
                     f"{e.get('subject')} ({e.get('sport')} {e.get('market')}, "
                     f"p={e.get('estimated_probability')})")
        lines.append("")

    lines.append(f":coin: Bankroll Advisory: {headline.get('advisory', 'Modest sizing.')}")
    lines.append("")
    lines.append("_EdgeStat: ML-driven sports betting analytics. Not financial advice._")

    post = "\n".join(lines)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(post)

    return {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "bytes_written": len(post),
        "output": OUT,
    }


if __name__ == "__main__":
    o = run()
    print(f"[discord-post] wrote {o.get('bytes_written', 0)} bytes -> {OUT}")
