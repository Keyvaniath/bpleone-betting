"""
EdgeStat -- daily summary digest v2.

Markdown brief that includes EVERYTHING actionable:
  - Today's slate count per sport
  - Top 5 picks (across all sources)
  - Player POT (cross-sport)
  - Pre-game alerts (HIGH conviction only)
  - Heat/cold flags
  - Anomaly detector flags
  - Multi-sport regime (HOME_FAV / ROAD_DOG day)
  - Portfolio recommendation
  - Self-training summary

Output: data/daily_summary_v2.md + data/daily_summary_v2.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MD_OUT = os.path.join(DATA_DIR, "daily_summary_v2.md")
JSON_OUT = os.path.join(DATA_DIR, "daily_summary_v2.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    now = dt.datetime.now()
    date = now.date().isoformat()
    lines = [f"# EdgeStat Daily Summary — {date}", ""]

    # Multi-sport regime
    msc = _load(os.path.join(DATA_DIR, "multi_sport_correlation.json"))
    if msc:
        lines.append(f"## 🌐 Slate Overview")
        lines.append(f"- **Regime today:** {msc.get('regime_label', 'BALANCED')} (avg P(home)={msc.get('regime_avg_phome', 0.5)})")
        lines.append(f"- **Total games on board:** {msc.get('n_games_today_total', 0)}")
        lines.append(f"- **Strong home favorites:** {msc.get('n_strong_home_favs', 0)} | **Strong road dogs:** {msc.get('n_strong_road_dogs', 0)}")
        lines.append("")

    # Top 5 best bets
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    bets = bb.get("bets") or []
    if bets:
        lines.append("## 🎯 Top 5 Best Bets")
        for b in bets[:5]:
            stars = "★" * (b.get("stars") or 0)
            lines.append(f"{b.get('rank',0)}. **{b.get('label','')}** ({b.get('quality_score',0)}/100 {stars})")
        lines.append("")

    # Player POT
    ppot = _load(os.path.join(DATA_DIR, "player_pot.json"))
    top5_players = ppot.get("top_5") or []
    if top5_players:
        lines.append("## 🎮 Player Play of the Day (cross-sport)")
        for p in top5_players[:5]:
            lines.append(f"- **[{p.get('sport','?')}]** {p.get('label','')} | {p.get('confidence','MED')} conviction · model {p.get('prob',0)*100:.1f}% fair {p.get('fair_american','?')}")
        lines.append("")

    # Pre-game alerts (HIGH conviction)
    pre = _load(os.path.join(DATA_DIR, "pregame_alerts.json"))
    high_pre = [a for a in (pre.get("alerts") or []) if a.get("confidence") == "HIGH"]
    if high_pre:
        lines.append(f"## ⚡ Pre-Game HIGH Conviction ({len(high_pre)})")
        for a in high_pre[:10]:
            lines.append(f"- [{a['sport']}] **{a['team']}** {a['side']} ({a.get('team_l10','?')} L10) · model {a['p_pick_side']*100:.1f}% fair {a.get('fair_american','?')}")
        lines.append("")

    # Heat/cold alerts
    hc = _load(os.path.join(DATA_DIR, "heat_cold_alerts.json"))
    bt = hc.get("by_type") or {}
    if hc.get("alerts"):
        lines.append(f"## 🔥/❄️ Heat / Cold Signals")
        lines.append(f"- Hot teams: **{bt.get('TEAM_HOT', 0)}** | Cold teams: **{bt.get('TEAM_COLD', 0)}** | Over-heavy: {bt.get('TEAM_HIGH_OVER', 0)} | Under-heavy: {bt.get('TEAM_LOW_OVER', 0)}")
        lines.append(f"- Heating-up players: **{bt.get('PLAYER_HEATING_UP', 0)}** | Cooling-down: {bt.get('PLAYER_COOLING_DOWN', 0)}")
        lines.append("")

    # Anomaly alerts
    anom = _load(os.path.join(DATA_DIR, "anomaly_alerts.json"))
    if anom.get("alerts"):
        lines.append(f"## ⚠️ Anomaly Detector ({anom.get('n_alerts', 0)})")
        for t, n in (anom.get("by_type") or {}).items():
            lines.append(f"- {t}: **{n}**")
        # Show top 5 anomalies
        for a in anom["alerts"][:5]:
            lines.append(f"  - {a['team']} ({a['sport']}): {a['detail']}")
        lines.append("")

    # Portfolio
    pf = _load(os.path.join(DATA_DIR, "portfolio_today.json"))
    if pf.get("picks"):
        lines.append(f"## 💰 Today's Portfolio ({pf.get('n_picks', 0)} picks)")
        lines.append(f"- Total stake: **${pf.get('total_stake_dollars', 0)}** ({pf.get('total_stake_pct', 0)}% of $1000 bankroll)")
        lines.append(f"- Expected EV: **${pf.get('expected_pl', 0)}**")
        for p in (pf.get("picks") or [])[:5]:
            lines.append(f"  - #{p['rank']} [{p['sport']}] ${p['stake_dollars']:.0f} on {p.get('label','')[:60]} (P={p['model_prob']*100:.0f}%)")
        lines.append("")

    # Self-training summary
    st = _load(os.path.join(DATA_DIR, "self_training_summary.json"))
    if st.get("by_sport"):
        lines.append(f"## 🤖 Self-Training Status")
        for sport, info in st["by_sport"].items():
            n = info.get("n_games", 0)
            hr = info.get("hit_rate")
            bias = info.get("bias")
            applied = info.get("recommendation_applied")
            applied_tag = " [calibration applied]" if applied else ""
            if hr is not None:
                lines.append(f"- **{sport.upper()}**: n={n} games · hit rate {hr*100:.1f}% · bias {(bias or 0)*100:+.1f}pp{applied_tag}")
        lines.append("")

    text = "\n".join(lines)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(text)

    n_sections = text.count("\n## ")
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "date": date,
        "n_sections": n_sections,
        "n_chars": len(text),
        "md_path": "data/daily_summary_v2.md",
    }
    with open(JSON_OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Daily summary v2: {p['n_sections']} sections, {p['n_chars']} chars")
