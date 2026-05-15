"""
EdgeStat -- Bovada odds fallback.

The Odds API (paid, 401-ing as of 2026-05-15) is the primary game-line + player-prop
data source. Bovada is a public, no-auth, not-IP-blocked alternative that mirrors
roughly the same lines (Bovada market efficiency is within ~2-3 cents of DraftKings
on liquid markets).

This module fetches the public MLB coupon JSON and returns it in the same shape
the rest of the pipeline expects:

  fetch_game_lines(date_iso) -> {matchup_str: {home_ml, away_ml, total, total_over, total_under,
                                                home_rl, away_rl, home_rl_hcap, away_rl_hcap,
                                                book: 'bovada'}}

Used as a fallback in pipeline.py / props_pipeline.py when the Odds API call fails
or quota is exhausted. Records carry book='bovada' so consumers know the source
(slightly less efficient than DK closing line, but real).
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore


BOVADA_MLB_URL = (
    "https://www.bovada.lv/services/sports/event/coupon/events/A/description/baseball/mlb"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Bovada uses full team names; pipeline.py uses TEAM_CODE 3-letter codes.
# Import the master dict so we stay in sync if codes change.
try:
    from pipeline import TEAM_CODE
except Exception:
    TEAM_CODE = {}


def _short_code(team_full_name: str) -> str:
    return TEAM_CODE.get(team_full_name, team_full_name[:3].upper())


def fetch_raw() -> List[Dict[str, Any]]:
    """Return the raw Bovada response (list of group dicts)."""
    if requests is None:
        return []
    try:
        r = requests.get(BOVADA_MLB_URL, headers=HEADERS, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [x] bovada fetch failed: {e}")
        return []


def _extract_events(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for grp in raw:
        for ev in grp.get("events") or []:
            out.append(ev)
    return out


def _american(price_dict: Optional[Dict[str, Any]]) -> Optional[int]:
    """Bovada price shape: {american: '+113', decimal: '2.13', ...}."""
    if not price_dict:
        return None
    val = price_dict.get("american")
    if not val:
        return None
    try:
        s = str(val).replace("EVEN", "+100").strip()
        return int(s)
    except Exception:
        return None


def _market_by_desc(group: Dict[str, Any], desc: str) -> Optional[Dict[str, Any]]:
    """Return the first market in group whose description matches (case-insensitive)."""
    for m in group.get("markets") or []:
        if (m.get("description") or "").strip().lower() == desc.lower():
            return m
    return None


def parse_game_lines(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract moneyline + total + runline for a single Bovada event.

    Returns a dict in the same shape pipeline.py expects when reading the Odds API,
    or None if we can't find the core markets.
    """
    desc = event.get("description") or ""
    if " @ " not in desc:
        return None
    away_name, home_name = desc.split(" @ ", 1)
    # Find the "Game Lines" group
    group = next((g for g in (event.get("displayGroups") or [])
                  if (g.get("description") or "").lower() == "game lines"), None)
    if not group:
        return None

    ml = _market_by_desc(group, "Moneyline")
    total = _market_by_desc(group, "Total")
    runline = _market_by_desc(group, "Runline")
    if not ml or not total:
        return None

    # Moneyline outcomes
    home_ml = away_ml = None
    for o in ml.get("outcomes") or []:
        name = o.get("description") or ""
        amer = _american(o.get("price"))
        # The full game ML uses the full team name (1H/1I are halves/innings, skip).
        if " - " in name:
            continue
        if name == home_name:
            home_ml = amer
        elif name == away_name:
            away_ml = amer

    # Total
    total_pts = total_over = total_under = None
    for o in (total.get("outcomes") or [])[:2]:
        name = (o.get("description") or "").lower()
        if " - " in name:
            continue
        amer = _american(o.get("price"))
        hcap = (o.get("price") or {}).get("handicap")
        try:
            total_pts = float(hcap) if hcap is not None else total_pts
        except Exception:
            pass
        if "over" in name:
            total_over = amer
        elif "under" in name:
            total_under = amer

    # Runline (-1.5 / +1.5)
    home_rl = away_rl = None
    home_rl_hcap = away_rl_hcap = None
    for o in (runline.get("outcomes") or []) if runline else []:
        name = o.get("description") or ""
        if " - " in name:
            continue
        amer = _american(o.get("price"))
        hcap = (o.get("price") or {}).get("handicap")
        try:
            hcap_num = float(hcap) if hcap is not None else None
        except Exception:
            hcap_num = None
        if name == home_name:
            home_rl = amer
            home_rl_hcap = hcap_num
        elif name == away_name:
            away_rl = amer
            away_rl_hcap = hcap_num

    if home_ml is None and away_ml is None:
        return None

    return {
        "away_name": away_name,
        "home_name": home_name,
        "away_code": _short_code(away_name),
        "home_code": _short_code(home_name),
        "matchup": f"{_short_code(away_name)} @ {_short_code(home_name)}",
        "home_ml": home_ml,
        "away_ml": away_ml,
        "total": total_pts,
        "total_over": total_over,
        "total_under": total_under,
        "home_rl": home_rl,
        "home_rl_hcap": home_rl_hcap,
        "away_rl": away_rl,
        "away_rl_hcap": away_rl_hcap,
        "start_time": event.get("startTime"),
        "book": "bovada",
        "event_id": event.get("id"),
    }


