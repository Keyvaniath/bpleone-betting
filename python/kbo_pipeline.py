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


def _parse_score(v) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _winner_from_game(g: Dict[str, Any], home_eng: str, away_eng: str,
                      hs: Optional[int], as_: Optional[int]) -> Optional[str]:
    """Winner of a finished game. Daum's homeWlt/awayWlt carry W / L / D
    directly; fall back to the score. Returns the English team name, the literal
    'tie' for a KBO draw, or None if undecidable."""
    hw = (g.get("homeWlt") or "").upper()
    aw = (g.get("awayWlt") or "").upper()
    if hw == "W" or aw == "L":
        return home_eng
    if aw == "W" or hw == "L":
        return away_eng
    if hw == "D" or aw == "D":
        return "tie"
    if hs is not None and as_ is not None:
        if hs > as_: return home_eng
        if as_ > hs: return away_eng
        return "tie"
    return None


# Daum gameStatus -> our state. END/FINAL = done; BEFORE/READY = scheduled;
# CANCEL/SUSPEND = washed out; anything else (a live in-progress code) -> "in".
_STATE_MAP = {"END": "post", "FINAL": "post", "RESULT": "post",
              "BEFORE": "pre", "READY": "pre", "PsTPONE": "pre",
              "CANCEL": "cancelled", "RAINCANCEL": "cancelled", "SUSPEND": "cancelled"}


def _pull_daum_schedule(day: dt.date) -> List[Dict[str, Any]]:
    """Pull ONE KST date's KBO games from Daum's hermes API.

    The real result fields are homeTeamName / awayTeamName, homeResult /
    awayResult (final runs) and gameStatus (END / BEFORE / CANCEL) -- NOT the
    homeTeam.displayName / homeTeamScore / status keys the old parser read (those
    don't exist, so it always saw 0 games). Finished games also carry homeWlt /
    awayWlt (W/L/D) and a stable gameId, so kbo_pot_history can settle straight
    off this same feed by game date."""
    ds = day.strftime("%Y%m%d")
    url = (f"https://sports.daum.net/prx/hermes/api/game/schedule.json"
           f"?fromDate={ds}&toDate={ds}&leagueCode=kbo&seasonKey={day.year}")
    data = _http_json(url)
    if not data:
        return []
    sched = data.get("schedule") or {}
    out: List[Dict[str, Any]] = []
    for _date_key, games_list in sched.items():
        if not isinstance(games_list, list): continue
        for g in games_list:
            home = _map_team(g.get("homeTeamName"))
            away = _map_team(g.get("awayTeamName"))
            if not home or not away: continue
            status_raw = (g.get("gameStatus") or "").upper()
            state = _STATE_MAP.get(status_raw, "in")
            hs = _parse_score(g.get("homeResult"))
            as_ = _parse_score(g.get("awayResult"))
            winner = _winner_from_game(g, home, away, hs, as_) if state == "post" else None
            out.append({
                "game_id": str(g.get("gameId") or ""),
                "game_date": day.isoformat(),
                "home_team": home, "away_team": away,
                "home_abbrev": KBO_TEAMS[home][0] if home in KBO_TEAMS else "?",
                "away_abbrev": KBO_TEAMS[away][0] if away in KBO_TEAMS else "?",
                "home_score": hs, "away_score": as_,
                "status": g.get("gameStatus"),
                "state": state,
                "winner": winner,
                "venue": g.get("fieldName"),
                "game_time_kst": g.get("startTime"),
                "data_source": "daum_sports",
            })
    return out


def run() -> Dict[str, Any]:
    today = dt.date.today()
    # Query a 3-day UTC window. KST = UTC+9, so a "today" UTC fetch at 14:00 UTC
    # sees KST games that already FINISHED -- we'd never surface a bettable slate.
    # Pulling yesterday/today/tomorrow guarantees the next un-started slate is in
    # view, plus recent finals for settlement context.
    window: List[Dict[str, Any]] = []
    seen: set = set()
    for off in (-1, 0, 1):
        for g in _pull_daum_schedule(today + dt.timedelta(days=off)):
            gid = g.get("game_id") or f"{g['game_date']}|{g['home_team']}|{g['away_team']}"
            if gid in seen:
                continue
            seen.add(gid)
            window.append(g)

    # Bettable slate = the EARLIEST date that still has pre/in games. The model
    # prices `matches`, so it must never contain a finished game (that would be a
    # lookahead "pick" on a decided result).
    upcoming = [g for g in window if g["state"] in ("pre", "in")]
    if upcoming:
        next_date = min(g["game_date"] for g in upcoming)
        matches = [g for g in window if g["game_date"] == next_date and g["state"] in ("pre", "in")]
        source = "daum_sports (live)"
        note = f"{len(matches)} KBO games on the next slate ({next_date}) -- real data from Daum Sports."
    else:
        matches = []
        source = "daum_sports (no upcoming games)"
        note = "No upcoming KBO games in the 3-day window (KBO is dark on Mondays / between series)."

    recent_finals = [g for g in window if g["state"] == "post"][-20:]

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
        "recent_finals": recent_finals,
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
