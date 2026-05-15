"""
EdgeStat - daily pipeline.

End-to-end:
  1. Pull schedule + odds from APIs (real data) or fall back to DEMO_SLATE.
  2. Hydrate per-game context (pitchers, parks, weather, umpire).
  3. Run mlb_model.project_game() on each.
  4. Filter to +EV plays above edge threshold.
  5. Pick Play of the Day (highest-confidence, highest-edge).
  6. Write a JSON manifest the front-end can hot-reload.

Cron it at 7:00 ET every morning and re-run hourly to catch line moves.

`python pipeline.py` tries real data first (needs ODDS_API_KEY). Pass --demo to
force synthetic data.
"""
from __future__ import annotations

import json
import os
import sys
import datetime as dt
from typing import Any, Dict, List, Optional

from mlb_model import project_game, GameInput, TeamFactor, PitcherFactor, GameContext


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "today.json")

# MLB full team name → 3-letter code used across the model and front-end.
TEAM_CODE = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL", "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS", "Chicago Cubs": "CHC", "Chicago White Sox": "CHW",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE", "Colorado Rockies": "COL",
    "Detroit Tigers": "DET", "Houston Astros": "HOU", "Kansas City Royals": "KCR",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Oakland Athletics": "OAK", "Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SDP", "San Francisco Giants": "SFG", "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBR", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN",
}

# League-average proxies used when we don't have a paid stats feed (FanGraphs).
# The model is robust to these because most of the edge comes from price + pitcher + park.
LEAGUE_AVG_TEAM = {"offensive_wrc_plus": 100, "bullpen_era_fip_delta": 0.0, "rest_days": 1}
LEAGUE_AVG_PITCHER = {"xfip": 4.10, "k_per_9": 8.6, "bb_per_9": 3.1, "hand": "R"}


# --- Static lookup tables. In production these come from your DB / nightly refresh ---

PARK_FACTORS = {
    "Dodger Stadium": 0.96, "Petco Park": 0.91, "Yankee Stadium": 1.08,
    "Fenway Park": 1.05, "Citizens Bank Park": 1.06, "Truist Park": 1.02,
    "Coors Field": 1.20, "Wrigley Field": 1.00, "Citi Field": 0.95,
    "Oracle Park": 0.89, "Globe Life Field": 1.04, "Minute Maid Park": 1.01,
    "Daikin Park": 1.01, "Tropicana Field": 0.93, "Rogers Centre": 1.03,
    "Great American Ball Park": 1.12, "Busch Stadium": 0.98, "Chase Field": 1.02,
    "Nationals Park": 0.99, "Oriole Park at Camden Yards": 1.04,
    "Comerica Park": 0.97, "Progressive Field": 0.99,
    "American Family Field": 1.04, "Target Field": 1.00,
    "Kauffman Stadium": 0.98, "Angel Stadium": 1.00,
    "Oakland Coliseum": 0.93, "Sutter Health Park": 1.05,
    "T-Mobile Park": 0.92, "Rate Field": 1.03, "loanDepot park": 0.94,
    "PNC Park": 0.95, "UNIQLO Field at Dodger Stadium": 0.96,
}

# Park HR factor split by batter handedness. Multiplier on overall park factor.
# Yankee Stadium's RF short porch favors LHB; Fenway's Green Monster favors RHB.
# 1.00 = no platoon effect; >1 favors hitters of this hand.
PARK_HANDEDNESS = {
    "Yankee Stadium":       {"L": 1.12, "R": 0.98},   # short RF porch -> LHB HRs
    "Fenway Park":          {"L": 0.96, "R": 1.10},   # Green Monster -> RHB doubles/HRs
    "Citizens Bank Park":   {"L": 1.08, "R": 1.02},   # short RF
    "Citi Field":           {"L": 0.95, "R": 0.97},   # both suppress
    "Oracle Park":          {"L": 0.82, "R": 0.95},   # Triples Alley kills LHB HRs
    "Coors Field":          {"L": 1.18, "R": 1.20},   # thin air for all
    "Great American Ball Park": {"L": 1.14, "R": 1.10},  # tiny park
    "Tropicana Field":      {"L": 0.94, "R": 0.93},
    "Petco Park":           {"L": 0.90, "R": 0.92},   # pitcher's park
    "Dodger Stadium":       {"L": 0.97, "R": 0.95},
    "UNIQLO Field at Dodger Stadium": {"L": 0.97, "R": 0.95},
    "T-Mobile Park":        {"L": 0.91, "R": 0.93},   # marine air
}


