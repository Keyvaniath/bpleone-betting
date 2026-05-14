"""
EdgeStat -- DraftKings player-props pipeline.

For each MLB game (up to MAX_GAMES), pull DK's player props for the markets
we model (pitcher_strikeouts, batter_home_runs), resolve each player to their
MLB ID, pull season stats, build a model projection, and compute the edge
against DK's posted line.

Writes data/props.json ordered by abs(edge_pct) descending.

QUOTA: each event call to The Odds API costs 1 credit per market requested.
With 2 markets * 8 games = 16 credits per refresh = ~480/month at the free tier.
Lift MAX_GAMES when the user upgrades the Odds API plan (the $30/mo tier is
20k req/month).

Player ID resolution caches name -> mlbid in data/cache/stats/ via stats_repo.
"""
from __future__ import annotations

import os
import sys
import math
import json
import time
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


ODDS_BASE = "https://api.the-odds-api.com/v4"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "props.json")

# Markets we model. Each adds 1 credit per event call.
# Free tier: keep at 2 markets * 8 games to fit 500/month.
# $20 tier (20k/month): can lift to all 4 markets * all games * 3x daily.
DEFAULT_MARKETS = ["pitcher_strikeouts", "batter_home_runs",
                   "batter_hits", "batter_total_bases"]

# Quota cap. Honors EDGESTAT_PROPS_MAX_GAMES env var so the workflow can run
# the same code on free vs paid tier without code changes.
# Free tier safe: 8. Paid ($20 tier, 20k credits/month): 32 (= all games).
MAX_GAMES = int(os.environ.get("EDGESTAT_PROPS_MAX_GAMES", "16"))

# Books takeable in the user's state for game lines; player props use DK only.
PROP_BOOK = "draftkings"

# Min edge magnitude (%) to surface in the UI as a "play".
MIN_EDGE_PLAY = 3.0


# -------------------- Odds API helpers --------------------

def _api_key() -> Optional[str]:
    return os.environ.get("ODDS_API_KEY")


def fetch_events() -> List[Dict[str, Any]]:
    """List today's MLB events. Free, no credit cost."""
    key = _api_key()
    if not key or requests is None:
        return []
    r = requests.get(f"{ODDS_BASE}/sports/baseball_mlb/events",
                     params={"apiKey": key}, timeout=15)
    r.raise_for_status()
    return r.json() or []


def fetch_event_props(event_id: str, markets: List[str]) -> Dict[str, Any]:
    """Fetch DK player props for one event. Costs len(markets) credits."""
    key = _api_key()
    if not key or requests is None:
        return {}
    r = requests.get(
        f"{ODDS_BASE}/sports/baseball_mlb/events/{event_id}/odds",
        params={
            "apiKey": key,
            "regions": "us",
            "markets": ",".join(markets),
            "oddsFormat": "american",
            "bookmakers": PROP_BOOK,
        },
        timeout=15,
    )
    if not r.ok:
        return {}
    return r.json()


# -------------------- Pricing math --------------------

def american_to_implied(price: int) -> float:
    """American odds -> implied probability (decimal)."""
    if price >= 0:
        return 100.0 / (price + 100.0)
    return -price / (-price + 100.0)


def implied_to_payout(price: int) -> float:
    """American odds -> decimal payout multiplier (incl. stake). $1 bet at +200 -> 3.0."""
    if price >= 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / -price


def edge_pct(model_prob: float, price: int) -> float:
    """Expected value as % of stake. +5 means +5% EV; play if > MIN_EDGE_PLAY."""
    payout = implied_to_payout(price)
    return round((model_prob * payout - 1.0) * 100.0, 2)


def poisson_p_at_least(lam: float, k: int) -> float:
    """P(X >= k) for X ~ Poisson(lam). Sum from k to ~3*lam tail."""
    if lam <= 0:
        return 0.0
    # P(X <= k-1) by CDF, then subtract from 1.
    cdf = 0.0
    term = math.exp(-lam)
    cdf += term
    for i in range(1, k):
        term *= lam / i
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


# -------------------- Player ID resolution --------------------

_player_id_cache: Dict[str, Optional[int]] = {}
_player_team_cache: Dict[int, Optional[int]] = {}


