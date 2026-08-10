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
    # the calibrated prob is the honest number when the record carries one (v2 picks)
    prob = p.get("model_prob_calibrated")
    if not isinstance(prob, (int, float)):
        prob = p.get("model_prob")
    tail = f" ({od})" if od else ""
    probtxt = f" · model {round(prob * 100)}%" if isinstance(prob, (int, float)) else ""
    m = str(p.get("market") or "").upper()
    if m in ("ML_HOME", "ML_AWAY") and "@" in name:
        away, _, home = [s.strip() for s in name.partition("@")]
        side = home if m == "ML_HOME" else away
        return f"{lead}{side} moneyline ({name}){tail}{probtxt}"
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


def _yesterday_receipt(history: List[Dict[str, Any]], today: Optional[str]) -> Optional[str]:
    """The most recent GRADED pick before today, as a one-line receipt.
    Wins AND losses both post -- the receipts-every-day habit IS the brand;
    an account that only surfaces wins reads as a tout."""
    for h in history or []:   # history is newest-first
        if today and h.get("date") == today:
            continue
        res = h.get("result")
        if res not in ("won", "lost"):
            continue
        mark = "✅" if res == "won" else "❌"
        pu = h.get("payout_units")
        put = f" {'+' if (pu or 0) >= 0 else ''}{round(pu, 2)}u" if isinstance(pu, (int, float)) else ""
        name = h.get("player_or_matchup") or "?"
        # Label honestly: "Yesterday" only when the receipt IS yesterday's slate.
        # After a settlement gap, an 8-day-old result billed as "Yesterday" reads
        # as a fresh receipt -- that's a tout move. Date it instead.
        lead = "Yesterday"
        try:
            gap = (dt.date.fromisoformat(today) - dt.date.fromisoformat(h.get("date"))).days
            if gap > 1:
                d0 = dt.date.fromisoformat(h.get("date"))
                lead = f"{d0.month}/{d0.day}"
        except (TypeError, ValueError):
            pass
        m = str(h.get("market") or "").upper()
        if m in ("ML_HOME", "ML_AWAY") and "@" in name:
            away, _, home = [s.strip() for s in name.partition("@")]
            side = home if m == "ML_HOME" else away
            return f"{lead}: {side} moneyline ({name}) {mark}{put}"
        mk = _humanize_market(h.get("market"))
        return f"{lead}: {name} {mk} {mark}{put}"
    return None


def _compose(date: str, picks: List[Dict[str, Any]], rec: Dict[str, Any],
             include_props: bool, receipt: Optional[str] = None,
             terse: bool = False) -> str:
    lines = ["\U0001F3AF Alpha Pick of the Day", ""]
    lines.append(_pick_line(picks[0]))
    if include_props and len(picks) > 1:
        for extra in picks[1:]:
            lines.append(_pick_line(extra, lead="+ "))
    lines.append("")
    if receipt:
        lines.append(receipt)
    rl = _record_line(rec)
    if rl:
        lines.append(f"Record: {rl}" + ("" if terse else " — every pick public, graded on the box score."))
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
        # v2 NO-PICK day: nothing cleared the curation/edge gate. That's a real,
        # postable message -- "we don't force bets" is the brand working, not a
        # gap in it -- and the receipt + record still ride along.
        if (one or {}).get("no_pick"):
            date = one.get("date")
            receipt = _yesterday_receipt(rec_data.get("history") or [], date)
            lines = ["\U0001F3AF Alpha Pick of the Day", "",
                     "No pick today. Nothing on the slate clears our edge gate, "
                     "and we don't force bets.", ""]
            if receipt:
                lines.append(receipt)
            rl = _record_line(record)
            if rl:
                lines.append(f"Record: {rl}")
            lines += ["", f"Receipts → {SITE}", "", "21+ · not betting advice"]
            tweet = "\n".join(lines)
            payload = {
                "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "date": date, "no_pick": True,
                "tweet": tweet, "char_count": len(tweet),
                "intent_url": _intent(tweet), "receipt": receipt, "picks": [],
                "record": {"wins": record.get("wins"), "losses": record.get("losses"),
                           "hit_rate": record.get("hit_rate"), "roi_pct": record.get("roi_pct")},
                "variants": {"bare": {"text": tweet, "char_count": len(tweet),
                                      "intent_url": _intent(tweet)}},
                "note": "No-pick day: the gate found no qualifying edge. Posting is manual.",
            }
            _write(payload)
            return payload
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "date": date, "tweet": None, "warning": "no alpha pick available today"}
        _write(payload)
        return payload

    # Yesterday's graded result (win OR loss) -- the daily receipt that builds trust.
    receipt = _yesterday_receipt(rec_data.get("history") or [], date)

    # Compose, slimming in priority order. The RECEIPT is the proof and outranks
    # the tagline: props go first, then the tagline, then (only if still over)
    # the receipt itself.
    candidates = [
        _compose(date, picks, record, include_props=True, receipt=receipt),
        _compose(date, picks, record, include_props=False, receipt=receipt),
        _compose(date, picks, record, include_props=True, receipt=receipt, terse=True),
        _compose(date, picks, record, include_props=False, receipt=receipt, terse=True),
        _compose(date, picks, record, include_props=False, receipt=None, terse=True),
    ]
    tweet = next((c for c in candidates if len(c) <= TWEET_MAX), candidates[-1])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "date": date,
        "tweet": tweet,
        "char_count": len(tweet),
        "intent_url": _intent(tweet),
        "receipt": receipt,
        "picks": [{"name": p.get("player_or_matchup"),
                   "market": _humanize_market(p.get("market")),
                   "odds": _odds(p.get("fair_american")),
                   "model_prob": p.get("model_prob")} for p in picks],
        "record": {"wins": record.get("wins"), "losses": record.get("losses"),
                   "hit_rate": record.get("hit_rate"), "roi_pct": record.get("roi_pct")},
        "variants": {
            "with_props": {"text": candidates[0], "char_count": len(candidates[0]), "intent_url": _intent(candidates[0])},
            "short": {"text": candidates[1], "char_count": len(candidates[1]), "intent_url": _intent(candidates[1])},
            "bare": {"text": candidates[-1], "char_count": len(candidates[-1]), "intent_url": _intent(candidates[-1])},
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
