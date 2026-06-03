"""
EdgeStat -- generic ESPN box-score -> per-player game logs + game results.

This is the DATA LAYER of the cross-sport grading adapter. MLB already settles
its picks against player_gamelogs.json + historical_mlb.json (real box scores),
so its picks feed the learning loop and earn real CLV. Every other sport voided
its picks unsettled because it had no outcome feed. This produces the same kind
of real outcomes for any ESPN box-score sport (basketball/wnba, basketball/nba,
...), so that sport's picks can finally settle + learn the way MLB does.

For each completed game in the trailing window it pulls the ESPN box score and
emits, mirroring the MLB shapes so the graders are parallel:
  data/<sport>_player_gamelogs.json  -> {by_name: {name: {name, games: [{date, pts,
                                          reb, ast, fg3m, stl, blk, to, min}]}}}
  data/<sport>_historical.json       -> {games: [{date, home_abbrev, away_abbrev,
                                          home_score, away_score}]}

Reusable: WNBA today, NBA in October plug straight in (same basketball box score).
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

# Basketball box-score config: which player stats to keep + the column header
# ESPN uses for each. 3PT comes as "made-attempted" (we keep made).
BASKETBALL_STATS = {
    "pts": "PTS", "reb": "REB", "ast": "AST",
    "stl": "STL", "blk": "BLK", "to": "TO", "min": "MIN", "fg3m": "3PT",
}

CFG_WNBA = {"sport_key": "wnba", "espn_path": "basketball/wnba", "stats": BASKETBALL_STATS}
CFG_NBA = {"sport_key": "nba", "espn_path": "basketball/nba", "stats": BASKETBALL_STATS}


def _http(url: str) -> Optional[Dict[str, Any]]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _to_int(s: Any) -> Optional[int]:
    try:
        return int(str(s).strip())
    except Exception:
        return None


def _made(s: Any) -> Optional[int]:
    """'4-9' -> 4 (makes); plain '4' -> 4."""
    t = str(s or "").strip()
    if "-" in t:
        return _to_int(t.split("-")[0])
    return _to_int(t)


def _completed_event_ids(espn_path: str, days_back: int) -> List[str]:
    today = dt.date.today()
    ids: List[str] = []
    for i in range(days_back + 1):
        d = today - dt.timedelta(days=i)
        url = f"{BASE_URL}/{espn_path}/scoreboard?dates={d.strftime('%Y%m%d')}"
        data = _http(url)
        for ev in ((data or {}).get("events") or []):
            comp = (ev.get("competitions") or [{}])[0]
            status = ((comp.get("status") or {}).get("type") or {})
            if status.get("completed") and ev.get("id"):
                ids.append(str(ev["id"]))
    return ids


def _parse_box(summary: Dict[str, Any], stats_cfg: Dict[str, str]):
    """Return (player_rows, game_result) for one game summary, or (None, None)."""
    header = summary.get("header") or {}
    comp = (header.get("competitions") or [{}])[0]
    date = (comp.get("date") or "")[:10]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    home_ab = ((home.get("team") or {}).get("abbreviation") or "").upper()
    away_ab = ((away.get("team") or {}).get("abbreviation") or "").upper()
    home_sc = _to_int(home.get("score"))
    away_sc = _to_int(away.get("score"))
    game = None
    if date and home_ab and away_ab and home_sc is not None and away_sc is not None:
        game = {"date": date, "home_abbrev": home_ab, "away_abbrev": away_ab,
                "home_score": home_sc, "away_score": away_sc}

    rows: List[Dict[str, Any]] = []
    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        for statblock in (team_block.get("statistics") or []):
            names = [str(n).upper() for n in (statblock.get("names") or [])]
            idx = {col: names.index(col) for col in set(stats_cfg.values()) if col in names}
            for ath in (statblock.get("athletes") or []):
                if ath.get("didNotPlay"):
                    continue
                nm = ((ath.get("athlete") or {}).get("displayName") or "").strip()
                stat_vals = ath.get("stats") or []
                if not nm or not stat_vals:
                    continue
                rec: Dict[str, Any] = {"date": date}
                for key, col in stats_cfg.items():
                    if col not in idx or idx[col] >= len(stat_vals):
                        continue
                    raw = stat_vals[idx[col]]
                    rec[key] = _made(raw) if col == "3PT" else _to_int(raw)
                if any(rec.get(k) is not None for k in stats_cfg):
                    rows.append({"name": nm, **rec})
    return rows, game


def run(cfg: Dict[str, Any], days_back: int = 8) -> Dict[str, Any]:
    espn_path = cfg["espn_path"]
    sport_key = cfg["sport_key"]
    stats_cfg = cfg["stats"]
    by_name: Dict[str, Dict[str, Any]] = {}
    games: List[Dict[str, Any]] = []
    seen_game = set()

    for eid in _completed_event_ids(espn_path, days_back):
        summ = _http(f"{BASE_URL}/{espn_path}/summary?event={eid}")
        if not summ:
            continue
        rows, game = _parse_box(summ, stats_cfg)
        if game:
            gk = (game["date"], game["home_abbrev"], game["away_abbrev"])
            if gk not in seen_game:
                seen_game.add(gk)
                games.append(game)
        for r in (rows or []):
            key = r["name"].lower()
            prec = by_name.setdefault(key, {"name": r["name"], "games": []})
            # de-dupe a player's game by date
            if not any(g.get("date") == r.get("date") for g in prec["games"]):
                prec["games"].append({k: v for k, v in r.items() if k != "name"})

    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    logs_out = {"generated_at": now, "sport": sport_key.upper(),
                "n_players": len(by_name), "by_name": by_name}
    hist_out = {"generated_at": now, "sport": sport_key.upper(),
                "n_games": len(games), "games": games}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f"{sport_key}_player_gamelogs.json"), "w") as f:
        json.dump(logs_out, f, indent=2)
    with open(os.path.join(DATA_DIR, f"{sport_key}_historical.json"), "w") as f:
        json.dump(hist_out, f, indent=2)
    return {"sport": sport_key, "n_players": len(by_name), "n_games": len(games)}


if __name__ == "__main__":
    import sys
    cfg = CFG_NBA if (len(sys.argv) > 1 and sys.argv[1].lower() == "nba") else CFG_WNBA
    r = run(cfg)
    print(f"[espn-box-logs] {r['sport']}: {r['n_players']} players, {r['n_games']} games "
          f"-> data/{r['sport'].lower()}_player_gamelogs.json + _historical.json")
