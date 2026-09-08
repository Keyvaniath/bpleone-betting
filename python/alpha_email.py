"""
EdgeStat -- the daily Alpha Pick EMAIL.

Composes an email-safe version of the day's Alpha pick (or honest no-pick)
from the same live artifacts the tweet uses, so the inbox and the site never
disagree: subject line, plain-text body, and a table-layout HTML body with
inline styles that survives Gmail / Outlook / Apple Mail.

Outputs (every pipeline run, after alpha_tweet):
  data/alpha_email.json              {date, subject, text, html, mailto}
  emails/alpha-daily-<date>.html     the rendered email (a shareable proof)
  emails/latest.html                 same, stable URL for the site's preview link

SENDING IS A HUMAN ACTION. This module never sends to a list or a subscriber.
The one exception is an opt-in notification TO THE OWNER'S OWN INBOX: when the
repo secrets ALPHA_EMAIL_TO / SMTP_USER / SMTP_PASS are present, `--send-self`
mails the digest to that single address so it lands in the morning inbox.
Without those secrets it composes, prints, and exits.
"""
from __future__ import annotations

import os
import json
import html
import datetime as dt
import urllib.parse
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
EMAIL_DIR = os.path.join(os.path.dirname(__file__), "..", "emails")
SITE = "https://betting.bpleone.com"
OUT = os.path.join(DATA_DIR, "alpha_email.json")
FONT = "-apple-system,Segoe UI,Roboto,Arial,sans-serif"
MONO = "'JetBrains Mono',Menlo,Consolas,monospace"


def _load(p: str) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _pct(x) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def _odds(a) -> str:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return "—"
    return f"+{a}" if a > 0 else str(a)


def _mk_human(market: Any, name: Any) -> str:
    m = str(market or "").upper()
    nm = str(name or "")
    if m in ("ML_HOME", "ML_AWAY") and "@" in nm:
        a, _, h = nm.partition("@")
        return (h if m == "ML_HOME" else a).strip() + " moneyline"
    if m.endswith("_ML"):
        return m[:-3] + " moneyline"
    return m.replace("_", " ").lower()


