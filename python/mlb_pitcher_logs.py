"""
EdgeStat -- MLB starting pitcher game logs from MLB Stats API.

For each MLB team's top 3 starting pitchers, pulls last 14-day game log
(IP, ER, K, BB, H, HR allowed) and projects per-start fair odds for:
  - K Over/Under (lines 4.5, 5.5, 6.5, 7.5)
  - ER Under (lines 2.5, 3.5)
  - Win prop (yes/no based on team ML)

Output: data/mlb_pitcher_logs.json
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
OUT_PATH = os.path.join(DATA_DIR, "mlb_pitcher_logs.json")

TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1&season={year}"
ROSTER_URL = "https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"
GAMELOG_URL = ("https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
                "?stats=gameLog&group=pitching&season={year}&gameType=R")


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    threshold = int(math.floor(line)) + 1
    s = 0.0
    for k in range(threshold):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _parse_ip(ip_str):
    """MLB stores IP as '6.2' meaning 6 and 2/3 innings."""
    try:
        if isinstance(ip_str, (int, float)): return float(ip_str)
        s = str(ip_str)
        if '.' in s:
            full, third = s.split('.')
            return int(full) + int(third) / 3
        return float(s)
    except Exception:
        return 0


def run():
    year = dt.date.today().year
    teams_data = _http(TEAMS_URL.format(year=year))
    if not teams_data:
        return {"error": "MLB teams unreachable", "n_pitchers": 0}
    teams = teams_data.get("teams", [])
    all_pitchers: List[Dict[str, Any]] = []
    for team in teams[:30]:
        tid = team.get("id")
        if not tid: continue
        roster_data = _http(ROSTER_URL.format(team_id=tid))
        if not roster_data: continue
        roster = roster_data.get("roster", [])
        team_pitchers = []
        for player_entry in roster:
            pos_code = ((player_entry.get("position") or {}).get("code") or "")
            if pos_code != "1": continue   # pitchers only
            person = player_entry.get("person") or {}
            pid = person.get("id")
            if not pid: continue
            log = _http(GAMELOG_URL.format(player_id=pid, year=year))
            if not log: continue
            splits = ((log.get("stats") or [{}])[0].get("splits") or [])
            if not splits: continue
            # Filter starts (games where IP >= 4)
            recent = list(reversed(splits))[:8]
            starts = [s for s in recent if _parse_ip((s.get("stat") or {}).get("inningsPitched", "0")) >= 4]
            if len(starts) < 2: continue
            tot_ip = sum(_parse_ip((s.get("stat") or {}).get("inningsPitched", "0")) for s in starts)
            tot_so = sum(int((s.get("stat") or {}).get("strikeOuts", 0)) for s in starts)
            tot_er = sum(int((s.get("stat") or {}).get("earnedRuns", 0)) for s in starts)
            tot_bb = sum(int((s.get("stat") or {}).get("baseOnBalls", 0)) for s in starts)
            tot_h = sum(int((s.get("stat") or {}).get("hits", 0)) for s in starts)
            tot_hr = sum(int((s.get("stat") or {}).get("homeRuns", 0)) for s in starts)
            n = len(starts)
            avg_ip = tot_ip / n
            avg_k = tot_so / n
            avg_er = tot_er / n
            era = (tot_er * 9 / tot_ip) if tot_ip > 0 else 99
            k_per_9 = (tot_so * 9 / tot_ip) if tot_ip > 0 else 0
            entry = {
                "name": person.get("fullName"),
                "team_id": tid,
                "team_abbr": team.get("abbreviation"),
                "team_name": team.get("name"),
                "n_starts_logged": n,
                "stats": {
                    "avg_ip": round(avg_ip, 2),
                    "avg_k": round(avg_k, 2),
                    "avg_er": round(avg_er, 2),
                    "era": round(era, 2),
                    "k_per_9": round(k_per_9, 2),
                    "tot_ip": round(tot_ip, 1),
                    "tot_k": tot_so, "tot_er": tot_er,
                    "tot_bb": tot_bb, "tot_h": tot_h, "tot_hr": tot_hr,
                },
                "props": {
                    "k_over_4_5": {"p": round(_poisson_p_over(avg_k, 4.5), 4)},
                    "k_over_5_5": {"p": round(_poisson_p_over(avg_k, 5.5), 4)},
                    "k_over_6_5": {"p": round(_poisson_p_over(avg_k, 6.5), 4)},
                    "k_over_7_5": {"p": round(_poisson_p_over(avg_k, 7.5), 4)},
                    "er_under_2_5": {"p": round(1 - _poisson_p_over(avg_er, 2.5), 4)},
                    "er_under_3_5": {"p": round(1 - _poisson_p_over(avg_er, 3.5), 4)},
                },
            }
            for k_line in (4.5, 5.5, 6.5, 7.5):
                key = f"k_over_{int(k_line)}_{int((k_line - int(k_line)) * 10)}"
                if key in entry["props"]:
                    entry["props"][key]["fair_over"] = _american(entry["props"][key]["p"])
                    entry["props"][key]["fair_under"] = _american(1 - entry["props"][key]["p"])
            for er_line in (2.5, 3.5):
                key = f"er_under_{int(er_line)}_{int((er_line - int(er_line)) * 10)}"
                if key in entry["props"]:
                    entry["props"][key]["fair_under"] = _american(entry["props"][key]["p"])
            team_pitchers.append(entry)
            time.sleep(0.05)
        # Take top 3 per team by IP volume (= rotation regulars)
        team_pitchers.sort(key=lambda p: -p["stats"]["tot_ip"])
        all_pitchers.extend(team_pitchers[:3])
    all_pitchers.sort(key=lambda p: p["stats"]["era"])
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season": year,
        "n_pitchers": len(all_pitchers),
        "top_5_lowest_era": [{"name": p["name"], "team": p["team_abbr"], "era": p["stats"]["era"]} for p in all_pitchers[:5]],
        "pitchers": all_pitchers,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB pitcher logs: {p.get('n_pitchers',0)} starters")
    for top in p.get("top_5_lowest_era", []):
        print(f"  {top['name']:25} ({top['team']:4}) ERA {top['era']}")
