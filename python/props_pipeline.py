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
DEFAULT_MARKETS = ["pitcher_strikeouts", "batter_home_runs"]

# Quota cap. Lift when user upgrades the Odds API tier.
MAX_GAMES = 8

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
    """P(K >= ceil(line)). Adjusts for opposing team's K rate; gates on sample size."""
    season = sr.pitcher_season(pid) if pid else {}
    if not season or not season.get("inningsPitched"):
        return 0.50, {"reason": "no-data", "low_confidence": True}
    try:
        ip = float(season.get("inningsPitched", 0) or 0)
        starts = float(season.get("gamesStarted", 0) or 0)
        # Quality gate: need >= 3 starts AND >= 15 IP for a real read.
        if starts < 3 or ip < 15:
            return 0.50, {"reason": "thin-sample", "starts": starts, "ip": ip, "low_confidence": True}
        avg_ip_per_start = ip / starts
        # Cap at 7 IP (rare deeper), floor at 4.5 (today's bullpens give starters 4.5+ minimum).
        expected_ip = max(4.5, min(7.0, avg_ip_per_start))
        k9 = float(season.get("strikeoutsPer9Inn", 8.6) or 8.6)
        expected_ks = k9 * expected_ip / 9.0
        # Opposing team K-rate adjustment.
        opp_k = _team_k_rate(opp_team_id)
        opp_mult = (opp_k / LEAGUE_K_RATE) if opp_k else 1.0
        expected_ks_adj = expected_ks * opp_mult
        line_int = int(math.ceil(line))
        p_over = poisson_p_at_least(expected_ks_adj, line_int)
        return p_over, {
            "k9": round(k9, 2), "starts": int(starts),
            "expected_ip": round(expected_ip, 2),
            "expected_ks_raw": round(expected_ks, 2),
            "opp_k_rate": round(opp_k, 3) if opp_k else None,
            "opp_mult": round(opp_mult, 3),
            "expected_ks_adj": round(expected_ks_adj, 2),
            "line_int": line_int,
        }
    except Exception as e:
        return 0.50, {"reason": f"exception: {e}", "low_confidence": True}


def project_batter_hr(pid: int, line: float) -> Tuple[float, Dict[str, Any]]:
    """P(player hits >= ceil(line) HRs in this game)."""
    if not pid:
        return 0.04, {"reason": "no-id"}
    try:
        season = sr._get(
            f"{sr.MLB_BASE}/people/{pid}/stats?stats=season&group=hitting&season={dt.date.today().year}",
            f"bhit_{pid}_{dt.date.today().year}",
        )
        if not season or not season.get("stats"):
            return 0.04, {"reason": "no-data"}
        splits = season["stats"][0].get("splits", [])
        if not splits:
            return 0.04, {"reason": "no-splits"}
        s = sr._coerce_stat(splits[0]["stat"])
        pa = s.get("plateAppearances")
        hr = s.get("homeRuns")
        if not pa or pa < 10 or hr is None:
            return 0.04, {"reason": "thin-sample", "pa": pa, "hr": hr}
        hr_per_pa = float(hr) / float(pa)
        # Expected PA for a starter: ~4.2; pinch hitters less.
        # Use 4.2 unless batting low in the order (no signal here yet -> assume starter).
        expected_pa = 4.2
        expected_hr = hr_per_pa * expected_pa
        line_int = int(math.ceil(line))  # over 0.5 -> need at least 1
        p_over = poisson_p_at_least(expected_hr, line_int)
        return p_over, {
            "pa": pa, "hr": hr, "hr_per_pa": round(hr_per_pa, 4),
            "expected_hr": round(expected_hr, 3), "line_int": line_int,
        }
    except Exception:
        return 0.04, {"reason": "exception"}


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

    out_games = []
    for e in events:
        eid = e["id"]
        home_team_id = sr.team_id(e.get("home_team", ""))
        away_team_id = sr.team_id(e.get("away_team", ""))
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
                if market_key == "pitcher_strikeouts":
                    p_over, dbg = project_pitcher_ks(pid, line, opp_team_id)
                elif market_key == "batter_home_runs":
                    p_over, dbg = project_batter_hr(pid, line)
                else:
                    continue
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