def compose() -> Dict[str, Any]:
    tw = _load(os.path.join(DATA_DIR, "alpha_tweet.json"))
    rec = _load(os.path.join(DATA_DIR, "alpha_pick_record.json"))
    today = rec.get("todays") or {}
    date = today.get("date") or tw.get("date") or dt.date.today().isoformat()
    record = rec.get("record") or {}
    v2 = rec.get("record_v2") or {}
    receipt = tw.get("receipt") or ""
    why = today.get("why") or {}
    no_pick = bool(today.get("no_pick"))

    if no_pick:
        subject = f"Alpha Pick {date}: no play today (we don't force bets)"
        headline = "No pick today."
        sub = ("Nothing on the slate cleared the v2 gate — a family with a real "
               "settled record and calibrated EV ≥ +2%. Posting nothing beats "
               "manufacturing a play.")
    else:
        head_txt = _mk_human(today.get("market"), today.get("player_or_matchup"))
        is_ml = "moneyline" in head_txt
        headline = (head_txt if is_ml else str(today.get("player_or_matchup") or ""))
        if today.get("fair_american") is not None:
            headline += f" @ {_odds(today.get('fair_american'))}"
        sub = (f"({today.get('player_or_matchup')})" if is_ml else head_txt)
        prob = today.get("model_prob_calibrated") or today.get("model_prob")
        subject = f"Alpha Pick {date}: {headline}"
        if prob:
            subject += f" · model {round(prob * 100)}%"

    roi = record.get("roi_pct") or 0
    rec_line = (f"Record: {record.get('wins', 0)}-{record.get('losses', 0)} · "
                f"{round((record.get('hit_rate') or 0) * 100)}% hit · "
                f"{'+' if roi >= 0 else ''}{roi}% ROI")
    v2_line = ""
    if v2:
        nu = v2.get("net_units") or 0
        v2_line = (f"Rule v2 (since 2026-08-10): {v2.get('wins', 0)}-{v2.get('losses', 0)}, "
                   f"{'+' if nu >= 0 else ''}{nu}u")

    # ---- plain text ----
    lines = [f"EdgeStat — Alpha Pick of the Day · {date}", "", headline, sub]
    if not no_pick and why:
        fam = ""
        if why.get("family"):
            fam = (f" ({why.get('family')} family, n={why.get('family_n_settled')}, "
                   f"realized {_pct(why.get('family_realized'))})")
        lines += ["", "Why:",
                  f"  model raw {_pct(why.get('raw_prob'))} → calibrated "
                  f"{_pct(why.get('calibrated_prob'))}{fam}",
                  f"  book implies {_pct(why.get('implied_prob_at_odds'))} → "
                  f"calibrated edge +{why.get('edge_pct')}%"]
    if receipt:
        lines += ["", receipt]
    lines += ["", rec_line]
    if v2_line:
        lines.append(v2_line)
    lines += ["", f"Full slate, why-chain and receipts: {SITE}/alpha-pick.html",
              f"Every pick public, graded on the box score: {SITE}/track-record.html",
              "", "21+ · informational only · not betting advice"]
    text = "\n".join(lines)

    # ---- email-safe HTML (tables + inline styles) ----
    E = html.escape
    why_html = ""
    if not no_pick and why:
        fam = ""
        if why.get("family"):
            fam = (f" against the <b>{E(str(why.get('family')))}</b> family's real settled record "
                   f"(n={why.get('family_n_settled')}, realized {_pct(why.get('family_realized'))})")
        why_html = (
            f'<tr><td style="padding:14px 22px 0;font:13px/1.65 {FONT};color:#9fb0c8;">'
            f'<div style="font-size:10px;letter-spacing:.6px;text-transform:uppercase;color:#7b8598;margin-bottom:4px;">Why this pick</div>'
            f'Model raw <b style="color:#e8eef7;">{_pct(why.get("raw_prob"))}</b> → calibrated '
            f'<b style="color:#e8eef7;">{_pct(why.get("calibrated_prob"))}</b>{fam}. '
            f'The book implies <b style="color:#e8eef7;">{_pct(why.get("implied_prob_at_odds"))}</b> → '
            f'calibrated edge <b style="color:#58c878;">+{why.get("edge_pct")}%</b> clears the +2% v2 bar.'
            f'</td></tr>')
    receipt_html = ""
    if receipt:
        receipt_html = (f'<tr><td style="padding:14px 22px 0;font:13px/1.6 {FONT};color:#9fb0c8;">'
                        f'{E(receipt)}</td></tr>')
    head_color = "#d4a04a" if no_pick else "#e8eef7"
    star = "" if no_pick else "★ "
    v2_html = f"<br>{E(v2_line)}" if v2_line else ""
    html_body = (
        '<!doctype html><html><body style="margin:0;padding:0;background:#0b0d12;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b0d12;">'
        '<tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="max-width:560px;background:#12161f;border:1px solid #232a37;border-radius:14px;">'
        f'<tr><td style="padding:18px 22px 6px;font:700 15px {FONT};color:#e8eef7;">'
        '<span style="color:#d4a04a;">⟁</span> Edge<span style="color:#d4a04a;">Stat</span>'
        f'<span style="font-weight:400;color:#7b8598;font-size:12px;"> · Alpha Pick of the Day · {E(date)}</span></td></tr>'
        f'<tr><td style="padding:10px 22px 0;font:800 22px/1.25 {FONT};color:{head_color};">{star}{E(headline)}</td></tr>'
        f'<tr><td style="padding:4px 22px 0;font:14px/1.5 {FONT};color:#9fb0c8;">{E(sub)}</td></tr>'
        f'{why_html}{receipt_html}'
        f'<tr><td style="padding:16px 22px 0;font:12.5px/1.6 {MONO};color:#b9c3d4;">{E(rec_line)}{v2_html}</td></tr>'
        f'<tr><td style="padding:18px 22px 6px;"><a href="{SITE}/alpha-pick.html" '
        f'style="display:inline-block;background:#d4a04a;color:#0b0d12;font:700 13px {FONT};text-decoration:none;padding:11px 18px;border-radius:9px;">Full slate + receipts →</a>'
        f'<a href="{SITE}/track-record.html" style="display:inline-block;margin-left:10px;color:#7fb0e8;font:13px {FONT};text-decoration:none;">public track record</a></td></tr>'
        f'<tr><td style="padding:12px 22px 18px;font:11px/1.6 {FONT};color:#6f7889;">Every pick is public and graded on the box score — losses post too. '
        '21+ · informational only · not betting advice. Gambling problem? 1-800-GAMBLER.</td></tr>'
        '</table></td></tr></table></body></html>')

    mailto = "mailto:?" + urllib.parse.urlencode({"subject": subject, "body": text},
                                                  quote_via=urllib.parse.quote)
    payload = {
        "date": date,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "subject": subject, "text": text, "html": html_body, "mailto": mailto,
        "no_pick": no_pick,
        "note": ("Composed from alpha_pick_record + alpha_tweet every run. Sending is a "
                 "human action; --send-self delivers ONLY to the owner's inbox when SMTP "
                 "secrets are set."),
    }
    os.makedirs(EMAIL_DIR, exist_ok=True)
    with open(os.path.join(EMAIL_DIR, f"alpha-daily-{date}.html"), "w", encoding="utf-8") as f:
        f.write(html_body)
    with open(os.path.join(EMAIL_DIR, "latest.html"), "w", encoding="utf-8") as f:
        f.write(html_body)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


def send_self(payload: Dict[str, Any]) -> bool:
    """Owner-only morning notification. Silent no-op without the secrets."""
    to = os.environ.get("ALPHA_EMAIL_TO", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    pw = os.environ.get("SMTP_PASS", "").strip()
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    if not (to and user and pw):
        print("[alpha-email] no ALPHA_EMAIL_TO/SMTP_USER/SMTP_PASS -- composed only, not sent")
        return False
    if "," in to or ";" in to:
        print("[alpha-email] refusing: ALPHA_EMAIL_TO must be ONE address (owner notification only)")
        return False
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    msg = MIMEMultipart("alternative")
    msg["Subject"] = payload["subject"]
    msg["From"] = user
    msg["To"] = to
    msg.attach(MIMEText(payload["text"], "plain", "utf-8"))
    msg.attach(MIMEText(payload["html"], "html", "utf-8"))
    with smtplib.SMTP_SSL(host, 465, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    print(f"[alpha-email] sent to owner inbox ({to})")
    return True


if __name__ == "__main__":
    import sys
    p = compose()
    print(f"[alpha-email] {p['date']} | {p['subject']}")
    if "--send-self" in sys.argv:
        send_self(p)
