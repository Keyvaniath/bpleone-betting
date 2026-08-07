"""
EdgeStat -- NHL extended player props (playoff-filtered).

For each player on a team playing tonight, project sport-specific props
using ESPN gamelog data (which has correct stat ordering):
  Goals (anytime goalscorer): P(G >= 1)
  Goals over 0.5 / 1.5
  Assists over 0.5 / 1.5 / 2.5
  Points (G+A) over 0.5 / 1.5 / 2.5
  Shots on Goal over 2.5 / 3.5 / 4.5 / 5.5

NHL gamelog stat indices:
  0=G, 1=A, 2=PTS, 3=+/-, 4=PIM, 5=S, 6=S%, 7=PPG, 8=PPA, 9=SHG,
  10=SHA, 11=GWG, 12=TOI/G, 13=PROD

CRITICAL: playoff filter (only project for teams playing tonight).

Output: data/nhl_extended_props.json
"""
from __future__ import annotations

import os
import json
import math
import time
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_extended_props.json")
GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{aid}/gamelog"
MAX_PLAYERS = 100   # cap per cycle


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _http(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _active_teams_today() -> set:
    state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    active = set()
    for g in (state.get("games") or []):
        if g.get("state") == "post": continue
        for fld in ("home_team", "away_team"):
            v = g.get(fld)
            if v: active.add(v)
    return active


def _gamelog_rates(aid):
    """Returns (n_games, g_rate, a_rate, sog_rate) from full NHL gamelog.
    NHL stat indices: G=0 A=1 PTS=2 ... S=5"""
    data = _http(GAMELOG_URL.format(aid=aid))
    if not data: return None
    events = []
    for st in (data.get("seasonTypes") or []):
        for cat in (st.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats") or []
                if isinstance(stats, list) and len(stats) >= 6:
                    events.append(stats)
        if events: break   # latest season type only
    if len(events) < 3: return None
    g_total = a_total = s_total = 0.0
    n = 0
    for s in events:
        try:
            g_total += float(s[0] or 0)
            a_total += float(s[1] or 0)
            s_total += float(s[5] or 0)
            n += 1
        except Exception: continue
    if n == 0: return None
    return n, g_total / n, a_total / n, s_total / n


def run() -> Dict[str, Any]:
    stats = _load(os.path.join(DATA_DIR, "player_stats_nhl.json"))
    players = stats.get("players") or []
    active_teams = _active_teams_today()
    if active_teams:
        players = [p for p in players if p.get("team") in active_teams]

    # Sort by points-per-game so we hit top scorers first
    players_sorted = sorted(players, key=lambda p: -(p.get("points_per_game") or 0))
    target = players_sorted[:MAX_PLAYERS]

    players_out = []
    n_fetched = 0
    for p in target:
        aid = p.get("athlete_id")
        if not aid: continue
        rates = _gamelog_rates(aid)
        n_fetched += 1
        if not rates: continue
        n_g, g_rate, a_rate, sog_rate = rates
        pts_rate = g_rate + a_rate

        props: Dict[str, Any] = {}
        # Goals over 0.5 / 1.5
        for line in (0.5, 1.5):
            prob = _poisson_p_over(g_rate, line)
            if 0.03 < prob < 0.97:
                props[f"goals_over_{line}"] = {"line": line, "p": round(prob, 4),
                                                  "fair_over": _american(prob),
                                                  "fair_under": _american(1 - prob)}
        # Anytime goalscorer (= goals over 0.5)
        ag = _poisson_p_over(g_rate, 0.5)
        if 0.03 < ag < 0.97:
            props["anytime_goal"] = {"p": round(ag, 4),
                                       "fair_yes": _american(ag),
                                       "fair_no": _american(1 - ag)}
        # Assists over 0.5 / 1.5 / 2.5
        for line in (0.5, 1.5, 2.5):
            prob = _poisson_p_over(a_rate, line)
            if 0.03 < prob < 0.97:
                props[f"assists_over_{line}"] = {"line": line, "p": round(prob, 4),
                                                    "fair_over": _american(prob),
                                                    "fair_under": _american(1 - prob)}
        # Points (G+A) over
        for line in (0.5, 1.5, 2.5):
            prob = _poisson_p_over(pts_rate, line)
            if 0.03 < prob < 0.97:
                props[f"points_over_{line}"] = {"line": line, "p": round(prob, 4),
                                                   "fair_over": _american(prob),
                                                   "fair_under": _american(1 - prob)}
        # SOG over 2.5 / 3.5 / 4.5 / 5.5
        for line in (2.5, 3.5, 4.5, 5.5):
            prob = _poisson_p_over(sog_rate, line)
            if 0.03 < prob < 0.97:
                props[f"sog_over_{line}"] = {"line": line, "p": round(prob, 4),
                                                "fair_over": _american(prob),
                                                "fair_under": _american(1 - prob)}
        if not props: continue
        players_out.append({
            "name": p.get("name"),
            "team": p.get("team_abbr"),
            "position": p.get("position"),
            "n_games": n_g,
            "rates": {"g": round(g_rate, 3),
                       "a": round(a_rate, 3),
                       "pts": round(pts_rate, 3),
                       "sog": round(sog_rate, 3)},
            "props": props,
        })
        time.sleep(0.04)

    # Sweet spot
    sweet = []
    for pp in players_out:
        for mkt, info in (pp.get("props") or {}).items():
            prob = info.get("p")
            if not prob or not (0.6 <= prob <= 0.9): continue
            sweet.append({
                "name": pp["name"], "team": pp["team"],
                "market": mkt, "prob": prob,
                "fair": info.get("fair_yes") or info.get("fair_over"),
            })
    sweet.sort(key=lambda x: -x["prob"])

    # Top anytime-goal
    atg = sorted(
        [pp for pp in players_out if pp["props"].get("anytime_goal")],
        key=lambda pp: -pp["props"]["anytime_goal"]["p"]
    )[:20]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "active_teams_today": sorted(list(active_teams)),
        "n_players_checked": n_fetched,
        "n_players_with_props": len(players_out),
        "n_total_props": sum(len(p["props"]) for p in players_out),
        "n_sweet_spot": len(sweet),
        "top_anytime_goal": atg,
        "top_picks": sweet[:30],
        "players": players_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NHL extended props: {p['n_players_with_props']} players, {p['n_total_props']} props, "
          f"{p['n_sweet_spot']} sweet-spot picks (active: {p['active_teams_today']})")
    print("Top 10 anytime-goalscorer:")
    for pp in p["top_anytime_goal"][:10]:
        atg = pp["props"]["anytime_goal"]
        print(f"  {pp['name']:25s} ({pp['team']:3s}) G={pp['rates']['g']:.2f}/gm "
              f"ATG p={atg['p']*100:.0f}% fair {atg['fair_yes']}")
    print("Top 10 sweet-spot picks:")
    for s in p["top_picks"][:10]:
        print(f"  {s['name']:25s} ({s['team']:3s}) {s['market']:25s} p={s['prob']*100:.0f}% fair={s['fair']}")
