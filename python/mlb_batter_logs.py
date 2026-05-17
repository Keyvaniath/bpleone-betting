"""
EdgeStat -- MLB batter per-game logs from MLB Stats API.

For each of the top ~150 MLB batters (active starters across 30 teams),
pulls last 14-day game log: AB, H, HR, RBI, R, BB, K, AVG.
Aggregates to per-game averages and produces fair-odds projections for:
  - 1+ Hit
  - 2+ Hits
  - 1+ HR
  - 1+ RBI
  - 1+ Run scored

Output: data/mlb_batter_logs.json
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
OUT_PATH = os.path.join(DATA_DIR, "mlb_batter_logs.json")

# MLB Stats API (free)
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1&season={year}"
ROSTER_URL = "https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=active"
GAMELOG_URL = ("https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
                "?stats=gameLog&group=hitting&season={year}&gameType=R")


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _binom_one_plus(p: float, n: int) -> float:
    return 1 - (1 - p) ** n


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    year = dt.date.today().year
    teams_data = _http(TEAMS_URL.format(year=year))
    if not teams_data:
        return {"error": "MLB teams unreachable", "n_batters": 0}

    teams = teams_data.get("teams", [])
    all_batters: List[Dict[str, Any]] = []

    for team in teams[:30]:
        tid = team.get("id")
        if not tid: continue
        roster_data = _http(ROSTER_URL.format(team_id=tid))
        if not roster_data: continue
        roster = roster_data.get("roster", [])
        for player_entry in roster:
            pos_code = ((player_entry.get("position") or {}).get("code") or "")
            # 1=P, 2=C, 3-6=infield, 7-9=OF, 10=DH
            if pos_code in ("1",):    # skip pitchers for batter logs
                continue
            person = player_entry.get("person") or {}
            pid = person.get("id")
            if not pid: continue
            log = _http(GAMELOG_URL.format(player_id=pid, year=year))
            if not log: continue
            splits = ((log.get("stats") or [{}])[0].get("splits") or [])
            if not splits: continue
            # Take last 14 games (most-recent first)
            last_14 = list(reversed(splits))[:14]
            n = len(last_14)
            if n < 5: continue    # need at least 5 games
            ab = sum(int((s.get("stat") or {}).get("atBats", 0)) for s in last_14)
            h = sum(int((s.get("stat") or {}).get("hits", 0)) for s in last_14)
            hr = sum(int((s.get("stat") or {}).get("homeRuns", 0)) for s in last_14)
            rbi = sum(int((s.get("stat") or {}).get("rbi", 0)) for s in last_14)
            runs = sum(int((s.get("stat") or {}).get("runs", 0)) for s in last_14)
            so = sum(int((s.get("stat") or {}).get("strikeOuts", 0)) for s in last_14)
            bb = sum(int((s.get("stat") or {}).get("baseOnBalls", 0)) for s in last_14)
            tb = sum(int((s.get("stat") or {}).get("totalBases", 0)) for s in last_14)
            if ab < 10:    # bench player
                continue
            avg = round(h / ab, 3) if ab else 0
            h_per_game = h / n
            hr_per_game = hr / n
            rbi_per_game = rbi / n
            run_per_game = runs / n
            pa_per_game = (ab + bb) / n if n else 4
            # Per-PA HR rate
            hr_rate_per_pa = hr / max(1, ab + bb)
            p_hr_yes = _binom_one_plus(hr_rate_per_pa, int(round(pa_per_game)))
            # 1+ hit
            p_hit_yes = _binom_one_plus(avg, int(round(ab / max(1, n))))
            # 2+ hit
            ab_per_game = ab / n
            poisson_lam = avg * ab_per_game
            p_2plus_hits = 1 - math.exp(-poisson_lam) - poisson_lam * math.exp(-poisson_lam)
            # 1+ RBI
            p_rbi_yes = _binom_one_plus(min(0.95, rbi_per_game), 1)
            p_run_yes = _binom_one_plus(min(0.95, run_per_game), 1)

            all_batters.append({
                "name": person.get("fullName"),
                "team_id": tid,
                "team_abbr": team.get("abbreviation"),
                "team_name": team.get("name"),
                "position": pos_code,
                "n_games_logged": n,
                "stats_last_14": {
                    "ab": ab, "h": h, "hr": hr, "rbi": rbi, "r": runs,
                    "so": so, "bb": bb, "tb": tb, "avg": avg,
                    "h_per_game": round(h_per_game, 3),
                    "hr_per_game": round(hr_per_game, 3),
                    "rbi_per_game": round(rbi_per_game, 3),
                },
                "props": {
                    "1_plus_hit": {"p": round(p_hit_yes, 4),
                                    "fair_yes": _american(p_hit_yes)},
                    "2_plus_hits": {"p": round(p_2plus_hits, 4),
                                     "fair_yes": _american(p_2plus_hits)},
                    "1_plus_hr": {"p": round(p_hr_yes, 4),
                                   "fair_yes": _american(p_hr_yes)},
                    "1_plus_rbi": {"p": round(p_rbi_yes, 4),
                                    "fair_yes": _american(p_rbi_yes)},
                    "1_plus_run": {"p": round(p_run_yes, 4),
                                    "fair_yes": _american(p_run_yes)},
                },
            })
            time.sleep(0.05)
    all_batters.sort(key=lambda b: -b["stats_last_14"]["avg"])
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season": year,
        "n_batters": len(all_batters),
        "top_avg": [b["name"] for b in all_batters[:5]],
        "batters": all_batters,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB batter logs: {p.get('n_batters', 0)} batters")
    print(f"  Top 5 by AVG: {p.get('top_avg', [])}")
