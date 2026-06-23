"""
ODDS_API_KEY preflight / readiness -> data/odds_key_status.json

The paid The Odds API key is the one structural unlock left: it lights up player-prop
BOOK lines (DraftKings / 8-book), the book-vs-PrizePicks +EV edges (pp_advantage), and
prop CLV confirmed against a real sharp close. The consuming code is already wired and
gated -- the moment the GitHub secret ODDS_API_KEY is set, the next pipeline run starts
using it. This module makes that activation OBSERVABLE and SELF-VALIDATING:

  - key not set  -> status "dormant", lists exactly what will activate.
  - key set      -> one FREE validation call to /v4/sports (does not cost quota):
                      200 -> "active" (key valid, feed live)
                      401 -> "invalid" (bad/expired key -- caught immediately, not
                             silently ignored).

So flipping the secret instantly flips the public status from dormant to active, and a
typo'd key surfaces on the next run instead of failing quietly. status.html renders it.
"""
import json
import os
import datetime
import urllib.request
import urllib.error

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "odds_key_status.json")
# /v4/sports is the documented free endpoint -- it validates the key WITHOUT spending
# a request from the monthly quota, so running this preflight 3x/day costs nothing.
VALIDATE_URL = "https://api.the-odds-api.com/v4/sports/?apiKey={}"
# A valid key with a near-empty monthly quota still can't fetch props, so report that
# distinctly instead of a misleading "active". Each odds/props pull costs requests.
LOW_QUOTA = 100   # warn below this
EXHAUSTED = 5     # effectively unusable at/below this

ACTIVATES = [
    "Player-prop BOOK lines (DraftKings / 8-book via The Odds API) -- the paid cross-check",
    "pp_advantage: book-vs-PrizePicks +EV edges (currently dormant)",
    "Prop CLV confirmed against a real sharp book close (sharpens prop_clv beyond PrizePicks-only)",
    "book_vs_model on the full paid multi-book feed (vs the free ESPN game lines today)",
]


def _validate(key):
    """Return (state, detail). Network-light: one free /v4/sports call."""
    try:
        req = urllib.request.Request(VALIDATE_URL.format(key),
                                     headers={"User-Agent": "EdgeStat-preflight/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                try:
                    n = len(json.loads(r.read().decode("utf-8")))
                except Exception:
                    n = None
                rem = r.headers.get("x-requests-remaining")
                return "active", {"sports_listed": n, "requests_remaining": rem}
            return "unknown", {"http_status": r.status}
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "invalid", {"http_status": 401, "hint": "key rejected -- check for a typo or an expired/lapsed plan"}
        return "unknown", {"http_status": e.code}
    except Exception as e:
        return "unknown", {"error": str(e)[:120]}


def build():
    key = os.environ.get("ODDS_API_KEY", "").strip()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    if not key:
        return {
            "checked_at": now,
            "key_set": False,
            "state": "dormant",
            "headline": "Odds feed DORMANT -- set the ODDS_API_KEY GitHub secret to activate.",
            "activates": ACTIVATES,
            "note": "Game-line odds + game-line CLV already run free via ESPN; only the "
                    "player-prop BOOK feed and the edges/CLV that depend on it are dormant.",
        }
    state, detail = _validate(key)
    # A valid key with a near-empty quota can't actually fetch props -- surface that as
    # its own state so it isn't mistaken for a healthy "active" feed. The real blocker
    # then reads as quota (bump the plan tier), NOT a missing key.
    rem = detail.get("requests_remaining")
    rem_int = int(rem) if (rem is not None and str(rem).lstrip("-").isdigit()) else None
    if state == "active" and rem_int is not None:
        if rem_int <= EXHAUSTED:
            state = "exhausted"
        elif rem_int <= LOW_QUOTA:
            state = "low_quota"
    headline = {
        "active": "Odds feed ACTIVE -- paid key validated, player-prop book feed is live.",
        "low_quota": "Odds key VALID but quota running low ({} requests left this month) -- "
                     "prop fetches stop when it hits 0.".format(rem_int),
        "exhausted": "Odds key VALID but quota EXHAUSTED ({} left) -- the key works, there's just "
                     "no request budget to fetch props. Raise the plan tier (or cut fetch "
                     "frequency); you do NOT need a new key.".format(rem_int),
        "invalid": "Odds key INVALID -- the secret is set but rejected by the API (check the key).",
        "unknown": "Odds key set -- validation call did not confirm (network/API hiccup); will recheck next run.",
    }.get(state, "Odds key set.")
    return {
        "checked_at": now,
        "key_set": True,
        "state": state,
        "requests_remaining": rem_int,
        "headline": headline,
        "detail": detail,
        "activates": ACTIVATES,
    }


def write_artifact():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = write_artifact()
    print(f"Wrote {OUT}")
    print(f"  key_set={p['key_set']} state={p['state']} -- {p['headline']}")
