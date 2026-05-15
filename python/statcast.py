"""
EdgeStat -- Baseball Savant (Statcast) feed.

Downloads + caches two leaderboard CSVs daily from baseballsavant.mlb.com:
  - PITCHER expected statistics + K%/BB%/Whiff%: xERA, xwOBA, k_percent, bb_percent, whiff_percent
  - BATTER expected statistics: xBA, xSLG, xwOBA, xOBP, barrel_pct, hard_hit_pct, sweet_spot_pct, sprint_speed

These metrics are the gold standard for projecting future performance because
they normalize out the luck/BABIP variance in raw stats:
  - xBA = batting avg you'd expect from your actual quality-of-contact (exit velo + launch angle)
  - xSLG = same idea for SLG
  - Barrel% = % of batted balls hit at the optimal exit velo + launch angle combo (barrels go for HR ~50% of the time, .800+ wOBA)
  - K% / Whiff% = much more stable + predictive than K/9
  - xwOBA = the single best summary statistic for an MLB hitter

Cache 24h since these update once daily on Savant. Single HTTP call covers
the whole league.
"""
from __future__ import annotations

import os
import io
import csv
import json
import time
import datetime as dt
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    requests = None  # type: ignore


CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache", "statcast")
CACHE_TTL = 24 * 3600   # 24 hours
SAVANT_BASE = "https://baseballsavant.mlb.com/leaderboard/custom"
HEADERS = {"User-Agent": "edgestat/1.0 (research)"}


# -------------------- Cache --------------------

def _cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{name}.json")


def _cache_get(name: str) -> Optional[Dict[str, Any]]:
    p = _cache_path(name)
    if not os.path.exists(p) or time.time() - os.path.getmtime(p) > CACHE_TTL:
        return None
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return None


