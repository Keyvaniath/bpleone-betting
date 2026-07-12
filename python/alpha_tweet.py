"""
EdgeStat -- daily Alpha Pick tweet generator.

Brandon wants to tweet the day's alpha pick every morning (~9am PT). This composes
the ready-to-post tweet from the SAME data the site shows, so what he posts always
matches the public record -- and it leads with that record for credibility.

It does NOT post anything (posting is a manual, human-in-the-loop action -- see the
"Post to X" one-tap intent link on alpha-pick.html, which opens X's composer
pre-filled so Brandon just taps Post). This module only WRITES the text.

Source of truth = data/alpha_pick_record.json:
  - todays        -> the day's One Pick (the tracked MLB alpha prop)
  - props_slate   -> the One Pick + 1-2 diversified extras (today's slate)
  - record        -> the public W-L / hit / ROI that gives the tweet its credibility

Output: data/alpha_tweet.json
  { generated_at, date, tweet, char_count, intent_url, picks:[...], record:{...},
    variants:{ short, with_props } }
"""
from __future__ import annotations

import os
import json
import urllib.parse
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REC = os.path.join(DATA_DIR, "alpha_pick_record.json")
OUT = os.path.join(DATA_DIR, "alpha_tweet.json")

SITE = "betting.bpleone.com/alpha-pick"
TWEET_MAX = 280


def _load(p) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _humanize_market(market: Any) -> str:
    """Turn a raw market code into human, tweet-friendly text."""
    m = str(market or "").strip()
    low = m.lower()
    table = {
        "3_plus_hrr": "3+ hits+runs+RBIs",
        "pp_batter_hrr_under_3.5": "under 3.5 hits+runs+RBIs",
        "pp_batter_hrr_under_4.5": "under 4.5 hits+runs+RBIs",
        "pp_batter_hrr_under_2.5": "under 2.5 hits+runs+RBIs",
        "1_plus_tb": "1+ total base",
        "to_record_hit_no": "to NOT record a hit",
        "to_record_hit_yes": "to record a hit",
        "to_hit_hr_yes": "to hit a home run",
        "to_score_run_no": "to NOT score a run",
        "hits_2plus_yes": "2+ hits",
        "k_1plus_yes": "1+ strikeout",
        "1_plus_hit": "1+ hit",
        "rbi_1plus_no": "under 1 RBI",
        "walk_1plus_yes": "1+ walk",
    }
    if low in table:
        return table[low]
    # generic prettify: strip PP_/batter_, underscores -> spaces
    pretty = (m.replace("PP_batter_", "").replace("pp_batter_", "")
              .replace("_", " ").strip())
    return pretty or m


def _odds(a: Any) -> str:
    try:
        a = int(a)
    except (TypeError, ValueError):
        return ""
    return f"+{a}" if a >= 0 else str(a)


def _pick_line(p: Dict[str, Any], lead: str = "") -> str:
    name = p.get("player_or_matchup") or "?"
    mk = _humanize_market(p.get("market"))
    od = _odds(p.get("fair_american"))
    prob = p.get("model_prob")
    tail = f" ({od})" if od else ""
    probtxt = f" · model {round(prob * 100)}%" if isinstance(prob, (int, float)) else ""
    return f"{lead}{name} — {mk}{tail}{probtxt}"


def _record_line(rec: Dict[str, Any]) -> str:
    w, l = rec.get("wins"), rec.get("losses")
    hr = rec.get("hit_rate")
    roi = rec.get("roi_pct")
    bits = []
    if w is not None and l is not None:
        bits.append(f"{w}-{l}")
    if isinstance(hr, (int, float)):
        bits.append(f"{round(hr * 100)}% hit")
    if isinstance(roi, (int, float)):
        bits.append(f"{'+' if roi >= 0 else ''}{round(roi)}% ROI")
    return " · ".join(bits)


def _compose(date: str, picks: List[Dict[str, Any]], rec: Dict[str, Any],
             include_props: bool) -> str:
    lines = ["\U0001F3AF Alpha Pick of the Day", ""]
    lines.append(_pick_line(picks[0]))
    if include_props and len(picks) > 1:
        for extra in picks[1:]:
            lines.append(_pick_line(extra, lead="+ "))
    lines.append("")
    rl = _record_line(rec)
    if rl:
        lines.append(f"Track record: {rl}")
        lines.append("Every pick public, graded on the box score.")
        lines.append("")
    lines.append(f"Full slate + receipts → {SITE}")
    lines.append("")
    lines.append("21+ · not betting advice")
    return "\n".join(lines)


def _intent(text: str) -> str:
    return "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(text, safe="")


def run() -> Dict[str, Any]:
    rec_data = _load(REC)
    record = rec_data.get("record") or {}
    slate = rec_data.get("props_slate") or {}
    todays_slate = (slate.get("todays") or {}).get("picks") or []
    one = rec_data.get("todays")

    # Prefer the full slate (One Pick + diversified props); fall back to the One Pick.
    if todays_slate:
        picks = todays_slate
        date = (slate.get("todays") or {}).get("date") or (one or {}).get("date")
    elif one:
        picks = [one]
        date = one.get("date")
    else:
        picks = []
        date = None

    if not picks:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "date": date, "tweet": None, "warning": "no alpha pick available today"}
        _write(payload)
        return payload

    # Compose: full (with props) if it fits, else short (One Pick only).
    full = _compose(date, picks, record, include_props=True)
    short = _compose(date, picks, record, include_props=False)
    tweet = full if len(full) <= TWEET_MAX else short
    if len(tweet) > TWEET_MAX:
        # last resort: drop the record continuity line
        tweet = tweet.replace("Every pick public, graded on the box score.\n", "")

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "date": date,
        "tweet": tweet,
        "char_count": len(tweet),
        "intent_url": _intent(tweet),
        "picks": [{"name": p.get("player_or_matchup"),
                   "market": _humanize_market(p.get("market")),
                   "odds": _odds(p.get("fair_american")),
                   "model_prob": p.get("model_prob")} for p in picks],
        "record": {"wins": record.get("wins"), "losses": record.get("losses"),
                   "hit_rate": record.get("hit_rate"), "roi_pct": record.get("roi_pct")},
        "variants": {
            "short": {"text": short, "char_count": len(short), "intent_url": _intent(short)},
            "with_props": {"text": full, "char_count": len(full), "intent_url": _intent(full)},
        },
        "note": ("Auto-composed from the live alpha record so the tweet always matches "
                 "the public numbers. Posting is manual: open intent_url (or tap 'Post "
                 "to X' on alpha-pick.html) to review + send. Nothing is posted "
                 "automatically."),
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys
    o = run()

    def _p(s):  # encoding-safe print (Windows console is cp1252)
        try:
            print(s)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((str(s) + "\n").encode("utf-8", "replace"))

    if o.get("tweet"):
        _p(f"[alpha-tweet] {o['date']} · {o['char_count']} chars")
        _p("-" * 50)
        _p(o["tweet"])
        _p("-" * 50)
    else:
        _p(f"[alpha-tweet] {o.get('warning')}")
