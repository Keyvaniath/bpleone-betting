"""
EdgeStat -- WNBA player heat tracker.

Mirrors nba_player_heat but tuned to WNBA scoring environment
(lower PPG averages -> smaller HOT/COLD thresholds).

Output: data/wnba_player_heat.json
"""
from __future__ import annotations

import os
import json
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "wnba_player_heat.json")

GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/basketball/wnba/athletes/{aid}/gamelog"
# WNBA: avg starter PPG ~12-18 (vs NBA ~15-25). Tighter thresholds.
PTS_DELTA_HOT = 4.0
PTS_DELTA_COLD = -4.0
REB_DELTA = 1.5
AST_DELTA = 1.5
MIN_GAMES_L5 = 3
MAX_PLAYERS = 100


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


def _gamelog_stats(athlete_id):
    """Returns (l5_stats, season_stats) tuple where each is (n, pts, reb, ast, mins).

    WNBA ESPN gamelog stat order DIFFERS from NBA:
      WNBA: MIN(0) PTS(1) REB(2) AST(3) STL(4) BLK(5) TO(6) FG(7) ...
      NBA:  MIN(0) FG(1) FG%(2) 3PT(3) ... REB(7) AST(8) ... PTS(13)
    """
    data = _http(GAMELOG_URL.format(aid=athlete_id))
    if not data: return None, None
    all_events = []
    for st in (data.get("seasonTypes") or []):
        for cat in (st.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats") or []
                if isinstance(stats, list) and len(stats) >= 7:
                    all_events.append(stats)
        if all_events: break
    if len(all_events) < MIN_GAMES_L5: return None, None

    def _safe_float(s):
        try: return float(s or 0)
        except Exception: return 0.0

    def _agg(events):
        pts = reb = ast = mins = 0.0
        n = 0
        for s in events:
            try:
                mins += _safe_float(s[0])
                pts += _safe_float(s[1])     # WNBA: PTS=1
                reb += _safe_float(s[2])     # WNBA: REB=2
                ast += _safe_float(s[3])     # WNBA: AST=3
                n += 1
            except Exception: continue
        if n == 0: return None
        return n, pts / n, reb / n, ast / n, mins / n

    return _agg(all_events[:5]), _agg(all_events)


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_wnba.json"))
    players = stats.get("players") or []
    # NOTE: player_stats_wnba pts_per_game is broken (see ESPN column-mapping bug
    # in espn_player_stats.py for WNBA). We compute SEASON AVG ourselves from
    # the gamelog instead of trusting it. Filter only on min_per_game >= 15
    # (real starters) since that field is reliable.
    players_sorted = sorted(players, key=lambda p: -(p.get("min_per_game") or 0))
    target = [p for p in players_sorted if (p.get("min_per_game") or 0) >= 15][:MAX_PLAYERS]

    alerts = []
    n_fetched = 0
    for p in target:
        aid = p.get("athlete_id")
        if not aid: continue
        l5, season = _gamelog_stats(aid)
        n_fetched += 1
        if not l5 or not season: continue
        _, ssn_pts, ssn_reb, ssn_ast, _ = season
        if ssn_pts < 6: continue
        n_g, l5_pts, l5_reb, l5_ast, l5_min = l5
        d_pts = l5_pts - ssn_pts
        d_reb = l5_reb - ssn_reb
        d_ast = l5_ast - ssn_ast
        signals = []
        kind = None
        if d_pts >= PTS_DELTA_HOT: signals.append(f"PTS +{d_pts:.1f}"); kind = "HOT"
        elif d_pts <= PTS_DELTA_COLD: signals.append(f"PTS {d_pts:.1f}"); kind = "COLD"
        if d_reb >= REB_DELTA: signals.append(f"REB +{d_reb:.1f}"); kind = kind or "HOT"
        elif d_reb <= -REB_DELTA: signals.append(f"REB {d_reb:.1f}"); kind = kind or "COLD"
        if d_ast >= AST_DELTA: signals.append(f"AST +{d_ast:.1f}"); kind = kind or "HOT"
        elif d_ast <= -AST_DELTA: signals.append(f"AST {d_ast:.1f}"); kind = kind or "COLD"
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
        time.sleep(0.04)

    hot = sorted([a for a in alerts if a["kind"] == "HOT"], key=lambda a: -a["delta_pts"])
    cold = sorted([a for a in alerts if a["kind"] == "COLD"], key=lambda a: a["delta_pts"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_players_checked": n_fetched,
        "n_hot": len(hot),
        "n_cold": len(cold),
        "hot_players": hot[:20],
        "cold_players": cold[:20],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"WNBA player heat: {p['n_hot']} HOT, {p['n_cold']} COLD (checked {p['n_players_checked']})")
    for a in p["hot_players"][:8]:
        print(f"  HOT  {a['name']:25s} ({a['team_abbr']:3s}) L5 {a['l5_pts']:.1f}/{a['l5_reb']:.1f}/{a['l5_ast']:.1f} vs season {a['season_pts']:.1f}/{a['season_reb']:.1f}/{a['season_ast']:.1f} [{', '.join(a['signals'])}]")
    for a in p["cold_players"][:8]:
        print(f"  COLD {a['name']:25s} ({a['team_abbr']:3s}) L5 {a['l5_pts']:.1f}/{a['l5_reb']:.1f}/{a['l5_ast']:.1f} vs season {a['season_pts']:.1f}/{a['season_reb']:.1f}/{a['season_ast']:.1f} [{', '.join(a['signals'])}]")
