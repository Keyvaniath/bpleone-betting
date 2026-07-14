"""
EdgeStat -- weekly receipts thread composer.

The weekly growth play for the X channel: one thread, every Alpha Pick from the
trailing 7 days, graded ✅/❌ with units -- wins AND losses (the losses are what
make the record believable). Composed from the SAME public ledger the site
shows, so the thread can never disagree with the receipts page.

Regenerates on every pipeline run (rolling window), so whenever Brandon wants to
post -- typically Sunday/Monday -- the thread is already drafted. Posting stays
MANUAL: tweet 1 goes out via the intent link / copy button; replies 2..N are
pasted as replies to build the thread.

Input : data/alpha_pick_record.json  (history: newest-first graded picks)
Output: data/weekly_thread.json     {tweets:[{n,text,char_count}], intent_url,
                                     week: {wins,losses,net_units}, note}
"""
from __future__ import annotations

import os
import json
import urllib.parse
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REC = os.path.join(DATA_DIR, "alpha_pick_record.json")
OUT = os.path.join(DATA_DIR, "weekly_thread.json")

SITE = "betting.bpleone.com/alpha-pick"
TWEET_MAX = 280
WINDOW_DAYS = 7

_MARKETS = {
    "3_plus_hrr": "3+ HRR",
    "pp_batter_hrr_under_3.5": "under 3.5 HRR",
    "pp_batter_hrr_under_4.5": "under 4.5 HRR",
    "pp_batter_hrr_under_2.5": "under 2.5 HRR",
    "to_record_hit_no": "no hit",
    "to_record_hit_yes": "to record a hit",
    "hits_2plus_yes": "2+ hits",
    "1_plus_hit": "1+ hit",
    "k_1plus_yes": "1+ K",
}


def _load(p) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _mk(market: Any) -> str:
    m = str(market or "")
    return _MARKETS.get(m.lower(), m.replace("PP_batter_", "").replace("_", " ").strip())


def _dow(date_str: str) -> str:
    try:
        return dt.date.fromisoformat(date_str).strftime("%a %-m/%-d") if os.name != "nt" \
            else dt.date.fromisoformat(date_str).strftime("%a %m/%d").replace(" 0", " ").lstrip("0")
    except Exception:
        return date_str


def _line(h: Dict[str, Any]) -> str:
    mark = "✅" if h.get("result") == "won" else "❌"
    pu = h.get("payout_units")
    put = f" {'+' if (pu or 0) >= 0 else ''}{round(pu, 2)}u" if isinstance(pu, (int, float)) else ""
    return f"{_dow(h.get('date') or '')} — {h.get('player_or_matchup') or '?'} {_mk(h.get('market'))} {mark}{put}"


def run() -> Dict[str, Any]:
    rec_data = _load(REC)
    record = rec_data.get("record") or {}
    today = dt.date.today()

    graded: List[Dict[str, Any]] = []
    for h in rec_data.get("history") or []:      # newest-first
        if h.get("result") not in ("won", "lost"):
            continue
        try:
            if (today - dt.date.fromisoformat(h.get("date") or "")).days > WINDOW_DAYS:
                continue
        except Exception:
            continue
        graded.append(h)

    if not graded:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "tweets": [], "warning": "no graded picks in the trailing week"}
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return payload

    graded_chrono = list(reversed(graded))       # oldest-first for the thread
    wins = sum(1 for h in graded if h.get("result") == "won")
    losses = len(graded) - wins
    net = round(sum(h.get("payout_units") or 0 for h in graded), 2)
    mood = "📈" if net >= 0 else "📉"

    # T1 — the hook (posted via intent link; replies build the thread)
    t1 = (f"{mood} Week in review — every Alpha Pick we posted, graded on the box score:\n\n"
          f"{wins}-{losses} · {'+' if net >= 0 else ''}{net}u (1u flat)\n\n"
          f"Wins AND losses below. No deletes, no cherry-picks. 🧵")

    # Middle tweets — the day-by-day receipts, packed under 280 each
    tweets: List[str] = [t1]
    block: List[str] = []
    for h in graded_chrono:
        line = _line(h)
        candidate = "\n".join(block + [line])
        if len(candidate) > TWEET_MAX - 10 and block:
            tweets.append("\n".join(block))
            block = [line]
        else:
            block.append(line)
    if block:
        tweets.append("\n".join(block))

    # Closer — running record + link + compliance
    w, l = record.get("wins"), record.get("losses")
    roi = record.get("roi_pct")
    closer = (f"Running record: {w}-{l}"
              + (f" · {'+' if (roi or 0) >= 0 else ''}{round(roi)}% ROI" if isinstance(roi, (int, float)) else "")
              + f"\n\nEvery pick, settled in a public ledger → {SITE}\n\n21+ · not betting advice")
    tweets.append(closer)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "week": {"wins": wins, "losses": losses, "net_units": net,
                 "first_date": graded_chrono[0].get("date"), "last_date": graded_chrono[-1].get("date")},
        "tweets": [{"n": i + 1, "text": t, "char_count": len(t)} for i, t in enumerate(tweets)],
        "intent_url": "https://twitter.com/intent/tweet?text=" + urllib.parse.quote(t1, safe=""),
        "note": ("Rolling trailing-week thread, regenerated每 pipeline run. Post tweet 1 "
                 "via intent_url, then paste tweets 2..N as replies. Losses are included "
                 "by design -- never trim them."),
    }
    # fix accidental unicode in note
    payload["note"] = payload["note"].replace("每", "every ")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


if __name__ == "__main__":
    import sys
    o = run()

    def _p(s):
        try:
            print(s)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((str(s) + "\n").encode("utf-8", "replace"))

    if o.get("tweets"):
        wk = o["week"]
        _p(f"[weekly-thread] {len(o['tweets'])} tweets · week {wk['wins']}-{wk['losses']} ({wk['net_units']:+}u)")
        for t in o["tweets"]:
            _p("-" * 46)
            _p(t["text"])
    else:
        _p(f"[weekly-thread] {o.get('warning')}")
