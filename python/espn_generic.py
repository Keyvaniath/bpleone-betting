"""
EdgeStat -- generic ESPN scoreboard pipeline + win-probability model.

A single reusable engine that powers WNBA, MLS, EPL, Champions League, NFL,
NCAA Football, NCAA Baseball, and any other ESPN scoreboard sport. Each
sport-specific wrapper (wnba_pipeline.py, mls_pipeline.py, etc.) just calls
run() with its config.

Each sport config defines:
  - espn_path: e.g. "basketball/wnba"
  - hfa_elo: home-field/court advantage in ELO points
  - regulation_seconds: total game length for live win prob
  - n_periods: 4 for basketball, 2 for soccer halves, 3 for hockey, etc.

Output: data/<sport_key>_state.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _winpct_to_elo(wp: float, base: float = 1500) -> float:
    if wp <= 0.01: return base - 250
    if wp >= 0.99: return base + 250
    return base + 400 * math.log10(wp / (1 - wp))


def _elo_winprob(home_elo: float, away_elo: float, hfa: float = 35) -> float:
    diff = (home_elo + hfa) - away_elo
    return 1 / (1 + 10 ** (-diff / 400))


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _clock_to_seconds(clock_str: Optional[str]) -> int:
    if not clock_str or ":" not in clock_str: return 0
    try:
        parts = clock_str.split(":")
        return int(int(parts[0]) * 60 + float(parts[1]))
    except Exception:
        return 0


def _team_record(team_block: Dict[str, Any]) -> Dict[str, Any]:
    """Extract W/L (or W-L-T or W-L-OTL) from competitor.records[]."""
    out = {"wins": 0, "losses": 0, "ties": 0, "win_pct": 0.5, "summary": "0-0"}
    for r in (team_block.get("records") or []):
        if r.get("type") == "total":
            summary = r.get("summary", "0-0")
            out["summary"] = summary
            try:
                parts = summary.split("-")
                if len(parts) >= 1: out["wins"] = int(parts[0])
                if len(parts) >= 2: out["losses"] = int(parts[1])
                if len(parts) >= 3: out["ties"] = int(parts[2])
                total = out["wins"] + out["losses"] + out["ties"]
                if total > 0:
                    out["win_pct"] = (out["wins"] + 0.5 * out["ties"]) / total
            except Exception:
                pass
    return out


def _live_win_prob(p_prior: float, h_score: int, a_score: int,
                    period: int, period_secs_left: int,
                    regulation_seconds: int, n_periods: int,
                    score_logodds_divisor: float = 3.5,
                    score_logodds_multiplier: float = 2.5) -> float:
    """Generic score-aware win prob. Different sports tune the divisor:
       - NBA: 3.5 (3pt = ~85% late)
       - NFL: 7.0 (7pt = ~85% late)
       - Soccer: 1.5 (1 goal = ~85% late)
       - NHL: similar to soccer
       """
    if period <= 0: return p_prior
    if period > n_periods:
        # OT
        diff = h_score - a_score
        if diff == 0: return 0.5
        return 1 / (1 + math.exp(-diff / max(1, score_logodds_divisor / 2)))

    sec_left_total = period_secs_left + (n_periods - period) * (regulation_seconds // n_periods)
    sec_left_total = max(0, sec_left_total)
    frac_left = sec_left_total / regulation_seconds
    diff = h_score - a_score
    prior_logodds = math.log(p_prior / max(1e-6, 1 - p_prior))
    score_logodds = diff / score_logodds_divisor
    blend = prior_logodds * frac_left + score_logodds * (1 - frac_left) * score_logodds_multiplier
    return 1 / (1 + math.exp(-blend))


def _parse_game(comp: Dict[str, Any], status: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    h_team = (home.get("team") or {}).get("displayName", "?")
    a_team = (away.get("team") or {}).get("displayName", "?")
    h_abbr = (home.get("team") or {}).get("abbreviation")
    a_abbr = (away.get("team") or {}).get("abbreviation")
    h_score_raw = home.get("score")
    a_score_raw = away.get("score")
    try:
        h_score = int(h_score_raw) if h_score_raw not in (None, "") else 0
        a_score = int(a_score_raw) if a_score_raw not in (None, "") else 0
    except Exception:
        h_score = a_score = 0

    h_rec = _team_record(home)
    a_rec = _team_record(away)
    h_elo = _winpct_to_elo(h_rec["win_pct"])
    a_elo = _winpct_to_elo(a_rec["win_pct"])
    p_prior = _elo_winprob(h_elo, a_elo, hfa=cfg.get("hfa_elo", 35))

    state = (status.get("type") or {}).get("state")
    period = status.get("period") or 0
    clock = status.get("displayClock")
    period_secs_left = _clock_to_seconds(clock) if state == "in" else 0

    if state == "in" and (h_score or a_score):
        p_home_win = _live_win_prob(
            p_prior, h_score, a_score, period, period_secs_left,
            regulation_seconds=cfg.get("regulation_seconds", 2880),
            n_periods=cfg.get("n_periods", 4),
            score_logodds_divisor=cfg.get("score_logodds_divisor", 3.5),
            score_logodds_multiplier=cfg.get("score_logodds_multiplier", 2.5),
        )
    elif state == "post":
        p_home_win = 1.0 if h_score > a_score else 0.0 if a_score > h_score else 0.5
    else:
        p_home_win = p_prior

    return {
        "id": comp.get("id"),
        "date": comp.get("date"),          # kickoff datetime (lets consumers gate by date)
        "matchup": f"{a_team} @ {h_team}",
        "home_team": h_team, "away_team": a_team,
        "home_abbrev": h_abbr, "away_abbrev": a_abbr,
        "home_record": h_rec["summary"], "away_record": a_rec["summary"],
        "home_score": h_score, "away_score": a_score,
        "status": (status.get("type") or {}).get("description"),
        "state": state,
        "period": period if state != "pre" else None,
        "clock": clock if state != "pre" else None,
        "home_elo": round(h_elo, 1), "away_elo": round(a_elo, 1),
        "p_home_win_pregame": round(p_prior, 4),
        "p_home_win": round(p_home_win, 4),
        "fair_home_american": _american(p_home_win),
        "fair_away_american": _american(1 - p_home_win),
    }


SPORT_LABELS = {1: "preseason", 2: "regular", 3: "playoffs", 4: "offseason"}


def _self_training_shift(sport_key: str) -> float:
    """Load the calibrated bias shift from self_training_<sport>.json.
    Returns the shift to ADD to model P(home win) (i.e. -bias)."""
    path = os.path.join(DATA_DIR, f"self_training_{sport_key}.json")
    if not os.path.exists(path):
        return 0.0
    try:
        with open(path) as f: d = json.load(f)
        reco = d.get("recommendation") or {}
        if reco.get("applied"):
            return float(reco.get("recommended_shift", 0))
    except Exception:
        pass
    return 0.0


def run(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """cfg shape:
       {
         "sport_key": "wnba",  # filename prefix (data/wnba_state.json)
         "espn_path": "basketball/wnba",  # ESPN URL fragment
         "league_label": "WNBA",
         "hfa_elo": 35,
         "regulation_seconds": 2400,  # 4 x 10min = WNBA
         "n_periods": 4,
         "score_logodds_divisor": 3.5,
         "score_logodds_multiplier": 2.5,
       }
    """
    sport_key = cfg["sport_key"]
    out_path = os.path.join(DATA_DIR, f"{sport_key}_state.json")
    # Apply learned calibration shift
    cal_shift = _self_training_shift(sport_key)
    url = f"{BASE_URL}/{cfg['espn_path']}/scoreboard"
    sb = _http(url)
    if not sb:
        out = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "league": cfg.get("league_label", sport_key),
            "active_season": False,
            "error": "ESPN scoreboard unreachable",
            "n_games_today": 0,
            "games": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(out_path, "w") as f: json.dump(out, f, indent=2)
        return out

    events = sb.get("events") or []
    games: List[Dict[str, Any]] = []
    for ev in events:
        comps = ev.get("competitions") or []
        if not comps: continue
        g = _parse_game(comps[0], ev.get("status") or {}, cfg)
        # Apply self-training calibration shift to p_home_win
        if cal_shift != 0 and g.get("state") != "post":
            shifted = max(0.01, min(0.99, g["p_home_win"] + cal_shift))
            g["p_home_win_raw"] = g["p_home_win"]
            g["p_home_win"] = round(shifted, 4)
            g["calibration_shift_pp"] = round(cal_shift * 100, 1)
            g["fair_home_american"] = _american(shifted)
            g["fair_away_american"] = _american(1 - shifted)
        games.append(g)

    season = (sb.get("season") or {}).get("year") or dt.date.today().year
    season_type = (sb.get("season") or {}).get("type")
    season_label = SPORT_LABELS.get(season_type, "season")

    # HONESTY: ESPN's scoreboard serves the NEXT slate when a league is idle --
    # e.g. the NFL endpoint returns Week 1 (September) games in July, which this
    # module used to count and caption as "on the board today". Only games whose
    # start falls on TODAY (US/Eastern, the site's slate convention) -- or that
    # are literally live -- count as today's. games[] still carries the full
    # board (downstream modules price upcoming fixtures from it); the COUNT and
    # the user-facing note must not lie about what "today" is.
    def _et_date(iso) -> str:
        try:
            d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            try:
                from zoneinfo import ZoneInfo
                d = d.astimezone(ZoneInfo("America/New_York"))
            except Exception:
                d = d - dt.timedelta(hours=4)  # EDT fallback
            return d.date().isoformat()
        except Exception:
            return ""

    try:
        from zoneinfo import ZoneInfo
        _today_et = dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        _today_et = (dt.datetime.utcnow() - dt.timedelta(hours=4)).date().isoformat()

    today_games = [g for g in games
                   if g.get("state") == "in" or _et_date(g.get("date")) == _today_et]
    upcoming = [g for g in games if g not in today_games and g.get("state") != "post"]
    next_date = min((_et_date(g.get("date")) for g in upcoming if _et_date(g.get("date"))),
                    default=None)
    if today_games:
        note = f"{len(today_games)} game(s) on the board today ({season_label})."
    elif upcoming:
        note = (f"No games today — next slate {next_date} "
                f"({len(upcoming)} upcoming, {season_label}).")
    else:
        note = f"No games today ({season_label})."

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "league": cfg.get("league_label", sport_key.upper()),
        "active_season": len(today_games) > 0 or season_type in (2, 3),
        "season_year": season,
        "season_status": season_label,
        "n_games_today": len(today_games),
        "n_upcoming": len(upcoming),
        "next_game_date": next_date,
        "calibration_shift_pp": round(cal_shift * 100, 1) if cal_shift else 0,
        "self_training_applied": cal_shift != 0,
        "games": games,
        "enabled": True,
        "note": note,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    # Self-test with WNBA
    cfg = {
        "sport_key": "wnba", "espn_path": "basketball/wnba",
        "league_label": "WNBA", "hfa_elo": 35,
        "regulation_seconds": 2400, "n_periods": 4,
    }
    p = run(cfg)
    print(f"WNBA: {p['n_games_today']} games ({p['season_status']})")
    for g in p["games"][:3]:
        print(f"  {g['matchup']} ({g['away_record']} vs {g['home_record']}) P(home) {g['p_home_win']*100:.1f}% fair {g['fair_home_american']:+d}")
