"""
EdgeStat -- Tonight's brief (60-second read).

Generates a SHORT focused markdown summary of tonight's actionable
picks. Different from daily_summary_v2.md (which has 24 sections);
this is the picks-only quick read for actually betting.

Output: data/tonight_brief.md
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MD_OUT = os.path.join(DATA_DIR, "tonight_brief.md")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    locks = _load(os.path.join(DATA_DIR, "locks_history.json"))
    whales = _load(os.path.join(DATA_DIR, "whale_picks.json"))
    parlays = _load(os.path.join(DATA_DIR, "cross_sport_parlays.json"))
    unders = _load(os.path.join(DATA_DIR, "mlb_unders_alerts.json"))
    sharp = _load(os.path.join(DATA_DIR, "sharp_action_radar.json"))
    cal = _load(os.path.join(DATA_DIR, "calibration_status.json"))

    today = dt.date.today().isoformat()
    lines = [f"# 🌙 Tonight's Brief — {today}", ""]
    lines.append(f"_60-second read. Calibration tier: **{cal.get('calibration_tier','?')}** ({cal.get('calibration_progress_pct',0)}% progress)._")
    lines.append("")

    # WHALES (top priority)
    top_whales = [w for w in (whales.get("whales") or []) if w.get("tier") == "WHALE"]
    strong_whales = [w for w in (whales.get("whales") or []) if w.get("tier") == "STRONG"]
    if top_whales:
        lines.append("## 🐋 WHALES (size up max)")
        for w in top_whales[:3]:
            lines.append(f"- **{w.get('sport')}** · {w.get('player_or_matchup')} {w.get('market')} · "
                          f"{w.get('prob',0)*100:.0f}% / +{w.get('edge_pct',0):.1f}%")
            for r in w.get("reasons", [])[:3]:
                lines.append(f"  - {r}")
        lines.append("")

    if strong_whales:
        lines.append(f"## 💪 STRONG ({len(strong_whales)} picks)")
        for w in strong_whales[:5]:
            lines.append(f"- [{w.get('sport')}] {w.get('player_or_matchup')} {w.get('market')} · "
                          f"{w.get('prob',0)*100:.0f}% / +{w.get('edge_pct',0):.1f}%")
        lines.append("")

    # Today's locks
    todays_locks = locks.get("todays_locks") or []
    if todays_locks:
        lines.append("## 🔒 5 Daily Locks")
        for L in todays_locks:
            lines.append(f"- **{L.get('player_or_matchup')}** {L.get('market')} ({L.get('sport')}) -- {L.get('prob',0)*100:.0f}% / +{L.get('edge_pct',0):.1f}%")
        lines.append("")

    # Top sharp signals
    pos_sharp = (sharp.get("positive_signals") or [])[:3]
    if pos_sharp:
        lines.append("## 📡 Sharp Money Following Model")
        for s in pos_sharp:
            lines.append(f"- **{s.get('matchup')}** {s.get('market')}: line moved {s.get('opening_implied_pct')}% → {s.get('latest_implied_pct')}% (+{s.get('shift_pp',0):.1f}pp)")
        lines.append("")

    # Strong unders
    strong_unders = (unders.get("strong_unders") or [])[:3]
    if strong_unders:
        lines.append("## 📉 Under Bets")
        for u in strong_unders:
            lines.append(f"- **{u.get('matchup')}** UNDER {u.get('market_total')} — model {u.get('model_fair_total')} [{u.get('tier')} signal]")
        lines.append("")

    # Top 1 parlay
    bal_parlays = (parlays.get("balanced_2_leg_picks") or [])
    if bal_parlays:
        p = bal_parlays[0]
        lines.append("## 🎰 Tonight's Best Parlay")
        legs_str = " + ".join([f"**{L['player_or_matchup']}** {L['market']}" for L in p['legs']])
        lines.append(f"- {legs_str}")
        lines.append(f"- Joint {p['joint_prob']*100:.0f}% · fair {p['fair_parlay_american']:+d} · edge +{p['edge_pct']:.1f}%")
        lines.append("")

    lines.append("---")
    lines.append(f"_Generated {dt.datetime.now().isoformat(timespec='seconds')}_")
    lines.append(f"_Full breakdown: /tonight · Full history: /locks-of-day_")

    md = "\n".join(lines)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MD_OUT, "w", encoding="utf-8") as f: f.write(md)
    return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"), "chars": len(md)}


if __name__ == "__main__":
    p = run()
    print(f"Tonight's brief: {p['chars']} chars written to {MD_OUT}")
