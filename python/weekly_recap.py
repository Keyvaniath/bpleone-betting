"""
EdgeStat -- weekly locks performance recap.

Each pipeline run, regenerates a public-facing weekly recap (last 7 days
of settled locks) suitable for sharing or pasting into the website / social.

Output: data/weekly_recap.md + data/weekly_recap.json

Sections:
   header   week-over-week record + ROI summary
   highlight reel   biggest wins this week (by payout units)
   tough beats      losses with highest pregame probability
   by-sport         per-sport hit rate this week
   by-market        per-market-family hit rate
   trend            7d vs all-time comparison
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MD_OUT = os.path.join(DATA_DIR, "weekly_recap.md")
JSON_OUT = os.path.join(DATA_DIR, "weekly_recap.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    locks = _load(os.path.join(DATA_DIR, "locks_history.json"))
    history = locks.get("history") or []
    today = dt.date.today()
    week_ago = today - dt.timedelta(days=7)

    # Filter to settled locks from last 7 days
    week_settled = []
    for p in history:
        if not p.get("settled"): continue
        try:
            d = dt.date.fromisoformat(p.get("date") or "")
        except Exception:
            continue
        if d < week_ago: continue
        week_settled.append(p)

    wins = [p for p in week_settled if p["result"] == "won"]
    losses = [p for p in week_settled if p["result"] == "lost"]
    pushes = [p for p in week_settled if p["result"] == "push"]
    n_decided = len(wins) + len(losses)
    hit_rate = round(len(wins) / n_decided, 4) if n_decided else None
    net_units = round(sum((p.get("payout_units") or 0) for p in week_settled), 3)
    total_risked = round(sum((p.get("unit_size_quarter_kelly") or 0)
                              for p in week_settled if p["result"] != "push"), 3)
    roi_pct = round(net_units / total_risked * 100, 2) if total_risked > 0 else None

    # Highlight reel: top 5 wins by payout
    top_wins = sorted(wins, key=lambda p: -(p.get("payout_units") or 0))[:5]
    # Tough beats: top 5 losses by pregame probability (sting the most)
    tough_beats = sorted(losses, key=lambda p: -(p.get("prob") or 0))[:5]

    # Per-sport
    by_sport: Dict[str, Dict[str, Any]] = {}
    for p in week_settled:
        sp = p.get("sport") or "?"
        b = by_sport.setdefault(sp, {"wins": 0, "losses": 0, "pushes": 0, "net_units": 0})
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for sp, b in by_sport.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # Per-market
    by_market: Dict[str, Dict[str, Any]] = {}
    for p in week_settled:
        fam = p.get("market_family") or "?"
        b = by_market.setdefault(fam, {"wins": 0, "losses": 0, "pushes": 0, "net_units": 0})
        if p["result"] == "won": b["wins"] += 1
        elif p["result"] == "lost": b["losses"] += 1
        elif p["result"] == "push": b["pushes"] += 1
        b["net_units"] = round(b["net_units"] + (p.get("payout_units") or 0), 3)
    for fam, b in by_market.items():
        d = b["wins"] + b["losses"]
        b["hit_rate"] = round(b["wins"] / d, 4) if d > 0 else None

    # Build markdown
    lines = [f"# EdgeStat Weekly Recap — {week_ago.isoformat()} to {today.isoformat()}", ""]
    if n_decided == 0:
        lines.append("_No settled locks in the past 7 days yet (still building track record)._")
    else:
        lines.append(f"## 📊 7-Day Record: **{len(wins)}-{len(losses)}** ({hit_rate*100:.1f}% hit rate)")
        if roi_pct is not None:
            sign = "+" if net_units >= 0 else ""
            lines.append(f"- Net units: **{sign}{net_units:.2f}u** | ROI: **{sign}{roi_pct:.1f}%**")
        lines.append(f"- {len(week_settled)} settled locks ({len(pushes)} pushes)")
        lines.append("")

    if top_wins:
        lines.append("## 🏆 Highlight Reel — Top 5 Wins")
        for w in top_wins:
            payout = w.get("payout_units") or 0
            lines.append(f"- [{w.get('sport')}] **{w.get('player_or_matchup','?')}** {w.get('market','?')[:30]} · model {w.get('prob',0)*100:.0f}% · +{payout:.3f}u")
        lines.append("")

    if tough_beats:
        lines.append("## 💔 Tough Beats — Locks That Didn't Land")
        for L in tough_beats:
            lines.append(f"- [{L.get('sport')}] **{L.get('player_or_matchup','?')}** {L.get('market','?')[:30]} · model {L.get('prob',0)*100:.0f}% pregame")
        lines.append("")

    if by_sport:
        lines.append("## 🏆 By Sport")
        sorted_sports = sorted(by_sport.items(), key=lambda kv: -(kv[1].get("net_units") or 0))
        for sp, b in sorted_sports:
            hr = b.get("hit_rate")
            sign = "+" if (b["net_units"] or 0) >= 0 else ""
            lines.append(f"- **{sp}**: {b['wins']}-{b['losses']}" + (f" ({hr*100:.1f}%)" if hr is not None else "") + f" · {sign}{b['net_units']:.2f}u")
        lines.append("")

    if by_market:
        lines.append("## 📈 By Market Family")
        sorted_markets = sorted(by_market.items(), key=lambda kv: -(kv[1].get("net_units") or 0))
        for fam, b in sorted_markets[:10]:
            hr = b.get("hit_rate")
            sign = "+" if (b["net_units"] or 0) >= 0 else ""
            lines.append(f"- **{fam}**: {b['wins']}-{b['losses']}" + (f" ({hr*100:.1f}%)" if hr is not None else "") + f" · {sign}{b['net_units']:.2f}u")
        lines.append("")

    # Compare to all-time
    all_hit = locks.get("hit_rate")
    if all_hit is not None and hit_rate is not None:
        delta = (hit_rate - all_hit) * 100
        direction = "above" if delta > 0 else "below" if delta < 0 else "in line with"
        lines.append("## 📊 Trend")
        lines.append(f"- 7-day hit rate ({hit_rate*100:.1f}%) is {abs(delta):.1f}pp {direction} all-time ({all_hit*100:.1f}%)")
        all_net = locks.get("net_units") or 0
        lines.append(f"- All-time: {locks.get('wins',0)}-{locks.get('losses',0)} · {('+' if all_net >= 0 else '')}{all_net:.2f}u")
        lines.append("")

    lines.append(f"_Generated by EdgeStat at {dt.datetime.now().isoformat(timespec='seconds')}_")

    md = "\n".join(lines)
    with open(MD_OUT, "w", encoding="utf-8") as f: f.write(md)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "week_start": week_ago.isoformat(),
        "week_end": today.isoformat(),
        "n_settled": len(week_settled),
        "wins": len(wins),
        "losses": len(losses),
        "pushes": len(pushes),
        "hit_rate": hit_rate,
        "net_units": net_units,
        "total_risked": total_risked,
        "roi_pct": roi_pct,
        "by_sport": by_sport,
        "by_market": by_market,
        "top_wins": top_wins,
        "tough_beats": tough_beats,
        "markdown_chars": len(md),
    }
    with open(JSON_OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Weekly recap: {p['n_settled']} settled locks in last 7 days")
    print(f"  Record: {p['wins']}-{p['losses']} ({(p['hit_rate'] or 0)*100:.1f}%)")
    print(f"  Net units: {p['net_units']:+.2f}u | ROI: {(p['roi_pct'] or 0):+.1f}%")
    if p["top_wins"]:
        print(f"  Top 3 wins:")
        for w in p["top_wins"][:3]:
            print(f"    [{w['sport']}] {w['player_or_matchup'][:25]:25s} +{w.get('payout_units',0):.3f}u")