def fetch_game_lines() -> Dict[str, Dict[str, Any]]:
    """Return {matchup_str: lines_dict} for all MLB events Bovada lists today."""
    raw = fetch_raw()
    if not raw:
        return {}
    events = _extract_events(raw)
    out: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        parsed = parse_game_lines(ev)
        if parsed and parsed.get("home_ml") is not None and parsed.get("total") is not None:
            out[parsed["matchup"]] = parsed
    return out


# -------------------- Player Props --------------------

PROP_MARKET_MAP = {
    # Bovada description prefix (lowercased) -> our market_key.
    # Order matters: more-specific prefixes first so substring matches don't
    # collide (e.g., "alternate strikeouts" should still hit pitcher_strikeouts).
    "alternate strikeouts": "pitcher_strikeouts",
    "total strikeouts": "pitcher_strikeouts",
    "total bases": "batter_total_bases",
    "total doubles": "batter_doubles",
    "total hits, runs and rbis": "batter_hits_runs_rbis",
    # Bovada writes these as "Player to record a/2+/3+ Hit/Run/RBI"
    "player to record 2+ hits": "batter_hits",
    "player to record a hit": "batter_hits",
    "player to record 2+ runs": "batter_runs_scored",
    "player to record a run": "batter_runs_scored",
    "player to record 2+ rbis": "batter_rbis",
    "player to record a rbi": "batter_rbis",
    "player to record a single": "batter_singles",
    "player to hit 2+ home runs": "batter_home_runs",
    "player to hit a home run": "batter_home_runs",
    # Fallback bare-word matchers
    "strikeouts": "pitcher_strikeouts",
    "home runs": "batter_home_runs",
    "hits": "batter_hits",
    "runs scored": "batter_runs_scored",
    "rbis": "batter_rbis",
    "doubles": "batter_doubles",
    "singles": "batter_singles",
}


def _implicit_line_from_desc(mdesc: str) -> Optional[float]:
    """For Bovada yes/no markets like 'Player to record a Hit' (line=0.5) or
    'Player to record 2+ Hits' (line=1.5), extract the implicit threshold."""
    d = mdesc.lower()
    # "Player to record a X" / "Player to hit a X" -> implicit line = 0.5
    if " a hit" in d or " a run" in d or " a rbi" in d or " a single" in d or " a stolen" in d:
        return 0.5
    if "hit a home run" in d:
        return 0.5
    # "Player to record 2+ X" / "Player to hit 2+ X" -> implicit line = 1.5
    if "2+ hits" in d:
        return 1.5
    if "2+ runs" in d:
        return 1.5
    if "2+ rbi" in d:
        return 1.5
    if "2+ home runs" in d:
        return 1.5
    return None


