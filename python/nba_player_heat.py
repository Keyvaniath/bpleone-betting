"""
EdgeStat -- NBA player heat tracker.

Per-player L5 PPG/RPG/APG vs SEASON-to-date deltas. Flags players who:
  - 🔥 HOT: L5 PPG >= season + 5 (or RPG/APG >= +2)
  - ❄️ COLD: L5 PPG <= season - 5 (or RPG/APG <= -2)

Uses player_stats_nba.json for season averages + ESPN per-athlete gamelog
for L5. Cross-checks team_form for game-level context.

Output: data/nba_player_heat.json
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_heat.json")

GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{aid}/gamelog"
PTS_DELTA_HOT = 5.0
PTS_DELTA_COLD = -5.0
REB_DELTA_HOT = 2.0
AST_DELTA_HOT = 2.0
MIN_GAMES_L5 = 3   # need 3+ games in last 5
MAX_PLAYERS = 200  # cap API calls


def _http(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _last5_avg(athlete_id):
    """Pull last 5 games via ESPN. Returns (n, pts, reb, ast, min).

    ESPN gamelog schema: response.seasonTypes[].categories[].events[].stats[].
    Stats array order (basketball):
      0=MIN 1=FG 2=FG% 3=3PT 4=3P% 5=FT 6=FT% 7=REB 8=AST 9=BLK 10=STL 11=TO 12=PF 13=PTS
    """
    data = _http(GAMELOG_URL.format(aid=athlete_id))
    if not data: return None
    # Gather all event stat arrays from the latest season type / categories
    season_types = data.get("seasonTypes") or []
    # Most recent season first
    all_events = []
    for st in season_types:
        for cat in (st.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats") or []
                if isinstance(stats, list) and len(stats) >= 14:
                    all_events.append({"eventId": ev.get("eventId"), "stats": stats})
        if all_events: break   # take first non-empty season type (regular > playoff)
    if not all_events:
        return None
    # Take last 5 (already newest-first in ESPN response per category)
    last5 = all_events[:5]
    pts = reb = ast = mins = 0.0
    n = 0
    for ev in last5:
        s = ev["stats"]
        try:
            mins += float(s[0] or 0)
            reb += float(s[7] or 0)
            ast += float(s[8] or 0)
            pts += float(s[13] or 0)
            n += 1
        except Exception:
            continue
    if n < MIN_GAMES_L5:
        return None
    return n, pts / n, reb / n, ast / n, mins / n


def _active_teams_today() -> set:
    """Teams with games scheduled today (pre or live). Critical during NBA
    playoffs when only 2-4 teams play each night."""
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    active = set()
    for g in (state.get("games") or []):
        if g.get("state") == "post": continue
        for fld in ("home_team", "away_team"):
            v = g.get(fld)
            if v: active.add(v)
    return active


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_nba.json"))
    players = stats.get("players") or []
    active_teams = _active_teams_today()

    # Filter to players on active teams (skip if no NBA state available)
    if active_teams:
        players = [p for p in players if p.get("team") in active_teams]

    # Sort by minutes-per-game desc so we hit the most relevant players first
    players_sorted = sorted(players, key=lambda p: -(p.get("min_per_game") or 0))
    target = players_sorted[:MAX_PLAYERS]

    alerts = []
    n_fetched = 0
    for p in target:
        aid = p.get("athlete_id")
        if not aid: continue
        ssn_pts = p.get("pts_per_game") or 0
        ssn_reb = p.get("reb_per_game") or 0
        ssn_ast = p.get("ast_per_game") or 0
        if ssn_pts < 8: continue  # skip bench warmers
        l5 = _last5_avg(aid)
        n_fetched += 1
        if not l5: continue
        n_g, l5_pts, l5_reb, l5_ast, l5_min = l5
        d_pts = l5_pts - ssn_pts
        d_reb = l5_reb - ssn_reb
        d_ast = l5_ast - ssn_ast
        # Combined hot/cold score (weighted by impact)
        signals = []
        kind = None
        if d_pts >= PTS_DELTA_HOT: signals.append(f"PTS +{d_pts:.1f}"); kind = "HOT"
        elif d_pts <= PTS_DELTA_COLD: signals.append(f"PTS {d_pts:.1f}"); kind = "COLD"
        if d_reb >= REB_DELTA_HOT: signals.append(f"REB +{d_reb:.1f}"); kind = kind or "HOT"
        elif d_reb <= -REB_DELTA_HOT: signals.append(f"REB {d_reb:.1f}"); kind = kind or "COLD"
        if d_ast >= AST_DELTA_HOT: signals.append(f"AST +{d_ast:.1f}"); kind = kind or "HOT"
        elif d_ast <= -AST_DELTA_HOT: signals.append(f"AST {d_ast:.1f}"); kind = kind or "COLD"
        if not kind: continue
        alerts.append({
            "name": p.get("name"),
            "team_abbr": p.get("team_abbr"),
            "team": p.get("team"),
            "position": p.get("position"),
            "kind": kind,
            "season_pts": round(ssn_pts, 1),
            "season_reb": round(ssn_reb, 1),
            "season_ast": round(ssn_ast, 1),
            "l5_pts": round(l5_pts, 1),
            "l5_reb": round(l5_reb, 1),
            "l5_ast": round(l5_ast, 1),
            "l5_min": round(l5_min, 1),
            "n_games_l5": n_g,
            "delta_pts": round(d_pts, 1),
            "delta_reb": round(d_reb, 1),
            "delta_ast": round(d_ast, 1),
            "signals": signals,
        })
        time.sleep(0.04)   # be polite to ESPN

    hot = sorted([a for a in alerts if a["kind"] == "HOT"], key=lambda a: -a["delta_pts"])
    cold = sorted([a for a in alerts if a["kind"] == "COLD"], key=lambda a: a["delta_pts"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_teams_today": sorted(list(active_teams)),
        "n_active_teams": len(active_teams),
        "n_players_checked": n_fetched,
        "n_hot": len(hot),
        "n_cold": len(cold),
        "hot_players": hot[:30],
        "cold_players": cold[:30],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NBA player heat: {p['n_hot']} HOT, {p['n_cold']} COLD (checked {p['n_players_checked']} players)")
    print("Top 10 HOT:")
    for a in p["hot_players"][:10]:
        print(f"  {a['name']:25s} ({a['team_abbr']:3s}) L5 {a['l5_pts']:.1f}/{a['l5_reb']:.1f}/{a['l5_ast']:.1f} vs season {a['season_pts']:.1f}/{a['season_reb']:.1f}/{a['season_ast']:.1f} [{', '.join(a['signals'])}]")
    print("Top 10 COLD:")
    for a in p["cold_players"][:10]:
        print(f"  {a['name']:25s} ({a['team_abbr']:3s}) L5 {a['l5_pts']:.1f}/{a['l5_reb']:.1f}/{a['l5_ast']:.1f} vs season {a['season_pts']:.1f}/{a['season_reb']:.1f}/{a['season_ast']:.1f} [{', '.join(a['signals'])}]")
