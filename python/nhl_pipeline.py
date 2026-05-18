"""
EdgeStat -- NHL scoreboard pipeline (live, free ESPN API).

Mid-May = NHL playoffs / Stanley Cup. Same shape as nba_pipeline but with
hockey-specific HFA (smaller than NBA -- about +0.3 goals).

Output: data/nhl_state.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "nhl_state.json")

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"

# NHL home-ice advantage is smaller than NBA -- roughly +0.15 win-prob bump.
# Use a +20 ELO bump.
HFA_ELO = 20


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _winpct_to_elo(wp: float, base: float = 1500) -> float:
    if wp <= 0.01:
        return base - 250
    if wp >= 0.99:
        return base + 250
    return base + 400 * math.log10(wp / (1 - wp))


def _elo_winprob(home_elo: float, away_elo: float) -> float:
    diff = (home_elo + HFA_ELO) - away_elo
    return 1 / (1 + 10 ** (-diff / 400))


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _team_record(team_block: Dict[str, Any]) -> Dict[str, Any]:
    out = {"wins": 0, "losses": 0, "otl": 0, "win_pct": 0.5}
    for r in (team_block.get("records") or []):
        if r.get("type") == "total":
            summary = r.get("summary", "0-0-0")
            try:
                parts = summary.split("-")
                if len(parts) >= 2:
                    out["wins"] = int(parts[0])
                    out["losses"] = int(parts[1])
                if len(parts) >= 3:
                    out["otl"] = int(parts[2])
                tot = out["wins"] + out["losses"] + out["otl"]
                # Hockey uses W + 0.5*OTL / GP
                out["win_pct"] = (out["wins"] + 0.5 * out["otl"]) / tot if tot else 0.5
            except Exception:
                pass
    return out


def _clock_to_seconds(clock_str: Optional[str]) -> int:
    if not clock_str or ":" not in clock_str:
        return 0
    try:
        parts = clock_str.split(":")
        return int(int(parts[0]) * 60 + float(parts[1]))
    except Exception:
        return 0


def _live_win_prob(p_prior: float, h_score: int, a_score: int,
                    period: int, period_secs_left: int) -> float:
    """NHL regulation = 3 periods x 20 min = 3600 sec. Score lead more
    dominant because hockey has fewer goals than basketball has points."""
    if period <= 0:
        return p_prior
    if period > 3:    # OT or shootout
        diff = h_score - a_score
        if diff == 0:
            return 0.5    # OT in hockey -- coin flip
        return 1 / (1 + math.exp(-diff * 0.8))

    sec_left_total = period_secs_left + (3 - period) * 20 * 60
    sec_left_total = max(0, sec_left_total)
    frac_left = sec_left_total / 3600.0

    diff = h_score - a_score
    prior_logodds = math.log(p_prior / max(1e-6, 1 - p_prior))
    # Hockey score: 1-goal lead = ~70% with 1 period left
    score_logodds = diff * 0.6
    blend = prior_logodds * frac_left + score_logodds * (1 - frac_left) * 1.8
    return 1 / (1 + math.exp(-blend))


def _parse_game(comp: Dict[str, Any], status: Dict[str, Any]) -> Dict[str, Any]:
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    h_team = (home.get("team") or {}).get("displayName", "?")
    a_team = (away.get("team") or {}).get("displayName", "?")
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
    p_prior = _elo_winprob(h_elo, a_elo)

    state = (status.get("type") or {}).get("state")
    period = (status.get("period") or 0)
    clock = status.get("displayClock")
    period_secs_left = _clock_to_seconds(clock) if state == "in" else 0

    if state == "in" and (h_score or a_score):
        p_home_win = _live_win_prob(p_prior, h_score, a_score, period, period_secs_left)
    elif state == "post":
        p_home_win = 1.0 if h_score > a_score else 0.0 if a_score > h_score else 0.5
    else:
        p_home_win = p_prior

    return {
        "id": comp.get("id"),
        "matchup": f"{a_team} @ {h_team}",
        "home_team": h_team,
        "away_team": a_team,
        "home_record": f"{h_rec['wins']}-{h_rec['losses']}-{h_rec['otl']}",
        "away_record": f"{a_rec['wins']}-{a_rec['losses']}-{a_rec['otl']}",
        "home_score": h_score,
        "away_score": a_score,
        "status": (status.get("type") or {}).get("description"),
        "state": state,
        "period": period if state != "pre" else None,
        "clock": clock if state != "pre" else None,
        "home_elo": round(h_elo, 1),
        "away_elo": round(a_elo, 1),
        "p_home_win_pregame": round(p_prior, 4),
        "p_home_win": round(p_home_win, 4),
        "fair_home_american": _american(p_home_win),
        "fair_away_american": _american(1 - p_home_win),
    }


def _self_training_shift(sport_key: str) -> float:
    """Load the calibrated bias shift from self_training_<sport>.json."""
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


def run() -> Dict[str, Any]:
    sb = _http(ESPN_SCOREBOARD)
    cal_shift = _self_training_shift("nhl")
    if not sb:
        out = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "active_season": False,
            "error": "ESPN NHL scoreboard unreachable",
            "n_games_today": 0,
            "games": [],
        }
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=2)
        return out

    events = sb.get("events") or []
    games: List[Dict[str, Any]] = []
    for ev in events:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        g = _parse_game(comps[0], ev.get("status") or {})
        if cal_shift != 0 and g.get("state") != "post":
            raw = g.get("p_home_win")
            if raw is not None:
                shifted = max(0.01, min(0.99, raw + cal_shift))
                g["p_home_win_raw"] = raw
                g["p_home_win"] = round(shifted, 4)
                g["calibration_shift_pp"] = round(cal_shift * 100, 1)
                g["fair_home_american"] = _american(shifted)
                g["fair_away_american"] = _american(1 - shifted)
        games.append(g)

    season = (sb.get("season") or {}).get("year") or dt.date.today().year
    season_type = (sb.get("season") or {}).get("type")
    season_label = {1: "preseason", 2: "regular", 3: "playoffs", 4: "offseason"}.get(
        season_type, "unknown"
    )

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_season": len(events) > 0 or season_type in (2, 3),
        "season_year": season,
        "season_status": season_label,
        "n_games_today": len(games),
        "calibration_shift_pp": round(cal_shift * 100, 1) if cal_shift else 0,
        "self_training_applied": cal_shift != 0,
        "games": games,
        "enabled": True,
        "note": f"{len(games)} NHL game(s) on the board today ({season_label}).",
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p.get('n_games_today',0)} games ({p.get('season_status','?')})")
    for g in p.get("games", []):
        print(f"  {g['matchup']} ({g['away_record']} vs {g['home_record']}) "
              f"P(home) = {g['p_home_win']*100:.1f}%  fair {g['fair_home_american']:+d}/{g['fair_away_american']:+d}  "
              f"-- {g.get('status')}")