def parse_player_props(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return prop rows for a single event: [{player, market, line, over_amer, under_amer, book}].

    Handles three Bovada prop shapes:
      1. Over/Under with explicit handicap (e.g. "Total Strikeouts - Aaron Nola")
      2. One-sided yes/no with implicit line (e.g. "Player to record a Hit"
         -> implicit line=0.5; only OVER priced, UNDER stays None)
      3. Single-side market with player in market description
    """
    rows: List[Dict[str, Any]] = []
    for grp in (event.get("displayGroups") or []):
        gd = (grp.get("description") or "").lower()
        if "prop" not in gd and "player" not in gd and "pitcher" not in gd:
            continue
        for m in grp.get("markets") or []:
            mdesc_raw = m.get("description") or ""
            mdesc = mdesc_raw.lower().strip()
            market_key = None
            for prefix, key in PROP_MARKET_MAP.items():
                if prefix in mdesc:
                    market_key = key
                    break
            if not market_key:
                continue
            outs = m.get("outcomes") or []
            player_in_desc = None
            if " - " in mdesc_raw:
                player_in_desc = mdesc_raw.split(" - ", 1)[1].strip()

            implicit_line = _implicit_line_from_desc(mdesc)

            # Shape (a): grouped by handicap -> over/under per line.
            # Shape (b): no handicap, one outcome per player -> implicit line.
            has_hcaps = any((o.get("price") or {}).get("handicap") is not None for o in outs)

            if has_hcaps:
                # Group outcomes into over/under pairs by line.
                by_line: Dict[float, Dict[str, Any]] = {}
                for o in outs:
                    price = o.get("price") or {}
                    hcap = price.get("handicap")
                    try:
                        line = float(hcap) if hcap is not None else None
                    except Exception:
                        line = None
                    if line is None:
                        continue
                    name = (o.get("description") or "").lower()
                    amer = _american(price)
                    key = line
                    if key not in by_line:
                        by_line[key] = {"line": line}
                    if "over" in name:
                        by_line[key]["over_amer"] = amer
                    elif "under" in name:
                        by_line[key]["under_amer"] = amer
                    elif amer is not None:
                        by_line[key]["one_side"] = {"player": o.get("description"), "amer": amer}

                for line, pair in by_line.items():
                    player = player_in_desc
                    if not player and pair.get("one_side"):
                        player = pair["one_side"]["player"]
                    if not player:
                        continue
                    rows.append({
                        "player": player.strip(),
                        "market": market_key,
                        "line": line,
                        "over_amer": pair.get("over_amer") or (pair.get("one_side") or {}).get("amer"),
                        "under_amer": pair.get("under_amer"),
                        "book": "bovada",
                    })
            elif implicit_line is not None:
                # Shape (b): yes/no markets. Each outcome = one player priced
                # for the OVER side; we leave under_amer=None.
                for o in outs:
                    price = o.get("price") or {}
                    amer = _american(price)
                    if amer is None:
                        continue
                    player = o.get("description")
                    if not player:
                        continue
                    rows.append({
                        "player": player.strip(),
                        "market": market_key,
                        "line": implicit_line,
                        "over_amer": amer,
                        "under_amer": None,   # implicit -- yes/no market
                        "book": "bovada",
                    })
    return rows


def fetch_player_props() -> List[Dict[str, Any]]:
    """Return ALL player-prop rows across the MLB slate."""
    raw = fetch_raw()
    if not raw:
        return []
    events = _extract_events(raw)
    out: List[Dict[str, Any]] = []
    for ev in events:
        rows = parse_player_props(ev)
        # Tag with matchup so downstream knows the game context
        desc = ev.get("description") or ""
        if " @ " in desc:
            away_name, home_name = desc.split(" @ ", 1)
            mu = f"{_short_code(away_name)} @ {_short_code(home_name)}"
        else:
            mu = ""
        for r in rows:
            r["matchup"] = mu
        out.extend(rows)
    return out


# -------------------- CLI --------------------

if __name__ == "__main__":
    print("== Game lines ==")
    gl = fetch_game_lines()
    print(f"  {len(gl)} games")
    for mu, d in list(gl.items())[:3]:
        print(f"  {mu:15} ml: {d['away_ml']}/{d['home_ml']}  total: {d['total']} ({d['total_over']}/{d['total_under']})  rl: {d['away_rl']}/{d['home_rl']}")
    print()
    print("== Player props ==")
    pp = fetch_player_props()
    print(f"  {len(pp)} prop rows")
    by_market: Dict[str, int] = {}
    for r in pp:
        by_market[r["market"]] = by_market.get(r["market"], 0) + 1
    for m, n in sorted(by_market.items(), key=lambda x: -x[1]):
        print(f"  {m:30} {n}")
    if pp:
        print()
        print("  sample:", pp[0])
