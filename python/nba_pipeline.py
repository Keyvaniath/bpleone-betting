"""
EdgeStat -- NBA scoreboard pipeline (live, free ESPN API).

Pulls today's NBA games + per-team season records from ESPN's public endpoints.
Mid-May = NBA playoffs (Conference Finals → Finals). The same pipeline is
useful in-season for daily scoreboard tracking.

For each game, computes:
  - Live or scheduled status
  - Team records + last-10 form
  - Naive win-probability projection from ELO derived from win-pct
    (no per-player injury/usage modeling yet -- v2 will add via injuries feed)

Output: data/nba_state.json
  {
    "active_season": true,
    "n_games_today": ...,
    "games": [...],
    "next_game_at": ISO
  }

This replaces the stub nba_stub.py (which still writes for back-compat).
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "nba_state.json")

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ESPN_TEAMS = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

# Home court advantage in NBA: roughly +3 points / about +60% win probability
# at neutral talent. We'll use a +0.5 ELO bump (≈3% win-prob bump).
HFA_ELO = 35


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _winpct_to_elo(wp: float, base: float = 1500) -> float:
    """Convert season win-pct to a synthetic ELO rating. A .700 team is ~+200
    ELO above league average."""
    if wp <= 0.01:
        return base - 250
    if wp >= 0.99:
        return base + 250
    # Logit-based: ELO = base + 400 * log10(wp / (1-wp))
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
    """Extract W/L + win-pct from competitor.records[]."""
    out = {"wins": 0, "losses": 0, "win_pct": 0.5}
    for r in (team_block.get("records") or []):
        if r.get("type") == "total":
            summary = r.get("summary", "0-0")
            try:
                w, l = summary.split("-")
                out["wins"] = int(w)
                out["losses"] = int(l)
                tot = out["wins"] + out["losses"]
                out["win_pct"] = out["wins"] / tot if tot else 0.5
            except Exception:
                pass
    return out


def _parse_game(comp: Dict[str, Any], status: Dict[str, Any]) -> Dict[str, Any]:
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0] if competitors else {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1] if len(competitors) > 1 else {})

    h_team = (home.get("team") or {}).get("displayName", "?")
    a_team = (away.get("team") or {}).get("displayName", "?")
    h_score = home.get("score")
    a_score = away.get("score")

    h_rec = _team_record(home)
    a_rec = _team_record(away)

    h_elo = _winpct_to_elo(h_rec["win_pct"])
    a_elo = _winpct_to_elo(a_rec["win_pct"])
    p_home_win = _elo_winprob(h_elo, a_elo)

    state = (status.get("type") or {}).get("state")
    return {
        "id": comp.get("id"),
        "matchup": f"{a_team} @ {h_team}",
        "home_team": h_team,
        "away_team": a_team,
        "home_record": f"{h_rec['wins']}-{h_rec['losses']}",
        "away_record": f"{a_rec['wins']}-{a_rec['losses']}",
        "home_score": h_score,
        "away_score": a_score,
        "status": (status.get("type") or {}).get("description"),
        "state": state,    # "pre" | "in" | "post"
        "period": (status.get("period") or 0) if state != "pre" else None,
        "clock": status.get("displayClock") if state != "pre" else None,
        "home_elo": round(h_elo, 1),
        "away_elo": round(a_elo, 1),
        "p_home_win": round(p_home_win, 4),
        "fair_home_american": _american(p_home_win),
        "fair_away_american": _american(1 - p_home_win),
    }


def run() -> Dict[str, Any]:
    sb = _http(ESPN_SCOREBOARD)
    if not sb:
        out = {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "active_season": False,
            "error": "ESPN NBA scoreboard unreachable",
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
        games.append(_parse_game(comps[0], ev.get("status") or {}))

    # Aggregate season metadata from first event (if any)
    season = (sb.get("season") or {}).get("year") or dt.date.today().year
    season_type = (sb.get("season") or {}).get("type")    # 1=pre, 2=reg, 3=post
    season_label = {1: "preseason", 2: "regular", 3: "playoffs", 4: "offseason"}.get(
        season_type, "unknown"
    )

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_season": len(events) > 0 or season_type in (2, 3),
        "season_year": season,
        "season_status": season_label,
        "n_games_today": len(games),
        "games": games,
        # Back-compat with old stub:
        "enabled": True,
        "note": f"{len(games)} game(s) on the board today ({season_label}).",
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
