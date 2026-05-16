"""
EdgeStat -- Discord/Slack webhook notifier.

Posts a compact nightly digest of best bets + slate confidence + key alerts
to a configured Discord (or Slack) webhook. Reads webhook URL from env
DISCORD_WEBHOOK_URL or SLACK_WEBHOOK_URL.

Stubs gracefully when no webhook configured.
"""
from __future__ import annotations
import os, json, datetime as dt, urllib.request
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _build_message() -> str:
    bb = _load(os.path.join(DATA_DIR, "best_bets.json")).get("bets") or []
    slate = _load(os.path.join(DATA_DIR, "slate_confidence.json"))
    fatigue = _load(os.path.join(DATA_DIR, "pitcher_fatigue.json"))
    pf = _load(os.path.join(DATA_DIR, "portfolio.json"))

    lines = ["**EdgeStat -- nightly digest**"]
    if slate.get("score") is not None:
        lines.append(f"Slate confidence: **{slate['score']}/100 ({(slate.get('tier') or '?').upper()})** -- {slate.get('summary', '')}")
        lines.append(f"_{slate.get('recommendation', '')}_")
    if pf.get("n_picked"):
        lines.append(f"\nAuto-portfolio: {pf['n_picked']} picks, ${pf['total_stake']} stake ({pf['stake_pct_of_bankroll']}%), expected +${pf['expected_pl']}.")
    if bb:
        lines.append(f"\n**Top {min(5, len(bb))} best bets:**")
        for b in bb[:5]:
            lines.append(f"  - {b['label']}  ({b['quality_score']}/100, {b['stars']}*)")
    if fatigue.get("high_risk"):
        lines.append(f"\n**Pitcher fatigue HIGH-risk early hooks:** {', '.join(fatigue['high_risk'][:6])}")
    lines.append("\nhttps://betting.bpleone.com/best-bets.html")
    return "\n".join(lines)


def _post(url: str, content: str, kind: str) -> bool:
    if not url:
        return False
    try:
        payload = {"content": content} if kind == "discord" else {"text": content}
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception:
        return False


def run() -> Dict[str, Any]:
    msg = _build_message()
    discord = os.environ.get("DISCORD_WEBHOOK_URL")
    slack = os.environ.get("SLACK_WEBHOOK_URL")
    sent_discord = _post(discord, msg, "discord") if discord else False
    sent_slack = _post(slack, msg, "slack") if slack else False
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sent_discord": sent_discord, "sent_slack": sent_slack,
        "preview": msg,
    }


if __name__ == "__main__":
    p = run()
    print(f"Discord posted: {p['sent_discord']}")
    print(f"Slack posted:   {p['sent_slack']}")
    print("---")
    print(p["preview"])
