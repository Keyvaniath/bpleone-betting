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
# Override via EDGESTAT_PROPS_MARKETS env var (comma-separated).
# Free tier safe (~480 credits/month): 4 markets * 8 games * 1x daily.
# Paid $20 tier (20k credits/month): all 8 markets * 16 games * 3x daily.
_DEFAULT_MARKETS_SAFE = ["pitcher_strikeouts", "batter_home_runs",
                          "batter_hits", "batter_total_bases"]
_DEFAULT_MARKETS_FULL = ["pitcher_strikeouts", "batter_home_runs",
                          "batter_hits", "batter_total_bases",
                          "batter_singles", "batter_doubles",
                          "batter_runs_scored", "batter_rbis"]
_env_markets = os.environ.get("EDGESTAT_PROPS_MARKETS", "").strip()
if _env_markets:
    DEFAULT_MARKETS = [m.strip() for m in _env_markets.split(",") if m.strip()]
else:
    DEFAULT_MARKETS = _DEFAULT_MARKETS_SAFE

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


def project_pitcher_ks(pid: int, line: float, opp_team_id: Optional[int] = None,
                       umpire_k_mult: float = 1.0) -> Tuple[float, Dict[str, Any]]:
    """P(K >= ceil(line)).

    v2 (Statcast-enabled): uses xK% blended with traditional K/9, expected
    batters faced (BF) instead of innings, opp-team K-rate multiplier, and
    recent-form weighting. Falls back to v1 (K/9 only) if Statcast lookup
    returns nothing.
    """
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
        season_bf = float(season.get("battersFaced", 0) or 0)

        # Statcast-derived K% (more stable + predictive than K/9).
        try:
            import statcast as sc
            sc_p = sc.pitcher_stats(pid) or {}
        except Exception:
            sc_p = {}
        statcast_k_pct = sc_p.get("k_percent")
        statcast_whiff = sc_p.get("whiff_percent")

        # Recent-form K/9 blend.
        recent = sr.pitcher_recent_form(pid, n=3)
        recent_k9 = recent.get("k9") if recent and recent.get("k9") else None
        if recent_k9 is not None and recent.get("starts", 0) >= 2:
            blended_k9 = 0.6 * recent_k9 + 0.4 * season_k9
            recent_ip = recent.get("ip", 0)
            recent_starts = recent.get("starts", 0)
            recent_ip_per_start = (recent_ip / recent_starts) if recent_starts else avg_ip_per_start
            blended_ip = 0.6 * max(3.0, min(7.5, recent_ip_per_start)) + 0.4 * expected_ip
        else:
            blended_k9 = season_k9
            blended_ip = expected_ip

        # Expected batters faced this start. Use season's BF/IP ratio (typically ~4.3) * expected_ip.
        bf_per_ip = (season_bf / ip) if ip > 0 else 4.3
        expected_bf = bf_per_ip * blended_ip

        # Strikeout projection: prefer Statcast xK%, fall back to K/9 if missing.
        if statcast_k_pct is not None:
            # Blend xK% (Statcast, season) with implied K rate from blended K/9.
            blended_k_rate_from_k9 = blended_k9 / bf_per_ip / 9.0 * 9.0  # = blended_k9 / bf_per_ip
            blended_k_rate_from_k9 = blended_k_rate_from_k9 / 100.0 * 100.0  # noop, kept for readability
            # Actually simpler: K rate per BF from K/9: blended_k9 * (1 IP / bf_per_ip) / 9 = blended_k9 / (9*bf_per_ip)
            k_rate_from_k9 = blended_k9 / (9.0 * (bf_per_ip if bf_per_ip > 0 else 4.3))
            k_rate_statcast = statcast_k_pct / 100.0
            blended_k_rate = 0.5 * k_rate_statcast + 0.5 * k_rate_from_k9
            model_version = "v2-statcast"
        else:
            blended_k_rate = blended_k9 / (9.0 * (bf_per_ip if bf_per_ip > 0 else 4.3))
            model_version = "v1-k9-only"

        # Opp-team K rate adjustment.
        opp_k = _team_k_rate(opp_team_id)
        opp_mult = (opp_k / LEAGUE_K_RATE) if opp_k else 1.0
        # Cap the adjustment to +/- 25% to keep extreme matchups from runaway.
        opp_mult = max(0.75, min(1.25, opp_mult))
        adj_k_rate = blended_k_rate * opp_mult * umpire_k_mult
        expected_ks = adj_k_rate * expected_bf

        line_int = int(math.ceil(line))
        p_over = poisson_p_at_least(expected_ks, line_int)
        return p_over, {
            "model_version": model_version,
            "season_k9": round(season_k9, 2),
            "blended_k9": round(blended_k9, 2),
            "recent_k9": round(recent_k9, 2) if recent_k9 else None,
            "statcast_k_pct": statcast_k_pct,
            "statcast_whiff_pct": statcast_whiff,
            "starts": int(starts),
            "expected_ip": round(blended_ip, 2),
            "expected_bf": round(expected_bf, 1),
            "blended_k_rate": round(blended_k_rate, 4),
            "opp_k_rate": round(opp_k, 3) if opp_k else None,
            "opp_mult": round(opp_mult, 3),
            "expected_ks": round(expected_ks, 2),
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


def _statcast_batter(pid: int) -> Dict[str, Any]:
    """Best-effort Statcast lookup. {} on miss."""
    try:
        import statcast as sc
        return sc.batter_stats(pid) or {}
    except Exception:
        return {}


def _ab_per_pa(s: Dict[str, Any]) -> float:
    """Estimate AB rate from PA (PA includes BB/HBP/SAC). Default 0.88."""
    pa = s.get("plateAppearances")
    ab = s.get("atBats")
    if pa and ab and pa > 0:
        return float(ab) / float(pa)
    return 0.88


def project_batter_hr(pid: int, line: float, order: Optional[int] = None,
                       carry_index: Optional[float] = None,
                       park_factor: Optional[float] = None) -> Tuple[float, Dict[str, Any]]:
    """P(HR >= ceil(line)). v2: barrel% as primary signal; barrels convert to HR ~50%.

    Adjusts for park factor + wind carry when known.
    """
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    hr = s.get("homeRuns")
    if not pa or pa < 30 or hr is None:
        return 0.04, {"reason": "thin-sample", "pa": pa, "hr": hr, "low_confidence": True}

    sc_b = _statcast_batter(pid)
    barrel_pct = sc_b.get("barrel_batted_rate")  # % of batted-ball events
    expected_pa_g = _expected_pa(order)
    ab_pa = _ab_per_pa(s)
    # Expected batted-ball events = AB * (1 - K%) ≈ AB * 0.75 league avg.
    # Use Statcast K% if available, else season K rate proxy.
    k_pct = sc_b.get("k_percent")
    ab_g = expected_pa_g * ab_pa
    if k_pct is not None:
        bbe_g = ab_g * (1.0 - k_pct / 100.0)
    else:
        bbe_g = ab_g * 0.75
    # Park + wind multiplier for HR rate (carry_index in [-1, +1]).
    env_mult = 1.0
    if park_factor is not None:
        env_mult *= park_factor
    if carry_index is not None:
        env_mult *= 1.0 + 0.15 * carry_index   # +/- 15% from wind direction

    if barrel_pct is not None and barrel_pct > 0:
        # Barrels -> HR conversion is ~50% league-wide.
        expected_hr_statcast = (barrel_pct / 100.0) * bbe_g * 0.50 * env_mult
        # Blend with season HR/PA for stability.
        hr_per_pa = float(hr) / float(pa)
        expected_hr_season = hr_per_pa * expected_pa_g * env_mult
        expected_hr = 0.5 * expected_hr_statcast + 0.5 * expected_hr_season
        model_version = "v2-statcast-barrel"
    else:
        hr_per_pa = float(hr) / float(pa)
        expected_hr = hr_per_pa * expected_pa_g * env_mult
        model_version = "v1-season-hr-pa"

    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_hr, line_int)
    return p_over, {
        "model_version": model_version,
        "pa": pa, "hr": hr,
        "batting_order": order, "expected_pa": expected_pa_g,
        "barrel_pct": barrel_pct, "k_pct_statcast": k_pct,
        "park_factor": park_factor, "carry_index": carry_index, "env_mult": round(env_mult, 3),
        "expected_hr": round(expected_hr, 3), "line_int": line_int,
    }


