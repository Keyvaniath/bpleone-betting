"""
EdgeStat -- FREE book odds feed from ESPN.

The paid The Odds API key (ODDS_API_KEY) is lapsed, which froze the book-vs-model
edges / line movement / CLV on stale lines. ESPN's public scoreboard API carries
live sportsbook odds (DraftKings) -- moneyline, total, and spread -- for free, no
key required. The site already uses ESPN's free endpoints for results
(espn_event_results, espn_box_logs), so this just adds the odds they also expose.

This removes the hard dependency on a paid key: fresh, comprehensive game odds for
every game on the slate, every pipeline run.

Output: data/espn_odds.json  -- matchup-keyed ("AWAY @ HOME" abbreviations) so it
joins straight onto matchups.json / today.json, consumed by book_vs_model_team.py.

Usage: python espn_odds.py [sport ...]   (default: mlb)
"""
from __future__ import annotations

import os
import sys
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional

PLACEHOLDER_ABS_ML = 3000   # beyond this an ESPN 'DK' moneyline is a placeholder, not a market (2026-11-05)
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "espn_odds.json")
HISTORY = os.path.join(DATA_DIR, "odds_history.json")

# Sports pulled by default each run (off-season leagues just return 0 games).
# 2026-08-13: football added for the season -- NFL preseason is live now, NCAAF
# starts late Aug, NCAAB self-activates in Nov. Free ESPN lines feed the desks,
# line_movement, and clv_tracker (all sport-generic) with zero extra plumbing.
DEFAULT_SPORTS = ["mlb", "nba", "nhl", "wnba", "nfl", "ncaaf", "ncaab"]
MAX_SNAPSHOTS = 80      # per game-day, bounds the history file
HISTORY_KEEP_DAYS = 8   # prune game-days older than this

# ESPN scoreboard path per sport (free, no key). Extensible -- add a row to cover
# another league's odds.
SPORT_PATHS = {
    "mlb": "baseball/mlb",
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "nhl": "hockey/nhl",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "ncaab": "basketball/mens-college-basketball",
}

# ESPN uses a few different team abbreviations than this codebase's model side
# (today.json / matchups.json / prop files). Normalize ESPN -> model so the
# "AWAY @ HOME" matchup key joins straight onto the model. Confirmed from the
# model's own vocabulary across data/.
ESPN_TO_MODEL = {
    "mlb": {"TB": "TBR", "KC": "KCR", "SD": "SDP", "WSH": "WSN", "SF": "SFG",
            "ATH": "OAK", "AZ": "ARI"},
}


def _norm(sport: str, abbr: Optional[str]) -> Optional[str]:
    if not abbr:
        return abbr
    return ESPN_TO_MODEL.get(sport, {}).get(abbr.upper(), abbr.upper())


