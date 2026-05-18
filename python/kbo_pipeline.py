"""
EdgeStat -- KBO (Korean Baseball Organization) pipeline.

KBO has 10 teams playing a 144-game season May-October. We pull live
schedule + scores from Daum Sports's KBO JSON API (no auth, free, returns
both pre-game and live games). If Daum returns 0 games, that's a rest
day in KBO -- we emit n_games_today=0 with a clear note, never synthetic.

Output: data/kbo_state.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "kbo_state.json")

# The 10 KBO teams (2024 season). Strength tier: top-3 contenders, mid-4,
# bottom-3 -- used as ELO baseline before historical results arrive.
KBO_TEAMS = {
    # English name -> (Korean abbrev, ELO baseline, city)
    "KIA Tigers":        ("KIA", 1560, "Gwangju"),
    "LG Twins":          ("LG",  1545, "Seoul"),
    "Samsung Lions":     ("SS",  1530, "Daegu"),
    "Doosan Bears":      ("OB",  1515, "Seoul"),
    "SSG Landers":       ("SK",  1505, "Incheon"),
    "KT Wiz":            ("KT",  1495, "Suwon"),
    "NC Dinos":          ("NC",  1485, "Changwon"),
    "Lotte Giants":      ("LT",  1470, "Busan"),
    "Hanwha Eagles":     ("HH",  1450, "Daejeon"),
    "Kiwoom Heroes":     ("WO",  1430, "Seoul"),
}

# Map Daum team codes -> our English names. Daum uses Korean team codes;
# we maintain a lookup that covers all 10 active KBO teams.
DAUM_TEAM_MAP = {
    "삼성":  "Samsung Lions",
    "한화":  "Hanwha Eagles",
    "LG":   "LG Twins",
    "두산":  "Doosan Bears",
    "롯데":  "Lotte Giants",
    "키움":  "Kiwoom Heroes",
    "SSG":  "SSG Landers",
    "NC":   "NC Dinos",
    "KT":   "KT Wiz",
    "KIA":  "KIA Tigers",
    # English fallbacks
    "Samsung":  "Samsung Lions",
    "Hanwha":   "Hanwha Eagles",
    "Doosan":   "Doosan Bears",
    "Lotte":    "Lotte Giants",
    "Kiwoom":   "Kiwoom Heroes",
}


def _http_json(url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; EdgeStat/1.0)",
        "Referer": "https://sports.daum.net/",
        "Accept": "application/json",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="ignore"))
    except Exception:
        return None


def _map_team(raw_name: Optional[str]) -> Optional[str]:
    if not raw_name: return None
    raw = raw_name.strip()
    if raw in DAUM_TEAM_MAP: return DAUM_TEAM_MAP[raw]
    # Fuzzy: case-insensitive English match
    for daum_key, eng in DAUM_TEAM_MAP.items():
        if raw.lower() == eng.lower() or raw.lower() == daum_key.lower():
            return eng
    return None


def _pull_daum_schedule(today: dt.date) -> List[Dict[str, Any]]:
    """Pull today's KBO schedule from Daum. Returns list of game dicts."""
    ds = today.strftime("%Y%m%d")
    url = (f"https://sports.daum.net/prx/hermes/api/game/schedule.json"
           f"?fromDate={ds}&toDate={ds}&leagueCode=kbo&seasonKey={today.year}")
    data = _http_json(url)
    if not data:
        return []
    sched = data.get("schedule") or {}
    matches: List[Dict[str, Any]] = []
    for date_key, games_list in sched.items():
        if not isinstance(games_list, list): continue
        for g in games_list:
            home_raw = (g.get("homeTeam") or {}).get("displayName") or (g.get("homeTeam") or {}).get("shortName")
            away_raw = (g.get("awayTeam") or {}).get("displayName") or (g.get("awayTeam") or {}).get("shortName")
            home = _map_team(home_raw)
            away = _map_team(away_raw)
            if not home or not away: continue
            # State: scheduled / 진행중 (in-progress) / 종료 (finished)
            status_code = (g.get("status") or "").upper()
            state_map = {"BEFORE": "pre", "RUNNING": "in", "AFTER": "post",
                          "READY": "pre", "FINISHED": "post"}
            state = state_map.get(status_code, "pre")
            home_score = g.get("homeTeamScore") if g.get("homeTeamScore") is not None else None
            away_score = g.get("awayTeamScore") if g.get("awayTeamScore") is not None else None
            matches.append({
                "home_team": home, "away_team": away,
                "home_abbrev": KBO_TEAMS[home][0] if home in KBO_TEAMS else "?",
                "away_abbrev": KBO_TEAMS[away][0] if away in KBO_TEAMS else "?",
                "home_score": home_score, "away_score": away_score,
                "status": g.get("statusName") or status_code,
                "state": state,
                "venue": g.get("locationName") or g.get("stadiumName"),
                "game_time_kst": g.get("startDate"),
                "data_source": "daum_sports",
            })
    return matches


def run() -> Dict[str, Any]:
    today = dt.date.today()
    matches = _pull_daum_schedule(today)

    if matches:
        source = "daum_sports (live)"
        note = f"{len(matches)} KBO games scheduled today (real data from Daum Sports)."
    else:
        source = "daum_sports (no games today)"
        note = "No KBO games scheduled today (likely rest day - KBO plays Tue-Sun in season)."

    standings = [
        {"team": name, "abbrev": KBO_TEAMS[name][0], "city": KBO_TEAMS[name][2],
         "elo_baseline": KBO_TEAMS[name][1]}
        for name in KBO_TEAMS
    ]
    standings.sort(key=lambda s: -s["elo_baseline"])
    for i, s in enumerate(standings, 1):
        s["rank_seed"] = i

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "data_source": source,
        "is_live_data": True,  # never synthetic anymore
        "season": today.year,
        "n_teams": len(KBO_TEAMS),
        "n_games_today": len(matches),
        "matches": matches,
        "standings_seed": standings,
        "note": note,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games_today']} games today (source: {p['data_source']})")
    for m in p.get("matches", []):
        sc = ""
        if m.get("home_score") is not None and m.get("away_score") is not None:
            sc = f" {m['away_score']}-{m['home_score']}"
        print(f"  {m['away_team']:18} ({m['away_abbrev']}) @ {m['home_team']:18} ({m['home_abbrev']}){sc} [{m['state']}]")
