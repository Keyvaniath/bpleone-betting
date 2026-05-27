"""
EdgeStat -- Tonight's bet ticket markdown export.

Renders tonight_bet_ticket_master.json as a copy/paste-ready markdown
document for Discord or sharing.

Output: data/tonight_bet_ticket_master.md
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tonight_bet_ticket_master.md")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    ticket = _load(os.path.join(DATA_DIR, "tonight_bet_ticket_master.json"))

    if not ticket:
        return {"status": "no_data"}

    lines = []
    lines.append("# EdgeStat -- Tonight's Bet Ticket")
    lines.append(f"_Generated {ticket.get('generated_at') or dt.datetime.utcnow().isoformat(timespec='seconds')} UTC_")
    lines.append("")

    lines.append(f"**Slate Quality:** {ticket.get('slate_quality_tier')}")
    lines.append(f"**Total Stake:** {ticket.get('total_stake_pct_of_bankroll')}% bankroll")
    if ticket.get("expected_pl_on_100_bankroll") is not None:
        lines.append(f"**Expected P&L (on $100):** ${ticket.get('expected_pl_on_100_bankroll')}")
    lines.append("")

    tickets = ticket.get("tickets") or []

    # Separate by type
    locks = [t for t in tickets if t.get("type") == "LOCK_OF_NIGHT"]
    singles = [t for t in tickets if str(t.get("type", "")).startswith("SINGLE_")]
    parlays = [t for t in tickets if str(t.get("type", "")).startswith("PARLAY_")]
    anchors = [t for t in tickets if t.get("type") == "ANCHOR_STACK"]

    if locks:
        lines.append("## LOCK OF THE NIGHT")
        for t in locks:
            lines.append(f"- **{t.get('subject')}** ({t.get('source')}, {t.get('sport')})")
            lines.append(f"  - Stake: {t.get('stake_pct_of_bankroll')}% bankroll")
        lines.append("")

    if singles:
        lines.append("## SINGLES (Top 5 Curated)")
        for t in singles:
            lines.append(f"{t.get('type').split('_')[1]}. **{t.get('subject')}** ({t.get('sport')})")
            if t.get("play"):
                lines.append(f"   - Play: {t.get('play')}")
            lines.append(f"   - Stake: {t.get('stake_pct_of_bankroll')}% bankroll")
        lines.append("")

    if parlays:
        lines.append("## PARLAYS (Top 3)")
        for t in parlays:
            lines.append(f"{t.get('type').split('_')[1]}. **{t.get('subject')}** "
                         f"({t.get('sport')}, {t.get('n_legs')} legs)")
            lines.append(f"   - Parlay p: {t.get('parlay_p')}")
            lines.append(f"   - Stake: {t.get('stake_pct_of_bankroll')}% bankroll")
        lines.append("")

    if anchors:
        lines.append("## ANCHOR STACK")
        for t in anchors:
            lines.append(f"- Tier: {t.get('tier')}, Legs: {t.get('n_legs')}")
            for leg in (t.get("legs") or [])[:4]:
                lines.append(f"  - Leg {leg.get('leg_n')}: {leg.get('entity')} "
                             f"({leg.get('source')}) — {leg.get('recommended_market')}")
            lines.append(f"  - Stake: {t.get('stake_pct_of_bankroll')}% bankroll")
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
    print(f"[bet-ticket-md] wrote {o.get('bytes_written', 0)} bytes -> {OUT}")
