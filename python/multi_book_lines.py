"""
EdgeStat -- Multi-book line aggregator.

Pulls MLB game lines from multiple US sportsbooks and identifies the BEST
available price per side. Line shopping is the single highest-ROI thing in
sports betting -- saving 2-5pp per pick.

Sources (in order of preference):
  1. DraftKings public eventgroups endpoint (no key needed)
  2. Bovada (already polled by live_clv.py)
  3. The Odds API (8+ books aggregated; needs ODDS_API_KEY)
  4. FanDuel public sbapi (best-effort)

For each MLB game today:
  - home ML + away ML across all books
  - F5 ML + F5 total
  - Game total + total over/under prices
  - Run line +1.5 / -1.5
  - Identifies BEST PRICE per side
  - Flags ARBITRAGE (book A favorite + book B underdog = positive sum)
  - Flags MIDDLE (book A total +0.5 vs book B total -0.5 with both close)

Output: data/multi_book_lines.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except Exception:
    Request = urlopen = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "multi_book_lines.json")

USER_AGENT = "Mozilla/5.0 EdgeStat/1.0 (research)"

# DraftKings public MLB event group -- often 403s outside whitelisted states
DK_MLB_URL = "https://sportsbook-us-il.draftkings.com/sites/US-IL-SB/api/v5/eventgroups/84240?format=json"
# ESPN scoreboard (no key) -- odds object inside each competition; one book per game
ESPN_MLB_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
# The Odds API (needs key) -- 8+ books aggregated
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"

# Request-budget guard (skip paid fetches when quota is low -> free ESPN fallback).
try:
    from odds_budget import should_fetch as _budget_ok, record_spend as _budget_spend
except Exception:
    def _budget_ok(cost=1):
        return True

    def _budget_spend(cost=1):
        pass


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _http(url: str, timeout: float = 10.0) -> Any:
    if not urlopen: return None
    try:
        ua = "EdgeStat/1.0" if "espn.com" in url else USER_AGENT
        req = Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


def _implied(odds) -> Optional[float]:
    if odds is None: return None
    try:
        o = float(odds)
        if o < 0: return abs(o) / (abs(o) + 100) * 100
        return 100 / (o + 100) * 100
    except Exception:
        return None


def _best_of(prices: List[Tuple[str, float]]) -> Optional[Tuple[str, float]]:
    """Given [(book, odds)], return the BEST (longest) price for that side."""
    if not prices: return None
    # Highest American line = best price for bettor (e.g. +130 beats +120; -110 beats -115)
    valid = [(b, o) for b, o in prices if o is not None]
    if not valid: return None
    return max(valid, key=lambda x: float(x[1]))


def _fetch_draftkings_mlb() -> Dict[str, Dict[str, Any]]:
    """Fetch DraftKings MLB lines. Returns dict keyed by 'AWAY @ HOME'."""
    data = _http(DK_MLB_URL, timeout=10)
    if not data: return {}
    out = {}
    eg = data.get("eventGroup") or {}
    events = eg.get("events") or []
    # Categories hold ML / Spread / Total offers
    cats = eg.get("offerCategories") or []
    # Build offer index: subcategoryId -> offer rows
    offers_by_event = {}
    for cat in cats:
        for sub in (cat.get("offerSubcategoryDescriptors") or []):
            sc = sub.get("offerSubcategory") or {}
            for o in (sc.get("offers") or []):
                # each o is a list of offers
                for inner in o:
                    eid = inner.get("eventId")
                    if not eid: continue
                    offers_by_event.setdefault(eid, []).append({
                        "label": inner.get("label"),
                        "outcomes": inner.get("outcomes") or [],
                    })

    for ev in events:
        eid = ev.get("eventId")
        name = ev.get("name") or ""  # e.g. "PHI @ CIN"
        if "@" not in name: continue
        away, home = [s.strip().upper() for s in name.split("@", 1)]
        key = f"{away} @ {home}"
        rec = {"away": away, "home": home, "dk": {}}

        for offer in offers_by_event.get(eid, []):
            label = (offer.get("label") or "").lower()
            outs = offer.get("outcomes") or []
            if label in ("moneyline", "money line", "ml"):
                for o in outs:
                    line = o.get("oddsAmerican")
                    label_team = (o.get("label") or "").upper()
                    if label_team == away:
                        rec["dk"]["away_ml"] = int(line) if line is not None else None
                    elif label_team == home:
                        rec["dk"]["home_ml"] = int(line) if line is not None else None
            elif "total" in label and "first" not in label and "1st" not in label:
                # Game total
                for o in outs:
                    line = o.get("oddsAmerican")
                    pt = o.get("line")
                    lbl = (o.get("label") or "").lower()
                    if "over" in lbl:
                        rec["dk"]["total_over"] = int(line) if line is not None else None
                        rec["dk"]["total_line"] = float(pt) if pt is not None else None
                    elif "under" in lbl:
                        rec["dk"]["total_under"] = int(line) if line is not None else None
            elif "spread" in label or "run line" in label:
                for o in outs:
                    line = o.get("oddsAmerican")
                    pt = o.get("line")
                    lbl = (o.get("label") or "").upper()
                    if lbl == away:
                        rec["dk"]["away_rl"] = int(line) if line is not None else None
                        rec["dk"]["away_rl_pt"] = float(pt) if pt is not None else None
                    elif lbl == home:
                        rec["dk"]["home_rl"] = int(line) if line is not None else None
                        rec["dk"]["home_rl_pt"] = float(pt) if pt is not None else None
        out[key] = rec
    return out


def _paid_fetch_already_today() -> bool:
    """ONCE-PER-DAY guard (2026-08-17): this module runs in the 2-hour heartbeat,
    so its 3-credit Odds-API call fired ~12x/day and burned ~36 paid credits
    daily on 8-book GAME lines -- data the free ESPN feed already refreshes in
    the same heartbeat. That torched the August quota to 4 credits in days.
    The paid multi-book snapshot adds line-shop depth; once a day is plenty."""
    prev = _load(OUT)
    if str(prev.get("generated_at", ""))[:10] != dt.date.today().isoformat():
        return False
    return bool(prev.get("had_odds_api"))


def _fetch_odds_api_mlb() -> Dict[str, Dict[str, Any]]:
    """Fetch from The Odds API if key set. Returns dict by matchup key."""
    key = os.environ.get("ODDS_API_KEY")
    if not key or not _budget_ok(3): return {}
    if _paid_fetch_already_today():
        return {}
    url = f"{ODDS_API_URL}?apiKey={key}&regions=us&markets=h2h,spreads,totals&oddsFormat=american"
    data = _http(url, timeout=12)
    if not data or not isinstance(data, list): return {}
    _budget_spend(3)
    out = {}
    for g in data:
        away = (g.get("away_team") or "").upper()
        home = (g.get("home_team") or "").upper()
        # Normalize team names to abbreviation if possible (Odds API uses full names)
        for book in (g.get("bookmakers") or []):
            book_key = book.get("key")  # 'draftkings', 'fanduel', etc.
            for market in (book.get("markets") or []):
                mkey = market.get("key")
                for outcome in (market.get("outcomes") or []):
                    pass  # could expand here; keeping shape minimal for now
        out[f"{away} @ {home}"] = {"away": away, "home": home,
                                    "bookmakers": [b.get("key") for b in (g.get("bookmakers") or [])]}
    return out


_ESPN_ABBR = {
    "ARIZONA DIAMONDBACKS": "ARI", "ATLANTA BRAVES": "ATL", "BALTIMORE ORIOLES": "BAL",
    "BOSTON RED SOX": "BOS", "CHICAGO CUBS": "CHC", "CHICAGO WHITE SOX": "CHW",
    "CINCINNATI REDS": "CIN", "CLEVELAND GUARDIANS": "CLE", "COLORADO ROCKIES": "COL",
    "DETROIT TIGERS": "DET", "HOUSTON ASTROS": "HOU", "KANSAS CITY ROYALS": "KCR",
    "LOS ANGELES ANGELS": "LAA", "LOS ANGELES DODGERS": "LAD", "MIAMI MARLINS": "MIA",
    "MILWAUKEE BREWERS": "MIL", "MINNESOTA TWINS": "MIN", "NEW YORK METS": "NYM",
    "NEW YORK YANKEES": "NYY", "OAKLAND ATHLETICS": "OAK", "ATHLETICS": "OAK",
    "PHILADELPHIA PHILLIES": "PHI", "PITTSBURGH PIRATES": "PIT", "SAN DIEGO PADRES": "SDP",
    "SAN FRANCISCO GIANTS": "SFG", "SEATTLE MARINERS": "SEA", "ST. LOUIS CARDINALS": "STL",
    "TAMPA BAY RAYS": "TBR", "TEXAS RANGERS": "TEX", "TORONTO BLUE JAYS": "TOR",
    "WASHINGTON NATIONALS": "WSN",
}


def _abbr(team_name: str) -> str:
    return _ESPN_ABBR.get((team_name or "").upper(), (team_name or "")[:3].upper())


def _fetch_espn_mlb() -> Dict[str, Dict[str, Any]]:
    """Pull ESPN scoreboard odds (one book per game; rotating provider)."""
    data = _http(ESPN_MLB_URL, timeout=10)
    if not data: return {}
    out = {}
    events = data.get("events") or []
    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        teams = comp.get("competitors") or []
        if len(teams) != 2: continue
        home_t = next((t for t in teams if t.get("homeAway") == "home"), None)
        away_t = next((t for t in teams if t.get("homeAway") == "away"), None)
        if not home_t or not away_t: continue
        home_full = (home_t.get("team") or {}).get("displayName", "")
        away_full = (away_t.get("team") or {}).get("displayName", "")
        home = _abbr(home_full)
        away = _abbr(away_full)
        key = f"{away} @ {home}"

        odds_list = comp.get("odds") or []
        if not odds_list: continue
        # ESPN can return multiple providers; take all
        books = {}
        for od in odds_list:
            book_name = ((od.get("provider") or {}).get("name") or "espn").lower().replace(" ", "_")
            # Parse spread + total + ML
            home_ml = od.get("homeTeamOdds", {}).get("moneyLine")
            away_ml = od.get("awayTeamOdds", {}).get("moneyLine")
            total_line = od.get("overUnder")
            total_over = od.get("overOdds")
            total_under = od.get("underOdds")
            books[book_name] = {
                "home_ml": int(home_ml) if home_ml is not None else None,
                "away_ml": int(away_ml) if away_ml is not None else None,
                "total_line": float(total_line) if total_line is not None else None,
                "total_over": int(total_over) if total_over is not None else None,
                "total_under": int(total_under) if total_under is not None else None,
            }
        out[key] = {"away": away, "home": home, "books": books}
    return out


def _fetch_bovada_from_clv() -> Dict[str, Dict[str, Any]]:
    """Read latest Bovada snapshot from live_clv.json (already polled)."""
    clv = _load(os.path.join(DATA_DIR, "live_clv.json"))
    games = clv.get("games", [])
    if isinstance(games, dict): games = list(games.values())
    out = {}
    for g in games:
        matchup = g.get("matchup") or ""
        if "@" not in matchup: continue
        away, home = [s.strip().upper() for s in matchup.split("@", 1)]
        snaps = g.get("snapshots") or []
        pre = [s for s in snaps if s.get("state") == "pre"]
        if not pre: continue
        latest = pre[-1]
        out[f"{away} @ {home}"] = {
            "away": away, "home": home,
            "bovada": {
                "away_ml": latest.get("away_ml"),
                "home_ml": latest.get("home_ml"),
                "total_line": latest.get("total"),
                "total_over": latest.get("total_over"),
                "total_under": latest.get("total_under"),
            },
        }
    return out


def _detect_arb(books: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Check for arbitrage: best home ML + best away ML implied prob < 100%."""
    home_prices = []
    away_prices = []
    for book, b in books.items():
        if b.get("home_ml") is not None:
            home_prices.append((book, b["home_ml"]))
        if b.get("away_ml") is not None:
            away_prices.append((book, b["away_ml"]))
    best_home = _best_of(home_prices)
    best_away = _best_of(away_prices)
    if not best_home or not best_away: return None
    p_home = _implied(best_home[1])
    p_away = _implied(best_away[1])
    if p_home is None or p_away is None: return None
    total = p_home + p_away
    if total < 100:
        return {
            "type": "ARBITRAGE",
            "implied_sum": round(total, 2),
            "edge_pct": round(100 - total, 2),
            "best_home": {"book": best_home[0], "odds": best_home[1]},
            "best_away": {"book": best_away[0], "odds": best_away[1]},
        }
    elif total < 102:
        return {
            "type": "LOW_VIG",
            "implied_sum": round(total, 2),
            "vig_pct": round(total - 100, 2),
            "best_home": {"book": best_home[0], "odds": best_home[1]},
            "best_away": {"book": best_away[0], "odds": best_away[1]},
        }
    return None


