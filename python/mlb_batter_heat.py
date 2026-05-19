"""
EdgeStat -- MLB batter heat tracker.

For each batter in mlb_batter_logs.json, identifies HOT (L14 AVG well above
career baseline) and COLD streaks. Highlights actionable prop opportunities
on hot batters whose lines may not yet reflect the heat.

Uses MLB Stats API to fetch each batter's SEASON AVG and compares to L14.
Caps at top 50 batters to respect API quota.

Output: data/mlb_batter_heat.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_heat.json")

HOT_THRESHOLD_PP = 0.060   # L14 AVG must be 60+ points above season
COLD_THRESHOLD_PP = -0.060
MIN_L14_AB = 25            # need 25+ at-bats in L14 to qualify


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _fetch_season_avg(team_id, year):
    """Fetch season-to-date AVG for every player on a team."""
    url = (f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
           f"?rosterType=active&hydrate=person(stats(group=[hitting],type=[season],season={year}))")
    d = _http(url)
    if not d: return {}
    out = {}
    for entry in (d.get("roster") or []):
        person = entry.get("person") or {}
        pid = person.get("id")
        name = person.get("fullName")
        if not pid or not name: continue
        for s in (person.get("stats") or []):
            for sp in (s.get("splits") or []):
                stat = sp.get("stat") or {}
                avg = stat.get("avg")
                ab = stat.get("atBats", 0)
                if avg is not None and ab >= 20:
                    try:
                        out[name] = {"season_avg": float(avg), "season_ab": int(ab)}
                    except Exception: pass
                    break
    return out


def run() -> Dict[str, Any]:
    logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    batters = logs.get("batters") or []
    year = dt.date.today().year

    # Group batters by team to batch API calls
    by_team: Dict[int, List[Dict[str, Any]]] = {}
    for b in batters:
        tid = b.get("team_id")
        if tid: by_team.setdefault(tid, []).append(b)

    # Fetch season AVG per team (one API call per team)
    season_by_name: Dict[str, Dict[str, Any]] = {}
    teams_fetched = 0
    for tid in list(by_team.keys())[:30]:    # all 30 MLB teams
        season_data = _fetch_season_avg(tid, year)
        season_by_name.update(season_data)
        teams_fetched += 1

    # Compute deltas
    alerts: List[Dict[str, Any]] = []
    for b in batters:
        name = b.get("name")
        s14 = b.get("stats_last_14") or {}
        l14_ab = s14.get("ab", 0)
        l14_avg = s14.get("avg", 0)
        if l14_ab < MIN_L14_AB: continue

        season_info = season_by_name.get(name)
        if not season_info: continue
        season_avg = season_info["season_avg"]
        season_ab = season_info["season_ab"]
        delta = l14_avg - season_avg
        if delta >= HOT_THRESHOLD_PP:
            kind = "HOT"
        elif delta <= COLD_THRESHOLD_PP:
            kind = "COLD"
        else:
            continue
        alerts.append({
            "name": name,
            "team": b.get("team_abbr"),
            "kind": kind,
            "l14_avg": round(l14_avg, 3),
            "l14_ab": l14_ab,
            "l14_hr": s14.get("hr"),
            "season_avg": round(season_avg, 3),
            "season_ab": season_ab,
            "delta_pp": round(delta * 1000, 1),    # in batting average points (.100 = 100pts)
            "fair_yes_1hit": (b.get("props") or {}).get("1_plus_hit", {}).get("fair_yes"),
            "p_1hit": (b.get("props") or {}).get("1_plus_hit", {}).get("p"),
        })

    hot = sorted([a for a in alerts if a["kind"] == "HOT"], key=lambda a: -a["delta_pp"])
    cold = sorted([a for a in alerts if a["kind"] == "COLD"], key=lambda a: a["delta_pp"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season": year,
        "n_batters_analyzed": len(batters),
        "n_with_season_data": len(season_by_name),
        "n_teams_fetched": teams_fetched,
        "hot_threshold_pts": int(HOT_THRESHOLD_PP * 1000),
        "cold_threshold_pts": int(COLD_THRESHOLD_PP * 1000),
        "min_l14_ab": MIN_L14_AB,
        "n_hot": len(hot),
        "n_cold": len(cold),
        "hot_batters": hot[:30],
        "cold_batters": cold[:30],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB batter heat: {p['n_hot']} HOT, {p['n_cold']} COLD "
          f"(of {p['n_batters_analyzed']} batters, {p['n_with_season_data']} with season data)")
    print(f"\nTop 10 HOT batters (L14 AVG well above season):")
    for a in p["hot_batters"][:10]:
        print(f"  {a['name']:25s} ({a['team']:3s}) L14 .{a['l14_avg']*1000:03.0f} / season .{a['season_avg']*1000:03.0f} = +{a['delta_pp']:.0f}pts {a['l14_ab']}ab")
    print(f"\nTop 10 COLD batters (L14 AVG well below season):")
    for a in p["cold_batters"][:10]:
        print(f"  {a['name']:25s} ({a['team']:3s}) L14 .{a['l14_avg']*1000:03.0f} / season .{a['season_avg']*1000:03.0f} = {a['delta_pp']:.0f}pts {a['l14_ab']}ab")
