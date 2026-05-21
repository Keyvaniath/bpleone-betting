"""
EdgeStat -- markdown snapshot of tonight's slate.

Generates a human-readable text summary Brandon can copy/paste into Discord,
notes, or anywhere else. Plain text + emoji icons. Pulls from bet_slate.json.

Output: data/slate_snapshot.md  (plus also data/slate_snapshot.json)
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MD_OUT = os.path.join(DATA_DIR, "slate_snapshot.md")
JSON_OUT = os.path.join(DATA_DIR, "slate_snapshot.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _fmt_pct(x):
    return f"{x*100:.1f}%" if x is not None else "—"


def _fmt_odds(a):
    if a is None: return "—"
    return f"+{a}" if a >= 0 else str(a)


def _fmt_signed(x):
    if x is None: return "—"
    return f"+{x:.1f}%" if x >= 0 else f"{x:.1f}%"


def run() -> Dict[str, Any]:
    slate = _load(os.path.join(DATA_DIR, "bet_slate.json"))
    picks = slate.get("slate") or []

    today_str = dt.date.today().isoformat()
    lines: List[str] = []
    lines.append(f"# EdgeStat Slate — {today_str}")
    lines.append("")
    lines.append(f"_{len(picks)} picks consolidated from POD + Alpha + Book Edges + Parlay-of-Day._")
    lines.append("")

    type_order = ["POD", "ALPHA", "BOOK", "FADE", "PARLAY"]
    by_type: Dict[str, list] = {t: [] for t in type_order}
    for p in picks:
        by_type.setdefault(p.get("type") or "OTHER", []).append(p)

    for t in type_order:
        items = by_type.get(t) or []
        if not items: continue
        emoji = {"POD": "⭐", "ALPHA": "🎯", "BOOK": "📊", "FADE": "✗", "PARLAY": "🎲"}.get(t, "•")
        label = {"POD": "Play of the Day", "ALPHA": "Alpha Pick", "BOOK": "Book Edges", "FADE": "Fade Pick", "PARLAY": "Parlay"}.get(t, t)
        lines.append(f"## {emoji} {label}")
        lines.append("")
        for p in items:
            title = p.get("title") or "—"
            market = p.get("market") or ""
            prob = p.get("prob")
            odds = p.get("fair_american")
            edge = p.get("edge_pct")
            kelly = p.get("kelly_fraction") or 0
            lines.append(f"- **{title}** · {market}")
            lines.append(f"  Prob {_fmt_pct(prob)} · Odds {_fmt_odds(odds)} · Edge {_fmt_signed(edge)} · Kelly {kelly:.3f}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated {dt.datetime.utcnow().isoformat(timespec='seconds')} UTC by EdgeStat._")
    lines.append("_Stakes assume ¼-Kelly fractional sizing on a flat bankroll._")

    md_text = "\n".join(lines)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(md_text)

    payload = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_picks": len(picks),
        "markdown_bytes": len(md_text.encode("utf-8")),
        "markdown": md_text,
    }
    with open(JSON_OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    o = run()
    print(f"[slate-md] {o['n_picks']} picks, {o['markdown_bytes']} bytes -> {MD_OUT}")