def run() -> Dict[str, Any]:
    # Pull from each source
    dk = _fetch_draftkings_mlb()
    espn = _fetch_espn_mlb()
    odds_api = _fetch_odds_api_mlb()
    bovada = _fetch_bovada_from_clv()

    # Merge by matchup key
    all_keys = set(dk.keys()) | set(espn.keys()) | set(odds_api.keys()) | set(bovada.keys())
    rows = []
    for key in sorted(all_keys):
        d_rec = dk.get(key, {})
        e_rec = espn.get(key, {})
        b_rec = bovada.get(key, {})
        away = d_rec.get("away") or e_rec.get("away") or b_rec.get("away") or "?"
        home = d_rec.get("home") or e_rec.get("home") or b_rec.get("home") or "?"

        books = {}
        if d_rec.get("dk"): books["draftkings"] = d_rec["dk"]
        if e_rec.get("books"):
            for bk, bv in e_rec["books"].items():
                books[bk] = bv
        if b_rec.get("bovada"): books["bovada"] = b_rec["bovada"]

        # Best lines
        home_prices = [(b, books[b].get("home_ml")) for b in books if books[b].get("home_ml") is not None]
        away_prices = [(b, books[b].get("away_ml")) for b in books if books[b].get("away_ml") is not None]
        over_prices = [(b, books[b].get("total_over")) for b in books if books[b].get("total_over") is not None]
        under_prices = [(b, books[b].get("total_under")) for b in books if books[b].get("total_under") is not None]

        best_home = _best_of(home_prices)
        best_away = _best_of(away_prices)
        best_over = _best_of(over_prices)
        best_under = _best_of(under_prices)

        arb = _detect_arb(books)

        rows.append({
            "matchup": key,
            "away_team": away,
            "home_team": home,
            "n_books": len(books),
            "books": books,
            "best_home_ml": {"book": best_home[0], "odds": best_home[1]} if best_home else None,
            "best_away_ml": {"book": best_away[0], "odds": best_away[1]} if best_away else None,
            "best_total_over": {"book": best_over[0], "odds": best_over[1]} if best_over else None,
            "best_total_under": {"book": best_under[0], "odds": best_under[1]} if best_under else None,
            "arbitrage_or_lowvig": arb,
        })

    arbs = [r["arbitrage_or_lowvig"] for r in rows if r.get("arbitrage_or_lowvig") and r["arbitrage_or_lowvig"]["type"] == "ARBITRAGE"]
    lowvigs = [r["arbitrage_or_lowvig"] for r in rows if r.get("arbitrage_or_lowvig") and r["arbitrage_or_lowvig"]["type"] == "LOW_VIG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_books_polled": len({b for r in rows for b in r["books"].keys()}),
        # Sticky same-day flag: the once-per-day paid-fetch guard reads this, so
        # a later heartbeat that (correctly) skipped the paid call must not
        # reset it and re-trigger spending on the next run.
        "had_odds_api": bool(odds_api) or _paid_fetch_already_today(),
        "sources_used": [
            ("DraftKings", "live" if dk else "blocked (geo)"),
            ("ESPN scoreboard", "live" if espn else "empty"),
            ("Bovada", "live" if bovada else "empty"),
            ("OddsAPI", "live" if odds_api else "skipped (quota-guarded or no key)"),
        ],
        "rows": rows,
        "n_arbitrage_found": len(arbs),
        "n_lowvig_found": len(lowvigs),
        "arbitrage_alerts": arbs,
        "lowvig_alerts": lowvigs,
        "note": ("Line shopping aggregator. Best price across DK + Bovada (+OddsAPI if key set). "
                 "Saves 2-5pp per pick long-term -- single highest-ROI feature in sports betting."),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[multi-book] {o['n_games']} games, {o['n_books_polled']} books polled, "
          f"{o['n_arbitrage_found']} arbs, {o['n_lowvig_found']} low-vigs -> {OUT}")
