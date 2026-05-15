"""
EdgeStat -- bullpen workload tracker.

For each team, sums total relief innings across the last 2 days of completed
games. Teams with > 5 IP from the bullpen in 2 days are flagged as "gassed":
their high-leverage relievers are likely unavailable, which means a tighter
late-inning game tonight projects to higher total runs.

This is a known +EV signal for live betting and totals.

Writes data/bullpen_workload.json.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bullpen_workload.json")
WINDOW_DAYS = 2
GASSED_THRESHOLD_IP = 8.0


def fetch_team_bullpen_load(team_id: int) -> Dict[str, Any]:
    """Return bullpen IP load + per-pitcher breakdown for the last WINDOW_DAYS."""
    if requests is None:
        return {}
    today = dt.date.today()
    start = (today - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    end = today.isoformat()
    try:
        r = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "teamId": team_id,
                    "startDate": start, "endDate": end},
            timeout=10,
        )
        if not r.ok:
            return {}
        sched = r.json().get("dates", [])
    except Exception:
        return {}
    total_relief_ip = 0.0
    relievers: Dict[str, Dict[str, Any]] = {}
    games_inspected = 0
    for d in sched:
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") != "Final":
                continue
            try:
                bs = requests.get(
                    f"https://statsapi.mlb.com/api/v1/game/{g['gamePk']}/boxscore",
                    timeout=10,
                ).json()
            except Exception:
                continue
            games_inspected += 1
            for side in ("home", "away"):
                tt = bs.get("teams", {}).get(side, {})
                if tt.get("team", {}).get("id") != team_id:
                    continue
                pitchers_in_order = tt.get("pitchers", []) or []
                for idx, pid in enumerate(pitchers_in_order):
                    p = tt.get("players", {}).get(f"ID{pid}", {})
                    stats = p.get("stats", {}).get("pitching", {})
                    ip = stats.get("inningsPitched")
                    if not ip:
                        continue
                    # The first pitcher in pitchers[] is the starter.
                    if idx == 0:
                        continue
                    try:
                        ip_f = float(ip)
                    except (TypeError, ValueError):
                        continue
                    total_relief_ip += ip_f
                    name = p.get("person", {}).get("fullName", "?")
                    rec = relievers.setdefault(name, {"appearances": 0, "ip": 0.0, "pitches": 0})
                    rec["appearances"] += 1
                    rec["ip"] += ip_f
                    pc = stats.get("numberOfPitches")
                    if pc:
                        try:
                            rec["pitches"] += int(pc)
                        except (TypeError, ValueError):
                            pass
    relievers_sorted = [{"name": n, **info} for n, info in
                         sorted(relievers.items(), key=lambda kv: -kv[1]["ip"])]
    # Closer availability heuristic: the top-usage reliever (or top-2) is
    # likely the closer / setup man. If they pitched in the last 2 days at
    # full effort (>= 1 IP or >= 20 pitches), they may be down today.
    top_2 = relievers_sorted[:2]
    closer_warning = []
    for r in top_2:
        # Real high-leverage usage: 2 outings with >= 2 IP combined, OR
        # 1 outing with >= 25 pitches (closer's typical full workload).
        if r.get("appearances", 0) >= 2 and r.get("ip", 0) >= 2.0:
            closer_warning.append(r["name"])
        elif r.get("pitches", 0) >= 25 and r.get("appearances", 0) == 1:
            closer_warning.append(r["name"])
    return {
        "games_inspected": games_inspected,
        "total_relief_ip": round(total_relief_ip, 1),
        "gassed": total_relief_ip >= GASSED_THRESHOLD_IP,
        "high_leverage_unavailable": closer_warning,
        "relievers": relievers_sorted[:8],
    }


def build_all() -> Dict[str, Any]:
    teams = sr._teams()
    out: Dict[str, Any] = {}
    for name, info in teams.items():
        load = fetch_team_bullpen_load(info["id"])
        if load:
            out[name] = {"team_id": info["id"], "abbr": info.get("abbr"), **load}
    gassed = [n for n, t in out.items() if t.get("gassed")]
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "window_days": WINDOW_DAYS,
        "gassed_threshold_ip": GASSED_THRESHOLD_IP,
        "teams_with_data": len(out),
        "gassed_teams": gassed,
        "teams": out,
    }


def write_bullpen(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote bullpen_workload -> {path}")
    print(f"  Teams with data: {payload.get('teams_with_data', 0)}")
    gassed = payload.get("gassed_teams") or []
    print(f"  Gassed bullpens ({len(gassed)}):")
    for name in gassed[:8]:
        t = payload["teams"][name]
        print(f"    {name:25} {t['total_relief_ip']} IP across {t['games_inspected']} games "
              f"(top reliever: {t['relievers'][0]['name'] if t['relievers'] else '?'})")


if __name__ == "__main__":
    write_bullpen(build_all())
