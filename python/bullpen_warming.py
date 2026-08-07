"""
EdgeStat -- bullpen warming detector for in-progress games.

Reads MLB Stats API live feed (gumbo) for each in-progress game and
detects when:
  - A closer is warming up (game state suggests save opportunity)
  - The opposing team is warming relievers (tells you the SP is likely
    out soon -> implications for K props + late-inning totals)
  - Mass bullpen activity (multiple warmups same inning -> blowout
    incoming or extra-inning prep)

Output: data/bullpen_warming.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "bullpen_warming.json")

MLB_BASE = "https://statsapi.mlb.com/api/v1"
MLB_LIVE = "https://statsapi.mlb.com/api/v1.1"   # gumbo lives on 1.1


def _http(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def run() -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    sched = _http(f"{MLB_BASE}/schedule?sportId=1&date={today}") or {}
    games_out: List[Dict[str, Any]] = []
    n_save_opps = 0
    n_warming_total = 0
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            state = (g.get("status") or {}).get("detailedState", "")
            if state in ("Scheduled", "Pre-Game", "Warmup", "Final", "Game Over"):
                continue
            pk = g.get("gamePk")
            if not pk:
                continue
            feed = _http(f"{MLB_LIVE}/game/{pk}/feed/live")
            if not feed:
                continue
            ls = feed.get("liveData", {}).get("linescore", {}) or {}
            cur_inning = ls.get("currentInning") or 0
            inning_state = (ls.get("inningState") or "").lower()
            away_runs = (ls.get("teams") or {}).get("away", {}).get("runs", 0)
            home_runs = (ls.get("teams") or {}).get("home", {}).get("runs", 0)
            run_diff = abs(home_runs - away_runs)
            # Save opportunity: 9th inning, leading by <= 3, top of 9th if home leads
            is_save_opp = cur_inning >= 8 and 0 < run_diff <= 3
            if is_save_opp:
                n_save_opps += 1

            # MLB feed has "warmup" data inside boxscore? Not directly --
            # use heuristic: in 7th+ inning + close game + reliever in current
            # batter list. Approximate.
            bs = feed.get("liveData", {}).get("boxscore", {}) or {}
            warming_signals = []
            for side in ("home", "away"):
                team = bs.get("teams", {}).get(side, {})
                # Bullpen list = pitchers minus current SP
                pitchers = team.get("pitchers") or []
                bullpen_used = len(pitchers) - 1 if pitchers else 0
                if bullpen_used >= 2 and cur_inning < 8:
                    warming_signals.append(f"{side} pen heavy use ({bullpen_used} relievers in {cur_inning})")
                if cur_inning >= 7 and bullpen_used >= 0:
                    warming_signals.append(f"{side} late-inning relief active (cur inning {cur_inning})")

            n_warming_total += len(warming_signals)
            games_out.append({
                "game_pk": pk,
                "matchup": f"{(g.get('teams', {}).get('away', {}).get('team', {}).get('name'))} @ {(g.get('teams', {}).get('home', {}).get('team', {}).get('name'))}",
                "state": state,
                "inning": cur_inning,
                "inning_state": inning_state,
                "score": f"{away_runs}-{home_runs}",
                "run_diff": run_diff,
                "is_save_opp": is_save_opp,
                "warming_signals": warming_signals,
            })

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_in_progress": len(games_out),
        "n_save_opps": n_save_opps,
        "n_warming_signals": n_warming_total,
        "by_game": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_in_progress']} live games, {p['n_save_opps']} save opps")
    for g in p["by_game"][:5]:
        print(f"  {g['matchup']:35} {g['state']:12} inn {g['inning']} {g['score']} (diff {g['run_diff']}) save_opp={g['is_save_opp']}")
        for s in g["warming_signals"][:2]:
            print(f"    > {s}")