def _player_team(pid: Optional[int]) -> Optional[int]:
    """Return MLB team_id the player is currently on. Cached."""
    if not pid:
        return None
    if pid in _player_team_cache:
        return _player_team_cache[pid]
    payload = sr._get(
        f"{sr.MLB_BASE}/people/{pid}?hydrate=currentTeam",
        f"player_team_{pid}",
    )
    tid = None
    if payload and payload.get("people"):
        tid = (payload["people"][0].get("currentTeam") or {}).get("id")
    _player_team_cache[pid] = tid
    return tid


def _player_opp_team(pid: Optional[int], home_tid: Optional[int], away_tid: Optional[int]) -> Optional[int]:
    """Given the player and the matchup, return whichever team is on the OTHER side."""
    own = _player_team(pid)
    if own is None or (home_tid is None and away_tid is None):
        return home_tid or away_tid
    if own == home_tid:
        return away_tid
    if own == away_tid:
        return home_tid
    return home_tid or away_tid

def resolve_player_id(name: str) -> Optional[int]:
    """Look up MLB player ID by full name. Cached in-process + on disk."""
    if not name:
        return None
    if name in _player_id_cache:
        return _player_id_cache[name]
    cache_name = f"pid_byname_{name.replace(' ', '_')}"
    cached = sr._cache_get(cache_name)
    if cached is not None:
        _player_id_cache[name] = cached
        return cached
    pid = None
    if requests is not None:
        try:
            r = requests.get("https://statsapi.mlb.com/api/v1/people/search",
                             params={"names": name}, timeout=8)
            if r.ok:
                people = r.json().get("people", [])
                # Prefer active player; fallback to first.
                for p in people:
                    if p.get("active"):
                        pid = p.get("id")
                        break
                if pid is None and people:
                    pid = people[0].get("id")
        except Exception:
            pass
    sr._cache_put(cache_name, pid)
    _player_id_cache[name] = pid
    return pid


# -------------------- Per-player model projections --------------------

def _team_k_rate(team_id: Optional[int]) -> Optional[float]:
    """Team strikeout rate per PA (proxy for how often they whiff). League ~ 0.22."""
    if not team_id:
        return None
    try:
        season = sr._get(
            f"{sr.MLB_BASE}/teams/{team_id}/stats?stats=season&group=hitting&season={dt.date.today().year}",
            f"team_{team_id}_hitting_{dt.date.today().year}",
        )
        if not season or not season.get("stats"):
            return None
        s = sr._coerce_stat(season["stats"][0]["splits"][0]["stat"])
        k = s.get("strikeOuts"); pa = s.get("plateAppearances")
        if not k or not pa:
            return None
        return float(k) / float(pa)
    except Exception:
        return None


LEAGUE_K_RATE = 0.22  # rough MLB-wide K%


