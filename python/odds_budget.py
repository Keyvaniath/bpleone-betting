"""
The Odds API request-budget guard.

The paid key has a finite monthly quota (each /odds call costs ~1 request per market
x region; per-event prop fetches multiply fast). Broad 3x/day fetching burned a free
500/mo tier down to ~0 in days -- exactly what odds_key_status.json shows. This gates
every paid call so the budget is spent deliberately:

  should_fetch(cost) -> False when
    * remaining monthly quota (from odds_key_preflight) would drop below RESERVE, or
    * today's recorded spend + cost would exceed the daily cap (env ODDS_DAILY_CAP).

A skipped caller returns its empty value and falls back to the FREE ESPN game lines --
the same graceful path as when no key is set -- so this guard can only conservatively
SKIP a fetch, never break a working one. record_spend(cost) logs per-day usage to
data/odds_spend_log.json.

Tune the daily cap to your plan tier (env ODDS_DAILY_CAP): free 500/mo ~= 16/day;
a paid 100k/mo tier ~= 3,000/day. RESERVE always protects the monthly pool regardless.
"""
import json
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
STATUS_PATH = os.path.join(DATA_DIR, "odds_key_status.json")
SPEND_PATH = os.path.join(DATA_DIR, "odds_spend_log.json")

RESERVE = 10                                              # never let monthly quota dip below this
DAILY_CAP = int(os.environ.get("ODDS_DAILY_CAP", "40"))  # max paid requests per day


def _load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def remaining_quota():
    """Monthly requests remaining per the last preflight (int), or None if unknown."""
    d = _load(STATUS_PATH)
    r = d.get("requests_remaining")
    if r is None:
        r = (d.get("detail") or {}).get("requests_remaining")
    try:
        return int(r)
    except (TypeError, ValueError):
        return None


def _today():
    return datetime.date.today().isoformat()


def today_spent():
    return int(_load(SPEND_PATH).get(_today(), 0) or 0)


def should_fetch(cost=1):
    """True only if this paid call fits BOTH the monthly reserve and the daily cap."""
    rem = remaining_quota()
    if rem is not None and (rem - cost) < RESERVE:
        return False
    if today_spent() + cost > DAILY_CAP:
        return False
    return True


def record_spend(cost=1):
    log = _load(SPEND_PATH)
    today = _today()
    log[today] = int(log.get(today, 0) or 0) + int(cost)
    for k in sorted(log.keys())[:-10]:   # keep ~10 days
        log.pop(k, None)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SPEND_PATH, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass


def status():
    return {"remaining_quota": remaining_quota(), "today_spent": today_spent(),
            "daily_cap": DAILY_CAP, "reserve": RESERVE,
            "fetch_allowed": should_fetch(1)}


if __name__ == "__main__":
    print("odds_budget:", json.dumps(status()))
