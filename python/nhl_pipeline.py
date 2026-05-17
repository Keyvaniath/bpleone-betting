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
        "home_record": f"{h_rec['wins']}-{h_rec['losses']}-{h_rec['otl']}",
        "away_record": f"{a_rec['wins']}-{a_rec['losses']}-{a_rec['otl']}",
        "home_score": h_score,
        "away_score": a_score,
        "status": (status.get("type") or {}).get("description"),
        "state": state,
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
        games.append(_parse_game(comps[0], ev.get("status") or {}))

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