def project_pitcher_ks(pid: int, line: float, opp_team_id: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(K >= ceil(line)). Adjusts for opposing team's K rate; weights season + recent form."""
    season = sr.pitcher_season(pid) if pid else {}
    if not season or not season.get("inningsPitched"):
        return 0.50, {"reason": "no-data", "low_confidence": True}
    try:
        ip = float(season.get("inningsPitched", 0) or 0)
        starts = float(season.get("gamesStarted", 0) or 0)
        if starts < 3 or ip < 15:
            return 0.50, {"reason": "thin-sample", "starts": starts, "ip": ip, "low_confidence": True}
        avg_ip_per_start = ip / starts
        expected_ip = max(4.5, min(7.0, avg_ip_per_start))
        season_k9 = float(season.get("strikeoutsPer9Inn", 8.6) or 8.6)

        # Recent-form weighting: blend season K/9 with last 3 starts.
        # 60% recent + 40% season gives the model responsiveness without overfitting to noise.
        recent = sr.pitcher_recent_form(pid, n=3)
        recent_k9 = recent.get("k9") if recent and recent.get("k9") else None
        if recent_k9 is not None and recent.get("starts", 0) >= 2:
            blended_k9 = 0.6 * recent_k9 + 0.4 * season_k9
            recent_ip = recent.get("ip", 0)
            recent_starts = recent.get("starts", 0)
            recent_ip_per_start = (recent_ip / recent_starts) if recent_starts else avg_ip_per_start
            # Blend expected IP too -- if pitcher has been getting yanked early lately, lower expectation.
            blended_ip = 0.6 * max(3.0, min(7.5, recent_ip_per_start)) + 0.4 * expected_ip
        else:
            blended_k9 = season_k9
            blended_ip = expected_ip

        expected_ks = blended_k9 * blended_ip / 9.0
        opp_k = _team_k_rate(opp_team_id)
        opp_mult = (opp_k / LEAGUE_K_RATE) if opp_k else 1.0
        expected_ks_adj = expected_ks * opp_mult
        line_int = int(math.ceil(line))
        p_over = poisson_p_at_least(expected_ks_adj, line_int)
        return p_over, {
            "season_k9": round(season_k9, 2),
            "recent_k9": round(recent_k9, 2) if recent_k9 else None,
            "blended_k9": round(blended_k9, 2),
            "starts": int(starts),
            "expected_ip": round(blended_ip, 2),
            "opp_k_rate": round(opp_k, 3) if opp_k else None,
            "opp_mult": round(opp_mult, 3),
            "expected_ks_adj": round(expected_ks_adj, 2),
            "line_int": line_int,
        }
    except Exception as e:
        return 0.50, {"reason": f"exception: {e}", "low_confidence": True}


def _batter_season(pid: int) -> Dict[str, Any]:
    """Cached season hitting line."""
    if not pid:
        return {}
    season = sr._get(
        f"{sr.MLB_BASE}/people/{pid}/stats?stats=season&group=hitting&season={dt.date.today().year}",
        f"bhit_{pid}_{dt.date.today().year}",
    )
    if not season or not season.get("stats"):
        return {}
    splits = season["stats"][0].get("splits", [])
    if not splits:
        return {}
    return sr._coerce_stat(splits[0]["stat"])


# Expected PAs by batting-order slot (typical 9-inning game; data from FanGraphs analysis).
PA_BY_ORDER = {1: 4.65, 2: 4.55, 3: 4.45, 4: 4.35, 5: 4.25,
               6: 4.15, 7: 4.05, 8: 3.95, 9: 3.85}


def _expected_pa(order: Optional[int]) -> float:
    """Expected PAs given batting-order slot. Falls back to 4.2 (mid-order avg)."""
    if order and 1 <= order <= 9:
        return PA_BY_ORDER[order]
    return 4.2


def project_batter_hr(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    s = _batter_season(pid)
    pa, hr = s.get("plateAppearances"), s.get("homeRuns")
    if not pa or pa < 30 or hr is None:
        return 0.04, {"reason": "thin-sample", "pa": pa, "hr": hr, "low_confidence": True}
    hr_per_pa = float(hr) / float(pa)
    expected_pa_g = _expected_pa(order)
    expected_hr = hr_per_pa * expected_pa_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_hr, line_int)
    return p_over, {"pa": pa, "hr": hr, "hr_per_pa": round(hr_per_pa, 4),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_hr": round(expected_hr, 3), "line_int": line_int}


def project_batter_hits(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    s = _batter_season(pid)
    pa, hits = s.get("plateAppearances"), s.get("hits")
    if not pa or pa < 30 or hits is None:
        return 0.27, {"reason": "thin-sample", "pa": pa, "hits": hits, "low_confidence": True}
    h_per_pa = float(hits) / float(pa)
    expected_pa_g = _expected_pa(order)
    expected_h = h_per_pa * expected_pa_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_h, line_int)
    return p_over, {"pa": pa, "hits": hits, "h_per_pa": round(h_per_pa, 4),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_hits": round(expected_h, 3), "line_int": line_int}


def project_batter_tb(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.30, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    hits = float(s.get("hits", 0) or 0)
    doubles = float(s.get("doubles", 0) or 0)
    triples = float(s.get("triples", 0) or 0)
    hr = float(s.get("homeRuns", 0) or 0)
    singles = hits - doubles - triples - hr
    tb = singles + 2 * doubles + 3 * triples + 4 * hr
    tb_per_pa = tb / float(pa)
    expected_pa_g = _expected_pa(order)
    expected_tb = tb_per_pa * expected_pa_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_tb, line_int)
    return p_over, {"pa": pa, "tb_season": int(tb), "tb_per_pa": round(tb_per_pa, 4),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_tb": round(expected_tb, 3), "line_int": line_int}


# -------------------- Main loop --------------------

def build_props(markets: Optional[List[str]] = None, max_games: int = MAX_GAMES) -> Dict[str, Any]:
    """Walk events, pull DK props, project, compute edges."""
    markets = markets or DEFAULT_MARKETS
    if not _api_key():
        print("  [x] ODDS_API_KEY not set; skipping props pipeline")
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "games": [], "warning": "ODDS_API_KEY missing"}

    events = fetch_events()
    if not events:
        print("  [x] no events from Odds API")
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "games": [], "warning": "no events"}

    # Sort by commence_time, take soonest N to respect quota.
    events.sort(key=lambda e: e.get("commence_time", ""))
    events = events[:max_games]

    # Load calibration corrections from yesterday's outcomes settlement.
    try:
        from calibration_runner import load_corrections
        corrections = load_corrections()
    except Exception:
        corrections = {}
    if corrections:
        print(f"  -> applying calibration corrections: {corrections}")

    # Pull MLB schedule once to map Odds event_id -> MLB gamePk for lineup lookups.
    today_iso = dt.date.today().isoformat()
    mlb_sched = []
    if requests is not None:
        try:
            mlb_sched = requests.get(
                "https://statsapi.mlb.com/api/v1/schedule",
                params={"sportId": 1, "date": today_iso},
                timeout=10,
            ).json().get("dates", [])
        except Exception:
            mlb_sched = []
    # Build (home_name, away_name) -> gamePk index.
    pk_by_pair: Dict[Tuple[str, str], int] = {}
    for d in mlb_sched:
        for g in d.get("games", []):
            try:
                home = g["teams"]["home"]["team"]["name"]
                away = g["teams"]["away"]["team"]["name"]
                pk_by_pair[(home, away)] = g["gamePk"]
            except Exception:
                pass

    out_games = []
    for e in events:
        eid = e["id"]
        home_team_id = sr.team_id(e.get("home_team", ""))
        away_team_id = sr.team_id(e.get("away_team", ""))
        game_pk = pk_by_pair.get((e.get("home_team", ""), e.get("away_team", "")))
        # Pull lineup once per game (cached 15min in stats_repo).
        lineups = sr.game_lineups(game_pk) if game_pk else {"home": {}, "away": {}}
        lineup_posted = bool(lineups["home"] or lineups["away"])
        payload = fetch_event_props(eid, markets)
        bks = payload.get("bookmakers", [])
        if not bks:
            continue
        bk = bks[0]
        game_props = []
        for m in bk.get("markets", []):
            market_key = m["key"]
            outcomes = m.get("outcomes", [])
            by_player_line: Dict[Tuple[str, float], Dict[str, int]] = {}
            for o in outcomes:
                pl = o.get("description")
                line = o.get("point")
                if pl is None or line is None:
                    continue
                key = (pl, float(line))
                by_player_line.setdefault(key, {})[o["name"].lower()] = int(o["price"])
            for (player_name, line), prices in by_player_line.items():
                over_p = prices.get("over")
                under_p = prices.get("under")
                if over_p is None and under_p is None:
                    continue
                pid = resolve_player_id(player_name)
                # Determine which side this player plays for so we know the OPP team.
                opp_team_id = _player_opp_team(pid, home_team_id, away_team_id)
                # Lineup status (batter markets only): None=bench, {}=not posted, {order, side, pos}=in
                batter_order = None
                lineup_status = "unknown"
                if market_key.startswith("batter_"):
                    if not lineup_posted:
                        lineup_status = "lineup-not-posted"
                    elif pid:
                        for side_key in ("home", "away"):
                            if pid in lineups[side_key]:
                                batter_order = lineups[side_key][pid].get("order")
                                lineup_status = f"in-lineup-{batter_order}"
                                break
                        if batter_order is None:
                            lineup_status = "not-in-lineup"
                if market_key == "pitcher_strikeouts":
                    p_over, dbg = project_pitcher_ks(pid, line, opp_team_id)
                elif market_key == "batter_home_runs":
                    p_over, dbg = project_batter_hr(pid, line, batter_order)
                elif market_key == "batter_hits":
                    p_over, dbg = project_batter_hits(pid, line, batter_order)
                elif market_key == "batter_total_bases":
                    p_over, dbg = project_batter_tb(pid, line, batter_order)
                else:
                    continue
                dbg["lineup_status"] = lineup_status
                # Apply calibration correction from yesterday's outcomes.
                cf = corrections.get(market_key, 1.0)
                p_over_raw = p_over
                if cf != 1.0:
                    p_over = max(0.001, min(0.999, p_over * cf))
                    dbg["correction_applied"] = round(cf, 4)
                    dbg["p_over_raw"] = round(p_over_raw, 4)
                row: Dict[str, Any] = {
                    "player": player_name,
                    "player_id": pid,
                    "market": market_key,
                    "line": line,
                    "dk_over": over_p,
                    "dk_under": under_p,
                    "model_prob_over": round(p_over, 4),
                    "model_prob_under": round(1.0 - p_over, 4),
                    "debug": dbg,
                }
                # Compute edges for both sides (only one will be positive).
                if over_p is not None:
                    row["edge_over_pct"] = edge_pct(p_over, over_p)
                if under_p is not None:
                    row["edge_under_pct"] = edge_pct(1.0 - p_over, under_p)
                # Top-line pick: side with higher positive edge.
                best_side, best_edge = None, -999.0
                for side, eg in (("OVER", row.get("edge_over_pct", -999)),
                                 ("UNDER", row.get("edge_under_pct", -999))):
                    if eg is not None and eg > best_edge:
                        best_side, best_edge = side, eg
                low_conf = bool(dbg.get("low_confidence"))
                # Lineup-aware filter (preferred when MLB has posted the card):
                # confirmed-not-in-lineup => hard SKIP. lineup-not-posted falls back
                # to the long-odds bench heuristic.
                if market_key.startswith("batter_"):
                    if lineup_status == "not-in-lineup":
                        low_conf = True
                        row["bench_flag"] = True
                    elif lineup_status == "lineup-not-posted":
                        # Fallback heuristic when lineup hasn't dropped yet.
                        if line <= 0.5 and over_p is not None and over_p > 200:
                            low_conf = True
                            row["bench_flag"] = True
                # If projection is thin or edge is suspiciously huge, downgrade.
                if low_conf or best_edge >= 35.0:
                    row["play"] = "SKIP"
                    row["play_reason"] = "low-confidence" if low_conf else "edge>35% (suspect)"
                else:
                    row["play"] = best_side if best_edge >= MIN_EDGE_PLAY else "SKIP"
                row["best_edge_pct"] = best_edge if best_edge > -999 else None
                row["low_confidence"] = low_conf
                game_props.append(row)
        out_games.append({
            "event_id": eid,
            "matchup": f"{e.get('away_team')} @ {e.get('home_team')}",
            "commence_time": e.get("commence_time"),
            "props": sorted(game_props, key=lambda r: abs(r.get("best_edge_pct") or 0), reverse=True),
        })

    # Flat top-edges list across all games.
    all_props = []
    for g in out_games:
        for p in g["props"]:
            all_props.append({**p, "matchup": g["matchup"], "commence_time": g["commence_time"]})
    all_props.sort(key=lambda r: abs(r.get("best_edge_pct") or 0), reverse=True)

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "book": PROP_BOOK,
        "markets": markets,
        "games": out_games,
        "top_edges": all_props[:25],
        "quota_note": f"Capped at {max_games} games to fit the free Odds API tier.",
    }


def write_props(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    n_props = sum(len(g["props"]) for g in payload["games"])
    n_plays = sum(1 for p in payload.get("top_edges", []) if p.get("play") != "SKIP")
    print(f"Wrote props -> {path}")
    print(f"  Games covered: {len(payload['games'])}")
    print(f"  Props analyzed: {n_props}")
    print(f"  Playable (>= {MIN_EDGE_PLAY}% edge): {n_plays}")


if __name__ == "__main__":
    payload = build_props()
    write_props(payload)
    # Print top 5 edges
    for r in payload.get("top_edges", [])[:5]:
        print(f"  {r['play']:5} {r['player']:24} {r['market']:22} {r['line']:>5} | "
              f"DK {r.get('dk_over')}/{r.get('dk_under')} | model {r['model_prob_over']:.2%} | "
              f"edge {r.get('best_edge_pct')}%")