def project_batter_hits(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(hits >= ceil(line)). v2: uses xBA when available (removes BABIP luck)."""
    s = _batter_season(pid)
    pa, hits = s.get("plateAppearances"), s.get("hits")
    if not pa or pa < 30 or hits is None:
        return 0.27, {"reason": "thin-sample", "pa": pa, "hits": hits, "low_confidence": True}
    sc_b = _statcast_batter(pid)
    xba = sc_b.get("xba")
    expected_pa_g = _expected_pa(order)
    ab_g = expected_pa_g * _ab_per_pa(s)
    season_ba = float(hits) / float(s.get("atBats", pa) or pa)
    if xba is not None and xba > 0:
        # 60% xBA + 40% actual; xBA leads but season hitting matters.
        blended_ba = 0.6 * xba + 0.4 * season_ba
        model_version = "v2-statcast-xba"
    else:
        blended_ba = season_ba
        model_version = "v1-season-ba"
    expected_h = blended_ba * ab_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_h, line_int)
    return p_over, {
        "model_version": model_version,
        "pa": pa, "hits": hits,
        "season_ba": round(season_ba, 3), "xba": xba, "blended_ba": round(blended_ba, 3),
        "batting_order": order, "expected_pa": expected_pa_g, "ab_g": round(ab_g, 2),
        "expected_hits": round(expected_h, 3), "line_int": line_int,
    }


def project_batter_runs(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(player scores >= ceil(line) runs)."""
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.50, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    runs = float(s.get("runs", 0) or 0)
    runs_per_pa = runs / float(pa)
    expected_pa_g = _expected_pa(order)
    expected_runs = runs_per_pa * expected_pa_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_runs, line_int)
    return p_over, {"model_version": "v1-season-runs", "pa": pa, "runs": runs,
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_runs": round(expected_runs, 3), "line_int": line_int}


def project_batter_rbis(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(player drives in >= ceil(line) runs)."""
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.50, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    rbis = float(s.get("rbi", 0) or 0)
    rbi_per_pa = rbis / float(pa)
    expected_pa_g = _expected_pa(order)
    expected_rbis = rbi_per_pa * expected_pa_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_rbis, line_int)
    return p_over, {"model_version": "v1-season-rbi", "pa": pa, "rbi": rbis,
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_rbis": round(expected_rbis, 3), "line_int": line_int}


def project_batter_hits_runs_rbis(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(H + R + RBI >= ceil(line)) -- one of PrizePicks' most popular markets."""
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.50, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    hits = float(s.get("hits", 0) or 0)
    runs = float(s.get("runs", 0) or 0)
    rbis = float(s.get("rbi", 0) or 0)
    expected_pa_g = _expected_pa(order)
    # Blend with Statcast where available for hits
    sc_b = _statcast_batter(pid)
    xba = sc_b.get("xba")
    ab_g = expected_pa_g * _ab_per_pa(s)
    season_ba = hits / float(s.get("atBats", pa) or pa)
    blended_ba = 0.6 * xba + 0.4 * season_ba if xba else season_ba
    exp_h = blended_ba * ab_g
    exp_r = (runs / float(pa)) * expected_pa_g
    exp_rbi = (rbis / float(pa)) * expected_pa_g
    expected_hrr = exp_h + exp_r + exp_rbi
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_hrr, line_int)
    return p_over, {"model_version": "v2-statcast-hrr" if xba else "v1-season-hrr",
                    "pa": pa, "h": int(hits), "r": int(runs), "rbi": int(rbis),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_h": round(exp_h, 2), "expected_r": round(exp_r, 2),
                    "expected_rbi": round(exp_rbi, 2),
                    "expected_hrr": round(expected_hrr, 3), "line_int": line_int}


def project_batter_singles(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(singles >= ceil(line))."""
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.40, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    hits = float(s.get("hits", 0) or 0)
    doubles = float(s.get("doubles", 0) or 0)
    triples = float(s.get("triples", 0) or 0)
    hr = float(s.get("homeRuns", 0) or 0)
    singles = hits - doubles - triples - hr
    rate = singles / float(s.get("atBats", pa) or pa)
    expected_pa_g = _expected_pa(order)
    ab_g = expected_pa_g * _ab_per_pa(s)
    expected_1b = rate * ab_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_1b, line_int)
    return p_over, {"model_version": "v1-season-1b", "pa": pa, "singles_season": int(singles),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_singles": round(expected_1b, 3), "line_int": line_int}


def project_batter_doubles(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(doubles >= ceil(line))."""
    s = _batter_season(pid)
    pa = s.get("plateAppearances")
    if not pa or pa < 30:
        return 0.25, {"reason": "thin-sample", "pa": pa, "low_confidence": True}
    doubles = float(s.get("doubles", 0) or 0)
    rate = doubles / float(s.get("atBats", pa) or pa)
    expected_pa_g = _expected_pa(order)
    ab_g = expected_pa_g * _ab_per_pa(s)
    expected_2b = rate * ab_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_2b, line_int)
    return p_over, {"model_version": "v1-season-2b", "pa": pa, "doubles_season": int(doubles),
                    "batting_order": order, "expected_pa": expected_pa_g,
                    "expected_doubles": round(expected_2b, 3), "line_int": line_int}


def project_batter_tb(pid: int, line: float, order: Optional[int] = None) -> Tuple[float, Dict[str, Any]]:
    """P(TB >= ceil(line)). v2: uses xSLG when available."""
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
    ab_season = float(s.get("atBats", pa) or pa)
    season_slg = tb / ab_season if ab_season else 0.0

    sc_b = _statcast_batter(pid)
    xslg = sc_b.get("xslg")
    expected_pa_g = _expected_pa(order)
    ab_g = expected_pa_g * _ab_per_pa(s)
    if xslg is not None and xslg > 0:
        blended_slg = 0.6 * xslg + 0.4 * season_slg
        model_version = "v2-statcast-xslg"
    else:
        blended_slg = season_slg
        model_version = "v1-season-slg"
    expected_tb = blended_slg * ab_g
    line_int = int(math.ceil(line))
    p_over = poisson_p_at_least(expected_tb, line_int)
    return p_over, {
        "model_version": model_version,
        "pa": pa, "tb_season": int(tb),
        "season_slg": round(season_slg, 3), "xslg": xslg, "blended_slg": round(blended_slg, 3),
        "batting_order": order, "expected_pa": expected_pa_g, "ab_g": round(ab_g, 2),
        "expected_tb": round(expected_tb, 3), "line_int": line_int,
    }


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
        lineups = sr.game_lineups(game_pk) if game_pk else {"home": {}, "away": {}}
        lineup_posted = bool(lineups["home"] or lineups["away"])
        # Park + weather + umpire for adjustments. Best-effort.
        venue = None
        for d in mlb_sched:
            for g in d.get("games", []):
                if g.get("gamePk") == game_pk:
                    venue = (g.get("venue") or {}).get("name")
                    break
        try:
            from pipeline import PARK_FACTORS
            park_factor = PARK_FACTORS.get(venue, 1.00) if venue else 1.00
        except Exception:
            park_factor = 1.00
        try:
            from weather import get_weather
            wx = get_weather(venue or "") if venue else {}
            carry_index = wx.get("carry_index") if not wx.get("indoor") else None
        except Exception:
            carry_index = None
        try:
            from umpires import k_multiplier
            umpire_k_mult = k_multiplier(game_pk) if game_pk else 1.0
        except Exception:
            umpire_k_mult = 1.0
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
                    p_over, dbg = project_pitcher_ks(pid, line, opp_team_id, umpire_k_mult)
                elif market_key == "batter_home_runs":
                    p_over, dbg = project_batter_hr(pid, line, batter_order,
                                                    carry_index=carry_index,
                                                    park_factor=park_factor)
                elif market_key == "batter_hits":
                    p_over, dbg = project_batter_hits(pid, line, batter_order)
                elif market_key == "batter_total_bases":
                    p_over, dbg = project_batter_tb(pid, line, batter_order)
                elif market_key == "batter_singles":
                    p_over, dbg = project_batter_singles(pid, line, batter_order)
                elif market_key == "batter_doubles":
                    p_over, dbg = project_batter_doubles(pid, line, batter_order)
                elif market_key == "batter_runs_scored":
                    p_over, dbg = project_batter_runs(pid, line, batter_order)
                elif market_key == "batter_rbis":
                    p_over, dbg = project_batter_rbis(pid, line, batter_order)
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
