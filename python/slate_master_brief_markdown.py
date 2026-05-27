"""
EdgeStat -- Slate master brief markdown export.

Renders slate_master_brief.json as a human-readable markdown document
that Brandon can copy into Discord, blog posts, or share directly.
Distinct from slate_markdown_export which renders bet_slate.

Output: data/slate_master_brief.md
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "slate_master_brief.md")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _bullet(label: str, value: Any) -> str:
    return f"- **{label}:** {value}\n"


def run() -> Dict[str, Any]:
    brief = _load(os.path.join(DATA_DIR, "slate_master_brief.json"))

    if not brief:
        return {"status": "no_data"}

    headline = brief.get("headline") or {}
    lock = brief.get("lock_of_night") or {}
    top_5 = brief.get("top_5_picks") or []
    fades = brief.get("top_3_fades") or []
    events = brief.get("top_events") or []
    roi = brief.get("expected_roi") or {}
    fade_top_5 = brief.get("fade_board_top_5") or []

    lines: list = []
    lines.append("# EdgeStat — Tonight's Master Brief")
    lines.append(f"_Generated {brief.get('generated_at') or dt.datetime.utcnow().isoformat(timespec='seconds')} UTC_")
    lines.append("")

    # Headline
    lines.append("## Slate Quality")
    lines.append(_bullet("Tier", headline.get("slate_quality_tier")).rstrip())
    lines.append(_bullet("Score", headline.get("slate_quality_score")).rstrip())
    lines.append(_bullet("Advisory", headline.get("advisory")).rstrip())
    lines.append(_bullet("Total LOCKs", headline.get("total_locks")).rstrip())
    lines.append(_bullet("Total STRONG", headline.get("total_strong")).rstrip())
    lines.append(_bullet("Total FADES", headline.get("total_fades")).rstrip())
    lines.append("")

    # Lock of the night
    if lock:
        lines.append("## Lock of the Night")
        lines.append(_bullet("Subject", lock.get("subject")).rstrip())
        lines.append(_bullet("Source", lock.get("source")).rstrip())
        lines.append(_bullet("Sport", lock.get("sport")).rstrip())
        lines.append(_bullet("Score", lock.get("score")).rstrip())
        if lock.get("details"):
            lines.append(_bullet("Details", lock.get("details").get("matchup")
                                  or lock.get("details").get("market") or "").rstrip())
        lines.append("")

    # Top 5 curated picks
    if top_5:
        lines.append("## Top 5 Curated Picks")
        for i, p in enumerate(top_5, 1):
            lines.append(f"{i}. **{p.get('sport')} / {p.get('subject')}** "
                         f"({p.get('source')}, score={p.get('score')})")
            if p.get("play"):
                lines.append(f"   - Play: {p.get('play')}")
            if p.get("rationale"):
                lines.append(f"   - Rationale: {p.get('rationale')}")
        lines.append("")

    # Top events
    if events:
        lines.append("## Top Events Board")
        for ev in events[:10]:
            lines.append(f"- **{ev.get('sport')}** / {ev.get('event')} "
                         f"({ev.get('tier')})")
            for ang in (ev.get("recommended_angles") or [])[:3]:
                lines.append(f"  - {ang}")
        lines.append("")

    # Expected ROI
    if roi:
        lines.append("## Slate ROI Projection")
        lines.append(_bullet("Picks", roi.get("n_picks")).rstrip())
        lines.append(_bullet("Avg edge", f"{roi.get('avg_edge_pp')}%").rstrip())
        lines.append(_bullet("Expected ROI (1/4 Kelly)",
                              f"{roi.get('expected_roi_pct_quarter_kelly')}%").rstrip())
        lines.append(_bullet("Expected P&L on $100",
                              f"${roi.get('expected_pl_on_100_bankroll')}").rstrip())
        lines.append("")

    # Top fades
    if fade_top_5 or fades:
        lines.append("## Top Fades")
        for fd in (fade_top_5 or fades)[:5]:
            lines.append(f"- **{fd.get('sport') or fd.get('source')}** / "
                         f"{fd.get('subject') or fd.get('entity')} ({fd.get('tier')})")
            if fd.get("recommended_fade_market"):
                lines.append(f"  - Fade angle: {fd.get('recommended_fade_market')}")
        lines.append("")

    md = "\n".join(lines)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)

    return {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "bytes_written": len(md),
        "output": OUT,
    }


if __name__ == "__main__":
    o = run()
    print(f"[master-brief-md] wrote {o.get('bytes_written', 0)} bytes -> {OUT}")