def _cache_put(name: str, data: Dict[str, Any]) -> None:
    try:
        with open(_cache_path(name), "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# -------------------- Leaderboard fetchers --------------------

def _fetch_csv(params: Dict[str, str]) -> Optional[str]:
    if requests is None:
        return None
    try:
        r = requests.get(SAVANT_BASE, params=params, headers=HEADERS, timeout=30)
        if not r.ok:
            return None
        return r.text.lstrip("﻿")
    except Exception:
        return None


def _parse_rows(csv_text: str) -> Dict[int, Dict[str, Any]]:
    """Parse Savant CSV into {player_id: row_dict}."""
    out: Dict[int, Dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for r in reader:
        try:
            pid = int(r.get("player_id") or 0)
        except (ValueError, TypeError):
            continue
        if not pid:
            continue
        cleaned: Dict[str, Any] = {}
        for k, v in r.items():
            if v in (None, ""):
                cleaned[k] = None
            else:
                try:
                    cleaned[k] = float(v)
                except ValueError:
                    cleaned[k] = v
        out[pid] = cleaned
    return out


def pitcher_leaderboard(season: Optional[int] = None) -> Dict[int, Dict[str, Any]]:
    """Return {player_id: {xera, xwoba, k_percent, bb_percent, whiff_percent, barrel_batted_rate}}."""
    season = season or dt.date.today().year
    cache_name = f"pitchers_{season}"
    c = _cache_get(cache_name)
    if c is not None:
        return {int(k): v for k, v in c.items()}
    params = {
        "year": str(season), "type": "pitcher", "filter": "", "min": "20",
        "selections": "p_game,p_formatted_ip,k_percent,bb_percent,whiff_percent,xera,xwoba,barrel_batted_rate",
        "chart": "false", "x": "p_game", "y": "p_game", "r": "no",
        "chartType": "beeswarm", "sort": "4", "sortDir": "desc", "csv": "true",
    }
    text = _fetch_csv(params)
    if not text:
        return {}
    parsed = _parse_rows(text)
    _cache_put(cache_name, {str(k): v for k, v in parsed.items()})
    return parsed


def batter_leaderboard(season: Optional[int] = None) -> Dict[int, Dict[str, Any]]:
    """Return {player_id: {xba, xslg, xwoba, xobp, barrel_pct, hard_hit_pct, sweet_spot_pct, sprint_speed}}."""
    season = season or dt.date.today().year
    cache_name = f"batters_{season}"
    c = _cache_get(cache_name)
    if c is not None:
        return {int(k): v for k, v in c.items()}
    params = {
        "year": str(season), "type": "batter", "filter": "", "min": "30",
        "selections": "b_game,xba,xslg,xwoba,xobp,k_percent,bb_percent,barrel_batted_rate,hard_hit_percent,sweet_spot_percent,sprint_speed",
        "chart": "false", "x": "b_game", "y": "b_game", "r": "no",
        "chartType": "beeswarm", "sort": "4", "sortDir": "desc", "csv": "true",
    }
    text = _fetch_csv(params)
    if not text:
        return {}
    parsed = _parse_rows(text)
    _cache_put(cache_name, {str(k): v for k, v in parsed.items()})
    return parsed


# -------------------- Lookup helpers --------------------

def pitcher_stats(pid: int) -> Dict[str, Any]:
    """Return Statcast dict for a pitcher. {} if not in leaderboard (low sample)."""
    return pitcher_leaderboard().get(pid, {})


def pitcher_arsenal_all(season: Optional[int] = None) -> Dict[int, List[Dict[str, Any]]]:
    """Return {player_id: [{pitch_type, pitch_name, pitches, usage_pct, whiff_pct, k_pct, xwoba, ...}]}.

    Per-pitcher list of every pitch type they've thrown, with quality metrics.
    Source: baseballsavant pitch-arsenal-stats leaderboard.
    """
    season = season or dt.date.today().year
    cache_name = f"arsenal_{season}"
    c = _cache_get(cache_name)
    if c is not None:
        return {int(k): v for k, v in c.items()}
    url = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
    params = {
        "type": "pitcher", "year": str(season), "min": "20",
        "pitchType": "", "hand": "", "csv": "true",
    }
    if requests is None:
        return {}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if not r.ok:
            return {}
        text = r.text.lstrip("﻿")
    except Exception:
        return {}
    out: Dict[int, List[Dict[str, Any]]] = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            pid = int(row.get("player_id") or 0)
        except (ValueError, TypeError):
            continue
        if not pid:
            continue
        entry: Dict[str, Any] = {}
        for k, v in row.items():
            if v in (None, ""):
                entry[k] = None
            else:
                try:
                    entry[k] = float(v)
                except ValueError:
                    entry[k] = v
        out.setdefault(pid, []).append(entry)
    # Sort each pitcher's pitches by usage descending
    for pid in out:
        out[pid].sort(key=lambda r: r.get("pitch_usage") or 0, reverse=True)
    _cache_put(cache_name, {str(k): v for k, v in out.items()})
    return out


def pitcher_arsenal(pid: int) -> List[Dict[str, Any]]:
    """Return list of {pitch_name, pitch_type, usage, whiff%, K%, xwoba} for pitcher."""
    return pitcher_arsenal_all().get(pid, [])


def batter_vs_pitch_all(season: Optional[int] = None) -> Dict[int, List[Dict[str, Any]]]:
    """Return {player_id: [{pitch_type, pitch_name, est_woba, est_ba, est_slg,
                            whiff_pct, k_pct, hard_hit_pct, pitches}]}."""
    season = season or dt.date.today().year
    cache_name = f"batter_vs_pitch_{season}"
    c = _cache_get(cache_name)
    if c is not None:
        return {int(k): v for k, v in c.items()}
    url = "https://baseballsavant.mlb.com/leaderboard/pitch-arsenal-stats"
    params = {
        "type": "batter", "year": str(season), "min": "20",
        "pitchType": "", "hand": "", "csv": "true",
    }
    if requests is None:
        return {}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if not r.ok:
            return {}
        text = r.text.lstrip("﻿")
    except Exception:
        return {}
    out: Dict[int, List[Dict[str, Any]]] = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        try:
            pid = int(row.get("player_id") or 0)
        except (ValueError, TypeError):
            continue
        if not pid:
            continue
        entry: Dict[str, Any] = {}
        for k, v in row.items():
            if v in (None, ""):
                entry[k] = None
            else:
                try:
                    entry[k] = float(v)
                except ValueError:
                    entry[k] = v
        out.setdefault(pid, []).append(entry)
    _cache_put(cache_name, {str(k): v for k, v in out.items()})
    return out


def batter_vs_pitch(pid: int) -> List[Dict[str, Any]]:
    return batter_vs_pitch_all().get(pid, [])


def matchup_xwoba(pitcher_arsenal_list: List[Dict[str, Any]],
                   batter_vs_pitch_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute weighted xwOBA for a specific pitcher-vs-batter matchup.

    Sum over pitch types of (pitcher_usage_pct/100) * (batter_xwoba_vs_that_type).
    If batter has no record vs a pitch type, fall back to league avg (.320).
    """
    if not pitcher_arsenal_list or not batter_vs_pitch_list:
        return {}
    batter_by_pt = {p.get("pitch_type"): p for p in batter_vs_pitch_list
                    if p.get("pitch_type")}
    total_usage = 0.0
    weighted = 0.0
    breakdown = []
    for ap in pitcher_arsenal_list:
        pt = ap.get("pitch_type")
        usage = ap.get("pitch_usage") or 0
        if not pt or usage <= 0:
            continue
        usage_frac = usage / 100.0
        b = batter_by_pt.get(pt) or {}
        b_xwoba = b.get("est_woba")
        if b_xwoba is None or b_xwoba == "":
            b_xwoba = 0.320   # league average fallback
        b_xwoba = float(b_xwoba)
        total_usage += usage_frac
        weighted += b_xwoba * usage_frac
        breakdown.append({
            "pitch": ap.get("pitch_name"),
            "pitch_type": pt,
            "pitcher_usage_pct": usage,
            "batter_xwoba_vs": b_xwoba,
            "pitcher_xwoba_allowed_overall": ap.get("est_woba") or ap.get("xwoba"),
        })
    if total_usage <= 0:
        return {}
    matchup = weighted / total_usage
    return {
        "matchup_xwoba": round(matchup, 4),
        "league_xwoba_baseline": 0.320,
        "delta_vs_league": round(matchup - 0.320, 4),
        "breakdown": breakdown,
    }


def batter_stats(pid: int) -> Dict[str, Any]:
    """Return Statcast dict for a batter. {} if not in leaderboard."""
    return batter_leaderboard().get(pid, {})


if __name__ == "__main__":
    print("Pitcher leaderboard:")
    pl = pitcher_leaderboard()
    print(f"  {len(pl)} pitchers")
    # Show a few samples
    for pid, r in list(pl.items())[:3]:
        print(f"  pid={pid} K%={r.get('k_percent')} Whiff%={r.get('whiff_percent')} xERA={r.get('xera')} xwOBA={r.get('xwoba')}")
    print("Batter leaderboard:")
    bl = batter_leaderboard()
    print(f"  {len(bl)} batters")
    for pid, r in list(bl.items())[:3]:
        print(f"  pid={pid} xBA={r.get('xba')} xSLG={r.get('xslg')} Barrel%={r.get('barrel_batted_rate')}")