def _get(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def _am(v) -> Optional[int]:
    """ESPN odds come as strings like '+103' / '-124' / 'EVEN'."""
    if v is None:
        return None
    s = str(v).strip().upper().replace("EVEN", "+100")
    try:
        return int(s.replace("+", ""))
    except ValueError:
        return None


def _deep(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


# Per-sport scoreboard query params. THE COLLEGE TRUNCATION (2026-09-03): the
# bare college-football scoreboard returns a CURATED subset -- 25 events on a
# day with 99. `limit` alone does nothing; `groups=80` (the FBS group) is what
# unlocks the full slate, and limit must then be raised because CFB Saturdays
# run past the default page size. Same shape applies to college basketball
# (group 50 = D-I). The pro leagues take no params and are unaffected.
SPORT_QUERY = {
    "ncaaf": "?groups=80&limit=400",
    "ncaab": "?groups=50&limit=400",
}


# THE MORNING ROLLOVER (2026-10-29): the bare scoreboard for the daily-slate
# leagues keeps showing YESTERDAY's games until ESPN rolls the day over in late
# morning ET. The 9 AM ET heartbeat snapshot had 4 finished NHL games and none
# of the 11 on that night's slate, so the 10 AM daily run priced an empty NHL
# board. For these leagues also ask for today's ET date explicitly and merge
# (deduped by event id; today's copy last so matchup-keyed joins take it).
DATED_SPORTS = {"mlb", "nba", "wnba", "nhl", "ncaab"}
# THE WEEKLY ROLLOVER (2026-11-03): the bare NFL / college-football board keeps
# showing LAST week (all finals) until midweek -- on Tuesday 11/3 it held 14
# finished Week 9 games and none of Week 10, so the game-lines desk had an empty
# NFL board whenever DraftKings posted next week's lines before the rollover.
# For weekly leagues also request the NEXT week (week + 1, same season type;
# after the last regular-season week, postseason week 1) and merge by event id.
WEEKLY_SPORTS = {"nfl", "ncaaf"}


def _next_week_query(board: Dict[str, Any]) -> Optional[str]:
    """`week=N+1&seasontype=T` from the bare board's own week / season block,
    or the postseason's first week once the regular season's weeks run out."""
    wk = (board.get("week") or {}).get("number")
    st = (board.get("season") or {}).get("type")
    if not wk or not st:
        return None
    return f"week={int(wk) + 1}&seasontype={int(st)}"


# THE NIGHT-BEFORE OPENERS (2026-11-13): DraftKings posts the next day's NHL (and NBA) lines
# the evening before -- at 3 PM ET on 11/13 all 14 of 11/14's NHL games were priced on ESPN's
# dated board -- and the opener is the softest number of a line's life. These leagues also
# fetch TOMORROW's ET date, written to a SEPARATE key (games_next_day) so the 20 consumers that
# read `games` as today's slate (matchup-keyed joins, pricing, today_status) never see them.
# Only the game-lines desk (line history + desk rows) and the board opt in.
NEXT_DAY_SPORTS = {"nba", "nhl"}


def _tomorrow_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return (dt.datetime.now(ZoneInfo("America/New_York")) + dt.timedelta(days=1)).strftime("%Y%m%d")
    except Exception:
        return (dt.datetime.utcnow() - dt.timedelta(hours=4) + dt.timedelta(days=1)).strftime("%Y%m%d")


def _today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d")
    except Exception:
        return (dt.datetime.utcnow() - dt.timedelta(hours=4)).strftime("%Y%m%d")


def fetch_sport(sport: str, only_date: Optional[str] = None) -> List[Dict[str, Any]]:
    path = SPORT_PATHS.get(sport)
    if not path:
        return []
    q = SPORT_QUERY.get(sport, "")
    base = f"https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"
    urls = [base + q]
    if only_date:                                   # one dated board only (the night-before slate)
        urls = [base + (q + "&" if q else "?") + f"dates={only_date}"]
    elif sport in DATED_SPORTS:
        urls.append(base + (q + "&" if q else "?") + f"dates={_today_et()}")
    events: List[Dict[str, Any]] = []
    first: Dict[str, Any] = {}
    for u in urls:
        try:
            d = _get(u)
            first = first or d
            events.extend(d.get("events") or [])
        except Exception as e:
            print(f"[espn-odds] {sport} fetch failed ({u.rsplit('/', 1)[-1]}): {e!r}")
    if sport in WEEKLY_SPORTS and first and not only_date:
        nq = _next_week_query(first)
        tries = [nq] if nq else []
        if (first.get("season") or {}).get("type") == 2:
            tries.append("week=1&seasontype=3")       # regular season over -> postseason week 1
        for qq in tries:
            try:
                nxt = _get(base + (q + "&" if q else "?") + qq).get("events") or []
            except Exception as e:
                print(f"[espn-odds] {sport} next-week fetch failed ({qq}): {e!r}")
                nxt = []
            if nxt:
                events.extend(nxt)
                break
    if not events:
        return []
    last = {}
    for e in events:
        last[str(e.get("id"))] = e
    seen, ordered = set(), []
    for e in reversed(events):
        k = str(e.get("id"))
        if k not in seen:
            seen.add(k)
            ordered.append(last[k])
    events = list(reversed(ordered))
    out: List[Dict[str, Any]] = []
    for e in events:
        comp = (e.get("competitions") or [{}])[0]
        teams = {t.get("homeAway"): t for t in (comp.get("competitors") or [])}
        home, away = teams.get("home") or {}, teams.get("away") or {}
        home_ab = _norm(sport, _deep(home, "team", "abbreviation"))
        away_ab = _norm(sport, _deep(away, "team", "abbreviation"))
        if not home_ab or not away_ab:
            continue
        odds_list = comp.get("odds") or []
        o = odds_list[0] if odds_list else {}
        ml = o.get("moneyline") or {}
        tot = o.get("total") or {}
        ml_home = _am(_deep(ml, "home", "close", "odds") or _deep(ml, "home", "open", "odds"))
        ml_away = _am(_deep(ml, "away", "close", "odds") or _deep(ml, "away", "open", "odds"))
        # (2026-11-05, pre-launch audit) ESPN files placeholder "DraftKings" lines on
        # lopsided college games (-100000/+5000, -20000/+3500). Downstream they
        # became a 98% "market" probability, a LOW_VIG flag and a TRACK button at
        # -100000. A side beyond +/-3000 is not a posted market: drop the pair.
        placeholder_ml = any(abs(int(x)) > PLACEHOLDER_ABS_ML for x in (ml_home, ml_away) if x is not None)
        if placeholder_ml:
            ml_home = ml_away = None
        # (2026-11-13) DraftKings' OWN opening moneyline (ESPN's moneyline.*.open), kept apart from
        # the current price: our first snapshot can come hours after the opener (NY @ IND opened
        # +110, first seen by us at +220). Informational only -- no bet is ever priced at it.
        ml_home_open = _am(_deep(ml, "home", "open", "odds"))
        ml_away_open = _am(_deep(ml, "away", "open", "odds"))
        if placeholder_ml or any(abs(int(x)) > PLACEHOLDER_ABS_ML for x in (ml_home_open, ml_away_open) if x is not None):
            ml_home_open = ml_away_open = None
        over_px = _am(_deep(tot, "over", "close", "odds") or _deep(tot, "over", "open", "odds"))
        under_px = _am(_deep(tot, "under", "close", "odds") or _deep(tot, "under", "open", "odds"))
        # (2026-11-13) spread PRICES: ESPN carries DraftKings' point-spread odds under
        # pointSpread.{home,away}.close; until now only the spread number was kept, so no
        # spread could ever be priced or backtested. Lines are signed for that side.
        ps = o.get("pointSpread") or {}

        def _line(v):
            try:
                return float(str(v).strip())
            except (TypeError, ValueError):
                return None
        def _pair(side):
            # (2026-11-13 review) line AND price from the same snapshot: the close when it has
            # both, else the open. Never a close line with an open price, and a 0 (pick'em)
            # line is a line, not a missing value.
            for when in ("close", "open"):
                ln, px = _line(_deep(ps, side, when, "line")), _am(_deep(ps, side, when, "odds"))
                if ln is not None and px is not None:
                    return ln, px
            return None, None
        sp_home_line, sp_home_px = _pair("home")
        sp_away_line, sp_away_px = _pair("away")
        if any(x is not None and abs(int(x)) > PLACEHOLDER_ABS_ML for x in (sp_home_px, sp_away_px)):
            sp_home_px = sp_away_px = None
        status = _deep(comp, "status", "type", "state")  # pre / in / post
        out.append({
            "sport": sport.upper(),
            # ESPN's own event id. Carried so downstream desks can settle a pick
            # against the EXACT game instead of re-deriving it from
            # matchup+date -- date matching has burned this repo twice (UTC
            # shear moved west-coast night games a day; doubleheaders made a
            # matchup+date pair ambiguous). An id has neither failure mode.
            "event_id": str(e.get("id") or ""),
            "matchup": f"{away_ab} @ {home_ab}",
            "away": away_ab,
            "home": home_ab,
            "neutral": bool(comp.get("neutralSite")),
            "commence_time": e.get("date"),
            "status": status,
            "provider": _deep(o, "provider", "name"),
            "market": {
                "ml_home": ml_home,
                "ml_away": ml_away,
                "placeholder_ml": placeholder_ml,
                "ml_home_open": ml_home_open,
                "ml_away_open": ml_away_open,
                # DraftKings' opening spread (home line) and total, same source as the opening ML
                "spread_home_open": _line(_deep(ps, "home", "open", "line")),
                "total_open": _line(str(_deep(tot, "over", "open", "line") or "").lstrip("oOuU") or None),
                "total": o.get("overUnder"),
                "over_price": over_px,
                "under_price": under_px,
                "spread": o.get("spread"),
                "spread_home_line": sp_home_line,
                "spread_home_price": sp_home_px,
                "spread_away_line": sp_away_line,
                "spread_away_price": sp_away_px,
                "book": (_deep(o, "provider", "name") or "espn").lower().replace(" ", ""),
            },
        })
    return out


def _load_json(p) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _update_history(priced: List[Dict[str, Any]], now: str) -> int:
    """Append a timestamped odds snapshot per game-day (only when a line moved),
    pruning game-days older than HISTORY_KEEP_DAYS. This is the open->close trail
    that powers line-movement / steam detection and Closing Line Value."""
    today = now[:10]
    hist = _load_json(HISTORY).get("history") or {}
    for g in priced:
        gd = (g.get("commence_time") or now)[:10]
        key = f"{g['sport']}|{g['matchup']}|{gd}"
        m = g["market"]
        snap = {"ts": now, "ml_home": m["ml_home"], "ml_away": m["ml_away"],
                "total": m["total"], "over": m["over_price"], "under": m["under_price"]}
        seq = hist.get(key) or []
        last = seq[-1] if seq else None
        if (last is None) or any(last.get(k) != snap.get(k) for k in ("ml_home", "ml_away", "total", "over", "under")):
            seq.append(snap)
        hist[key] = seq[-MAX_SNAPSHOTS:]

    def _too_old(k: str) -> bool:
        try:
            d = k.rsplit("|", 1)[1]
            return (dt.date.fromisoformat(today) - dt.date.fromisoformat(d)).days > HISTORY_KEEP_DAYS
        except Exception:
            return False
    hist = {k: v for k, v in hist.items() if not _too_old(k)}
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump({"generated_at": now, "n_games_tracked": len(hist), "history": hist}, f, indent=2)
    return len(hist)


def run(sports: Optional[List[str]] = None) -> Dict[str, Any]:
    sports = sports or DEFAULT_SPORTS
    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    games: List[Dict[str, Any]] = []
    for s in sports:
        games.extend(fetch_sport(s))
    priced = [g for g in games if g["market"]["ml_home"] is not None and g["market"]["ml_away"] is not None]
    n_tracked = _update_history(priced, now)
    # by_matchup is MLB-only so book_vs_model_team (MLB game lines) joins cleanly;
    # other sports live in the full games list + the history trail.
    by_matchup = {g["matchup"]: g["market"] for g in priced if g["sport"] == "MLB"}
    # tomorrow's slate for the night-before leagues: pre-game, priced, and not already listed today
    have = {str(g.get("event_id")) for g in games}
    next_day: List[Dict[str, Any]] = []
    tmr = _tomorrow_et()
    for s in sports:
        if s in NEXT_DAY_SPORTS:
            for g in fetch_sport(s, only_date=tmr):
                if (str(g.get("event_id")) not in have and g.get("status") == "pre"
                        and g["market"]["ml_home"] is not None and g["market"]["ml_away"] is not None):
                    next_day.append(g)
    result = {
        "generated_at": now,
        "source": "espn-scoreboard (free, no key)",
        "sports": [s.upper() for s in sports],
        "n_games": len(games),
        "n_priced": len(priced),
        "n_games_tracked_history": n_tracked,
        "by_sport": {s.upper(): sum(1 for g in priced if g["sport"] == s.upper()) for s in sports},
        "by_matchup": by_matchup,
        "games": games,
        # NOT today's slate: read only by game_lines_desk + board (see NEXT_DAY_SPORTS)
        "next_day_date": f"{tmr[:4]}-{tmr[4:6]}-{tmr[6:]}",
        "games_next_day": next_day,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    args = [a.lower() for a in sys.argv[1:]] or DEFAULT_SPORTS
    o = run(args)
    print(f"[espn-odds] {o['n_priced']}/{o['n_games']} games priced "
          f"({o['by_sport']}) -> {OUT}")
    for g in o["games"]:
        m = g["market"]
        if m["ml_home"] is not None and m["ml_away"] is not None:
            ou = f"O/U {m['total']}" if m["total"] is not None else "O/U --"
            print(f"    {g['matchup']:14s} {g['sport']:4s} away {m['ml_away']:+d} / home {m['ml_home']:+d} | {ou} [{m['book']}]")