def run_pipeline(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a list of game dicts into a daily manifest."""
    out_games = []
    best = None
    for g in games:
        proj = project_game(_to_input(g))
        record = {
            "matchup": f"{g['away']['code']} @ {g['home']['code']}",
            "time": g.get("time", "TBD"),
            "park": g.get("park", "Unknown"),
            "model": {
                "fair_home_ml": proj.fair_ml_home,
                "fair_away_ml": proj.fair_ml_away,
                "fair_total": round(proj.fair_total, 2),
                "p_home_win": round(proj.p_home_win, 4),
                "p_away_win": round(proj.p_away_win, 4),
                "p_over_market": round(proj.p_over.get(g.get("market_total", 8.5), 0), 4),
            },
            "market": {
                "home_ml": g.get("market_ml_home"),
                "away_ml": g.get("market_ml_away"),
                "total": g.get("market_total"),
                "book": g.get("market_book"),
            },
            "weather": {k: v for k, v in (g.get("ctx") or {}).items()
                        if k in ("temp_f", "wind_mph", "is_indoor", "wind_dir_deg",
                                 "carry_index", "precip_pct")},
            "umpire": {k: v for k, v in (g.get("ctx") or {}).items()
                       if k in ("ump_name", "ump_label", "ump_k_mult")},
            "recommendations": proj.recommendations,
        }
        out_games.append(record)
        # Track the highest-edge play in the slate.
        for r in proj.recommendations:
            if best is None or r["edge_pct"] > best["edge_pct"]:
                best = {**r, "matchup": record["matchup"], "time": record["time"]}
    manifest = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": out_games,
        "play_of_day": best,
    }
    return manifest


_MODEL_CTX_KEYS = {"park_factor", "temp_f", "wind_mph", "is_indoor", "umpire_zone_size"}


def _to_input(g: Dict[str, Any]) -> GameInput:
    ctx = {k: v for k, v in g["ctx"].items() if k in _MODEL_CTX_KEYS}
    return GameInput(
        away=TeamFactor(**g["away"]),
        home=TeamFactor(**g["home"]),
        away_pitcher=PitcherFactor(**g["away_pitcher"]),
        home_pitcher=PitcherFactor(**g["home_pitcher"]),
        ctx=GameContext(**ctx),
        market_total=g.get("market_total", 8.5),
        market_ml_away=g.get("market_ml_away", 100),
        market_ml_home=g.get("market_ml_home", -110),
    )


def write_manifest(manifest: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote manifest -> {path}")
    print(f"  Games: {len(manifest['games'])}")
    if manifest.get("play_of_day"):
        pod = manifest["play_of_day"]
        print(f"  Play of Day: {pod['matchup']} | {pod['label']} | "
              f"edge +{pod['edge_pct']:.2f}% | {pod['kelly_units']:.1f}u")


# --- Demo: hard-coded slate from data.js, fully self-contained ---

DEMO_SLATE = [
    {
        "time": "7:05p ET", "park": "Petco Park", "market_total": 8.0,
        "market_ml_away": +126, "market_ml_home": -148,
        "away": {"code": "SDP", "offensive_wrc_plus": 104, "bullpen_era_fip_delta": +0.41, "rest_days": 1},
        "home": {"code": "LAD", "offensive_wrc_plus": 124, "bullpen_era_fip_delta": -0.46, "rest_days": 1},
        "away_pitcher": {"name": "Darvish", "xfip": 4.12, "k_per_9": 9.1, "bb_per_9": 2.8, "hand": "R"},
        "home_pitcher": {"name": "Yamamoto", "xfip": 2.89, "k_per_9": 10.4, "bb_per_9": 2.1, "hand": "R"},
        "ctx": {"park_factor": 0.91, "temp_f": 62, "wind_mph": -6, "umpire_zone_size": 0.018, "is_indoor": False},
    },
    {
        "time": "6:45p ET", "park": "Yankee Stadium", "market_total": 9.0,
        "market_ml_away": +115, "market_ml_home": -128,
        "away": {"code": "BOS", "offensive_wrc_plus": 109, "bullpen_era_fip_delta": +0.18, "rest_days": 1},
        "home": {"code": "NYY", "offensive_wrc_plus": 119, "bullpen_era_fip_delta": -0.22, "rest_days": 1},
        "away_pitcher": {"name": "Crochet", "xfip": 3.05, "k_per_9": 11.8, "bb_per_9": 2.0, "hand": "L"},
        "home_pitcher": {"name": "Cole", "xfip": 3.18, "k_per_9": 11.2, "bb_per_9": 2.4, "hand": "R"},
        "ctx": {"park_factor": 1.08, "temp_f": 71, "wind_mph": 12, "umpire_zone_size": -0.01, "is_indoor": False},
    },
    {
        "time": "9:40p ET", "park": "Coors Field", "market_total": 10.5,
        "market_ml_away": -110, "market_ml_home": +100,
        "away": {"code": "CIN", "offensive_wrc_plus": 105, "bullpen_era_fip_delta": -0.05, "rest_days": 1},
        "home": {"code": "COL", "offensive_wrc_plus": 92,  "bullpen_era_fip_delta": +0.55, "rest_days": 1},
        "away_pitcher": {"name": "Greene", "xfip": 3.40, "k_per_9": 11.0, "bb_per_9": 3.0, "hand": "R"},
        "home_pitcher": {"name": "Freeland", "xfip": 4.80, "k_per_9": 6.3, "bb_per_9": 2.7, "hand": "L"},
        "ctx": {"park_factor": 1.20, "temp_f": 74, "wind_mph": 4, "umpire_zone_size": 0.0, "is_indoor": False},
    },
]


def _et_time(iso_utc: str) -> str:
    """'2026-05-14T16:35:00Z' → '12:35p ET'. Naive offset (UTC-4 EDT)."""
    try:
        t = dt.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        et = t.astimezone(dt.timezone(dt.timedelta(hours=-4)))
        hour = et.hour % 12 or 12
        ampm = "p" if et.hour >= 12 else "a"
        return f"{hour}:{et.minute:02d}{ampm} ET"
    except Exception:
        return "TBD"


def _american_to_int(price: Any) -> Optional[int]:
    try:
        return int(round(float(price)))
    except Exception:
        return None


# Books Brandon can actually bet at in his state. Game lines come from
# DraftKings (the only traditional sportsbook of the three). PrizePicks and
# Sleeper are DFS pick-em — player props only, no h2h/totals — and need a
# separate pipeline (see TODO in matchup_engine.py / props.html).
TAKEABLE_BOOKS = ["draftkings"]


def _consensus_odds(event: Dict[str, Any], home_name: str, away_name: str,
                    books: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return price snapshot from the configured takeable books only.

    Default: DraftKings. We use *the price Brandon can actually bet*, not a
    cross-market average — model edges must compare to the actual line he'll
    take. If DK isn't pricing the event, returns None values and the slate
    falls back to defaults.
    """
    books = books or TAKEABLE_BOOKS
    h2h_h, h2h_a, tot_pts, used_books = [], [], [], []
    for bk in event.get("bookmakers", []):
        if bk.get("key") not in books:
            continue
        used_books.append(bk["key"])
        for m in bk.get("markets", []):
            if m["key"] == "h2h":
                for o in m.get("outcomes", []):
                    if o["name"] == home_name: h2h_h.append(o["price"])
                    elif o["name"] == away_name: h2h_a.append(o["price"])
            elif m["key"] == "totals":
                for o in m.get("outcomes", []):
                    if "point" in o: tot_pts.append(o["point"])
    avg = lambda xs: round(sum(xs) / len(xs)) if xs else None
    return {
        "ml_home": avg(h2h_h),
        "ml_away": avg(h2h_a),
        "total": round(sum(tot_pts) / len(tot_pts), 1) if tot_pts else None,
        "book": "+".join(used_books) if used_books else None,
    }


def _team_dict_real(team_id_or_none: Optional[int], code: str) -> Dict[str, Any]:
    """Build TeamFactor dict from real season stats, falling back to league avg."""
    import stats_repo as sr
    if not team_id_or_none:
        return {"code": code, **LEAGUE_AVG_TEAM}
    try:
        off = sr.team_offensive_index(team_id_or_none)
        bp = sr.team_bullpen_delta(team_id_or_none)
    except Exception:
        return {"code": code, **LEAGUE_AVG_TEAM}
    return {"code": code, "offensive_wrc_plus": off, "bullpen_era_fip_delta": bp, "rest_days": 1}


def _fip_from_season(s: Dict[str, Any]) -> Optional[float]:
    """FIP = (13*HR + 3*BB - 2*K)/IP + 3.10. Returns None if IP=0."""
    ip = s.get("inningsPitched")
    if not ip:
        return None
    try:
        hr = s.get("homeRuns", 0) or 0
        bb = s.get("baseOnBalls", 0) or 0
        k = s.get("strikeOuts", 0) or 0
        return round((13 * hr + 3 * bb - 2 * k) / ip + 3.10, 2)
    except Exception:
        return None


def _pitcher_dict_real(pid: Optional[int], name: Optional[str]) -> Dict[str, Any]:
    """Build PitcherFactor dict from real season stats."""
    import stats_repo as sr
    if not pid:
        return {**LEAGUE_AVG_PITCHER, "name": name or "TBD"}
    try:
        s = sr.pitcher_season(pid)
        hand = sr.pitcher_hand(pid)
    except Exception:
        return {**LEAGUE_AVG_PITCHER, "name": name or "TBD"}
    if not s:
        return {**LEAGUE_AVG_PITCHER, "name": name or "TBD"}
    fip = _fip_from_season(s)
    return {
        "name": name or "TBD",
        "xfip": fip if fip is not None else s.get("era", LEAGUE_AVG_PITCHER["xfip"]),
        "k_per_9": s.get("strikeoutsPer9Inn", LEAGUE_AVG_PITCHER["k_per_9"]),
        "bb_per_9": s.get("walksPer9Inn", LEAGUE_AVG_PITCHER["bb_per_9"]),
        "hand": hand or "R",
    }


def build_real_slate() -> Optional[List[Dict[str, Any]]]:
    """Build today's slate from MLB Stats API + The Odds API. None on any failure."""
    import data_fetcher as df
    import stats_repo as sr
    try:
        sched = df.fetch_today_schedule()
    except Exception as e:
        print(f"  [x] schedule fetch failed: {e}")
        return None
    if not sched:
        print("  [x] no games on today's schedule")
        return None

    try:
        # Restrict to takeable books to (a) avoid wasting API quota fetching
        # books Brandon can't use and (b) ensure prices reflect what he'll bet.
        odds_events = df.fetch_mlb_odds(bookmakers=",".join(TAKEABLE_BOOKS))
    except RuntimeError as e:
        print(f"  [x] odds fetch skipped: {e}")
        odds_events = []
    except Exception as e:
        print(f"  [x] odds fetch failed: {e}")
        odds_events = []

    odds_by_pair = {}
    for ev in odds_events:
        odds_by_pair[(ev["home_team"], ev["away_team"])] = ev

    slate = []
    for g in sched:
        if g.get("status") not in ("Scheduled", "Pre-Game", "Warmup", "Delayed Start: Rain"):
            continue
        home_name, away_name = g["home"], g["away"]
        home_code = TEAM_CODE.get(home_name, home_name[:3].upper())
        away_code = TEAM_CODE.get(away_name, away_name[:3].upper())
        home_tid = sr.team_id(home_name)
        away_tid = sr.team_id(away_name)
        ev = odds_by_pair.get((home_name, away_name))
        prices = _consensus_odds(ev, home_name, away_name) if ev else {"ml_home": None, "ml_away": None, "total": None}

        # Probable pitchers with IDs (preferred) or names only (fallback).
        pp = sr.probable_pitchers_for_game(g["gamePk"]) or {"home": {}, "away": {}}
        home_pid, home_pname = pp["home"].get("id"), pp["home"].get("name")
        away_pid, away_pname = pp["away"].get("id"), pp["away"].get("name")

        park_factor = PARK_FACTORS.get(g["venue"], 1.00)
        # Weather for ctx (mlb_model uses temp_f + wind_mph for run-environment).
        try:
            from weather import get_weather
            wx = get_weather(g["venue"], g.get("time"))
        except Exception:
            wx = {}
        ctx_temp = wx.get("temp_f", 70)
        ctx_wind = wx.get("wind_mph", 0)
        ctx_indoor = bool(wx.get("indoor"))
        carry = wx.get("carry_index")  # -1..+1 wind-to-CF signal (None if indoor)
        # Home Plate umpire tendency
        try:
            from umpires import get_home_plate_umpire
            ump = get_home_plate_umpire(g["gamePk"]) or {}
        except Exception:
            ump = {}
        ump_zone_size = (float(ump.get("k_mult", 1.0)) - 1.0)  # +0.04 = wider zone
        slate.append({
            "time": _et_time(g["time"]),
            "park": g["venue"],
            "market_total": prices["total"] or 8.5,
            "market_ml_away": prices["ml_away"] or 100,
            "market_ml_home": prices["ml_home"] or -110,
            "market_book": prices.get("book"),
            "away": _team_dict_real(away_tid, away_code),
            "home": _team_dict_real(home_tid, home_code),
            "away_pitcher": _pitcher_dict_real(away_pid, away_pname),
            "home_pitcher": _pitcher_dict_real(home_pid, home_pname),
            "ctx": {"park_factor": park_factor, "temp_f": ctx_temp, "wind_mph": ctx_wind,
                    "umpire_zone_size": ump_zone_size, "is_indoor": ctx_indoor,
                    "wind_dir_deg": wx.get("wind_dir_deg"), "carry_index": carry,
                    "precip_pct": wx.get("precip_pct"), "forecast_hour": wx.get("forecast_hour"),
                    "ump_name": ump.get("name"), "ump_label": ump.get("label"),
                    "ump_k_mult": ump.get("k_mult")},
            # Metadata for downstream tools (matchup engine, quirks, research page).
            # Stripped before passing to the model.
            "_meta": {
                "gamePk": g["gamePk"],
                "home_team_id": home_tid, "away_team_id": away_tid,
                "home_pitcher_id": home_pid, "away_pitcher_id": away_pid,
                "home_pitcher_name": home_pname, "away_pitcher_name": away_pname,
                "venue": g["venue"],
            },
        })
    return slate or None


def build_slate(force_demo: bool = False) -> List[Dict[str, Any]]:
    """Try real data first. If real fails AND demo isn't forced, emit a sentinel
    slate flagged with `is_demo: True` so downstream consumers (snapshot, outcomes,
    calibration) can skip these records instead of silently treating fake matchups
    as real settlements.

    The previous behavior was to silently return DEMO_SLATE on any failure -- that
    cost us yesterday's game-line settlements because outcomes.py tried to look up
    "SDP @ LAD" in the real 2026-05-14 MLB schedule (where SDP actually played MIL).
    """
    if force_demo:
        print("  -> demo mode (forced)")
        return [dict(g, is_demo=True) for g in DEMO_SLATE]
    print("  -> attempting real data pull")
    real = build_real_slate()
    if real:
        print(f"  [ok] real slate: {len(real)} games")
        return real
    print("  [!!] real-data pull failed -- returning DEMO_SLATE TAGGED is_demo=True")
    print("        Downstream snapshot/outcomes/calibration will skip these records.")
    return [dict(g, is_demo=True) for g in DEMO_SLATE]


if __name__ == "__main__":
    slate = build_slate(force_demo="--demo" in sys.argv)
    manifest = run_pipeline(slate)
    write_manifest(manifest)
    if manifest.get("play_of_day"):
        print(json.dumps(manifest["play_of_day"], indent=2))

    # Also write the matchup research digest. Failures here shouldn't break the
    # daily refresh -- the slate JSON is the critical artifact.
    try:
        from matchup_engine import build_all_matchups, write_matchups
        m_payload = build_all_matchups()
        write_matchups(m_payload)
    except Exception as e:
        print(f"  [x] matchup digest skipped: {e}")

    # Snapshot today's projections so tomorrow's outcomes job can settle them.
    try:
        from snapshot import snapshot_today
        paths = snapshot_today()
        print(f"  [ok] snapshotted {len(paths)} files to data/history/")
    except Exception as e:
        print(f"  [x] snapshot skipped: {e}")
