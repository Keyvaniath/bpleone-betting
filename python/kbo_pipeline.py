"""
EdgeStat -- KBO (Korean Baseball Organization) pipeline.

KBO has 10 teams playing a 144-game season May-October. No free official
JSON API, so we use a hybrid approach:
  1. Scrape KBO official schedule HTML (koreabaseball.com)
  2. Fall back to a synthetic round-robin schedule between the 10 known teams
     so the desk stays populated even when scraping fails

Output: data/kbo_state.json
"""
from __future__ import annotations

import os
import json
import re
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


def _http(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    h = {"User-Agent": "Mozilla/5.0 EdgeStat/1.0"}
    if headers: h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception:
        return None


def _scrape_kbo_schedule() -> List[Dict[str, Any]]:
    """Scrape today's KBO schedule from koreabaseball.com.
    Today's-game format: <li class="match"> blocks with team1 vs team2 + time."""
    html = _http("https://www.koreabaseball.com/Schedule/Schedule.aspx")
    if not html:
        return []
    matches: List[Dict[str, Any]] = []
    # KBO format uses Korean team names + 'VS' separator. Look for a stable pattern:
    # Korean team team abbrev or English mapping.
    abbrev_to_en = {v[0]: k for k, v in KBO_TEAMS.items()}
    # Pattern: "TM1 vs TM2" with abbreviations
    abbrev_pattern = re.compile(
        r"([A-Z]{2,3})\s*(?:vs|VS|대)\s*([A-Z]{2,3})",
    )
    for m in abbrev_pattern.finditer(html):
        a, b = m.group(1).strip(), m.group(2).strip()
        if a in abbrev_to_en and b in abbrev_to_en and a != b:
            matches.append({
                "home_team": abbrev_to_en[a],
                "away_team": abbrev_to_en[b],
                "home_abbrev": a,
                "away_abbrev": b,
                "home_score": None,
                "away_score": None,
                "status": "Scheduled",
                "state": "pre",
                "scraped": True,
            })
    return matches[:10]    # cap


def _synthetic_today_schedule(today: dt.date) -> List[Dict[str, Any]]:
    """Generate a plausible 5-game KBO day using a deterministic round-robin
    rotation. Ensures the desk stays populated when scraping fails."""
    teams = list(KBO_TEAMS.keys())
    # Day-of-year as rotation offset so the pairings rotate over time
    offset = today.timetuple().tm_yday % len(teams)
    rotated = teams[offset:] + teams[:offset]
    # KBO plays 5 games per day max (10 teams paired up)
    matches: List[Dict[str, Any]] = []
    for i in range(0, 10, 2):
        if i + 1 >= len(rotated):
            break
        away = rotated[i]
        home = rotated[i + 1]
        matches.append({
            "home_team": home,
            "away_team": away,
            "home_abbrev": KBO_TEAMS[home][0],
            "away_abbrev": KBO_TEAMS[away][0],
            "home_score": None,
            "away_score": None,
            "status": "Scheduled",
            "state": "pre",
            "synthetic": True,
            "game_time_utc": dt.datetime(
                today.year, today.month, today.day, 9, 30  # KBO ~18:30 KST = 09:30 UTC
            ).isoformat(),
        })
    return matches


def run() -> Dict[str, Any]:
    today = dt.date.today()
    matches = _scrape_kbo_schedule()
    source = "koreabaseball.com"
    if not matches:
        matches = _synthetic_today_schedule(today)
        source = "synthetic (5-game day, deterministic rotation)"

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
        "season": today.year,
        "n_teams": len(KBO_TEAMS),
        "n_games_today": len(matches),
        "matches": matches,
        "standings_seed": standings,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_games_today']} games today (source: {p['data_source']})")
    for m in p["matches"]:
        print(f"  {m['away_team']} ({m['away_abbrev']}) @ {m['home_team']} ({m['home_abbrev']})")
