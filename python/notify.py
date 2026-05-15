"""
EdgeStat -- daily notification dispatcher.

Sends today's brief to channels Brandon has configured via env vars:
  - DISCORD_WEBHOOK_URL: a Discord channel incoming webhook URL
  - SLACK_WEBHOOK_URL:   a Slack incoming webhook URL

If neither is set, this module is a no-op (logs and exits).

Setup:
  1. Discord: server settings -> Integrations -> Webhooks -> New Webhook ->
     copy URL -> add to GitHub Actions secrets as DISCORD_WEBHOOK_URL
  2. Slack: api.slack.com/apps -> Create App -> Incoming Webhooks -> create
     -> copy URL -> add to GitHub Actions secrets as SLACK_WEBHOOK_URL

Runs once per morning cron after daily_summary.py.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def build_compact_message() -> str:
    """Build a compact summary suitable for chat embeds. ~1500 chars max."""
    today = _load("today.json")
    pickem = _load("pickem.json")
    tr = _load("track_record.json")

    date = (today.get("generated_at") or "")[:10] or dt.date.today().isoformat()
    pod = today.get("play_of_day") or {}
    parts = [f"**EdgeStat Daily Brief - {date}**", ""]

    if pod:
        is_precal = (pod.get("edge_pct") or 0) >= 15
        precal_tag = " _(model in calibration)_" if is_precal else ""
        parts.append(f"**Play of the Day:** {pod['matchup']} - **{pod['label']}**{precal_tag}")
        parts.append(f"  Market: {pod['market_price'] >= 0 and '+' + str(pod['market_price']) or pod['market_price']} | "
                     f"Model: {pod['model_prob']*100:.1f}% | "
                     f"Edge: +{pod['edge_pct']}% | "
                     f"Stake: {'<= 0.5u' if is_precal else f'{pod['kelly_units']}u'}")
        parts.append("")

    # Slate count
    games = today.get("games") or []
    if games:
        parts.append(f"**Slate:** {len(games)} games modeled")

    # Top edges from games (capped to sane levels)
    actionable = []
    for g in games:
        recs = sorted(g.get("recommendations") or [], key=lambda r: -(r.get("edge_pct") or 0))
        if recs and 3 <= (recs[0].get("edge_pct") or 0) < 20:
            actionable.append(f"  {g['matchup']} {recs[0]['label']} +{recs[0]['edge_pct']}%")
    if actionable:
        parts.append("**Tonight's Edges (3-20% band):**")
        parts.extend(actionable[:6])
        parts.append("")

    # PP softer than DK
    softer = [p for p in (pickem.get("props") or []) if p.get("pp_advantage")]
    if softer:
        parts.append(f"**PrizePicks soft lines ({len(softer)} total):**")
        for p in softer[:4]:
            best = max(p.get("model_prob_over") or 0.5, p.get("model_prob_under") or 0.5)
            parts.append(f"  {p['player']} {p['stat_type']} {p['pp_softer_for']} PP {p['pp_line']} "
                         f"(DK {p['dk_line']}, model {best*100:.1f}%)")
        parts.append("")

    # Track record snippet
    props_settled = sum(1 for p in (tr.get('props') or []) if p.get('play_hit') is not None)
    if props_settled:
        wins = sum(1 for p in (tr.get('props') or []) if p.get('play_hit') is True)
        parts.append(f"**Live track record:** {props_settled} graded, {wins} wins, "
                     f"{wins/props_settled*100:.1f}% hit rate.")

    parts.append("")
    parts.append("Full breakdown: https://betting.bpleone.com")
    parts.append("Bet responsibly. 21+. 1-800-GAMBLER.")
    return "\n".join(parts)


def post_discord(message: str) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url or requests is None:
        return False
    # Discord embeds support markdown; the content field also works.
    payload = {
        "content": message[:1900],   # Discord 2000-char content limit
        "username": "EdgeStat",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.ok
    except Exception:
        return False


def post_slack(message: str) -> bool:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url or requests is None:
        return False
    try:
        r = requests.post(url, json={"text": message}, timeout=10)
        return r.ok
    except Exception:
        return False


def run() -> None:
    msg = build_compact_message()
    sent = []
    if post_discord(msg): sent.append("discord")
    if post_slack(msg): sent.append("slack")
    if sent:
        print(f"Sent to: {', '.join(sent)}")
    else:
        print("No webhook configured (set DISCORD_WEBHOOK_URL or SLACK_WEBHOOK_URL). Preview:")
        print("-" * 60)
        print(msg[:600])
        if len(msg) > 600:
            print(f"... ({len(msg) - 600} more chars)")


if __name__ == "__main__":
    run()
