"""
EdgeStat -- generic ESPN box-score -> per-player game logs + game results.

The DATA LAYER of the cross-sport grading adapter. MLB already settles its picks
against real box scores (player_gamelogs.json + historical_mlb.json), so its
picks feed the learning loop and earn CLV; every other sport voided its picks
unsettled for lack of an outcome feed. This produces the same real outcomes for
any ESPN box-score sport so that sport's picks can finally settle + learn.

Supported shapes:
  - basketball (WNBA today, NBA in Oct): one stat row per player.
  - football (NFL): stats split across passing/rushing/receiving categories,
    aggregated per player.

Outputs (mirroring the MLB shapes so the graders stay parallel):
  data/<sport>_player_gamelogs.json -> {by_name: {name: {name, games: [{date, ...}]}}}
  data/<sport>_historical.json      -> {games: [{date, home_abbrev, away_abbrev,
                                        home_score, away_score}]}

Back-date with an anchor date (YYYY-MM-DD) to validate against an archived season
(e.g. NFL 2025) before that sport's season is live.
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

# Basketball: each player has one stats row; we keep these columns (3PT is
# "made-attempted" -> made).
BASKETBALL_STATS = {
    "pts": "PTS", "reb": "REB", "ast": "AST",
    "stl": "STL", "blk": "BLK", "to": "TO", "min": "MIN", "fg3m": "3PT",
}
# Football: stats live under per-category blocks. (category -> {ESPN label -> field}).
FOOTBALL_FIELDS = {
    "passing":   {"YDS": "pass_yds", "TD": "pass_td", "INT": "pass_int"},
    "rushing":   {"YDS": "rush_yds", "CAR": "rush_att", "TD": "rush_td", "LONG": "longest_rush"},
    "receiving": {"REC": "rec", "YDS": "rec_yds", "TD": "rec_td", "TGTS": "targets",
                  "LONG": "longest_reception"},
}
# Hockey: skater stats indexed by column label (forwards + defenses blocks hold
# the athletes; the 'skaters' block is a summary with no athletes).
HOCKEY_STATS = {"HT": "hits", "BS": "blocks", "G": "goals", "A": "assists", "SOG": "shots", "PIM": "pim"}

CFG_WNBA = {"sport_key": "wnba", "espn_path": "basketball/wnba", "kind": "basketball", "stats": BASKETBALL_STATS}
CFG_NBA = {"sport_key": "nba", "espn_path": "basketball/nba", "kind": "basketball", "stats": BASKETBALL_STATS}
CFG_NFL = {"sport_key": "nfl", "espn_path": "football/nfl", "kind": "football"}
CFG_NHL = {"sport_key": "nhl", "espn_path": "hockey/nhl", "kind": "hockey", "stats": HOCKEY_STATS}


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


def _completed_event_ids(espn_path: str, days_back: int, anchor: dt.date) -> List[str]:
    ids: List[str] = []
    for i in range(days_back + 1):
        d = anchor - dt.timedelta(days=i)
        data = _http(f"{BASE_URL}/{espn_path}/scoreboard?dates={d.strftime('%Y%m%d')}")
        for ev in ((data or {}).get("events") or []):
            comp = (ev.get("competitions") or [{}])[0]
            status = ((comp.get("status") or {}).get("type") or {})
            if status.get("completed") and ev.get("id"):
                ids.append(str(ev["id"]))
    return ids


def _game_result(summary: Dict[str, Any]):
    """(date, game_dict) from a summary header -- shared by both parsers."""
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    date = (comp.get("date") or "")[:10]
    competitors = comp.get("competitors") or []
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    home_ab = ((home.get("team") or {}).get("abbreviation") or "").upper()
    away_ab = ((away.get("team") or {}).get("abbreviation") or "").upper()
    home_sc = _to_int(home.get("score"))
    away_sc = _to_int(away.get("score"))

    def _periods(c):
        return [_to_int(x.get("value") if isinstance(x, dict) else x)
                for x in (c.get("linescores") or [])]

    home_nm = ((home.get("team") or {}).get("displayName") or "")
    away_nm = ((away.get("team") or {}).get("displayName") or "")
    game = None
    if date and home_ab and away_ab and home_sc is not None and away_sc is not None:
        game = {"date": date, "home_abbrev": home_ab, "away_abbrev": away_ab,
                "home_name": home_nm, "away_name": away_nm,
                "home_score": home_sc, "away_score": away_sc,
                "home_periods": _periods(home), "away_periods": _periods(away)}
    return date, game


def _parse_basketball(summary: Dict[str, Any], date: str, stats_cfg: Dict[str, str]) -> List[Dict[str, Any]]:
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
                rec: Dict[str, Any] = {"name": nm, "date": date}
                for key, col in stats_cfg.items():
                    if col in idx and idx[col] < len(stat_vals):
                        raw = stat_vals[idx[col]]
                        rec[key] = _made(raw) if col == "3PT" else _to_int(raw)
                if any(rec.get(k) is not None for k in stats_cfg):
                    rows.append(rec)
    return rows


def _parse_football(summary: Dict[str, Any], date: str) -> List[Dict[str, Any]]:
    """Aggregate each player's stats across passing/rushing/receiving categories."""
    agg: Dict[str, Dict[str, Any]] = {}
    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        for cat in (team_block.get("statistics") or []):
            fmap = FOOTBALL_FIELDS.get((cat.get("name") or "").lower())
            if not fmap:
                continue
            labels = [str(l).upper() for l in (cat.get("labels") or [])]
            idx = {lab: labels.index(lab) for lab in fmap if lab in labels}
            for ath in (cat.get("athletes") or []):
                nm = ((ath.get("athlete") or {}).get("displayName") or "").strip()
                stat_vals = ath.get("stats") or []
                if not nm or not stat_vals:
                    continue
                rec = agg.setdefault(nm, {"name": nm, "date": date})
                for lab, field in fmap.items():
                    if lab in idx and idx[lab] < len(stat_vals):
                        v = _to_int(stat_vals[idx[lab]])
                        if v is not None:
                            rec[field] = v
                # Passing completions/attempts arrive combined as "22/30".
                if "C/ATT" in labels and labels.index("C/ATT") < len(stat_vals):
                    ca = str(stat_vals[labels.index("C/ATT")])
                    if "/" in ca:
                        c, a = _to_int(ca.split("/")[0]), _to_int(ca.split("/")[1])
                        if c is not None: rec["pass_cmp"] = c
                        if a is not None: rec["pass_att"] = a
    rows: List[Dict[str, Any]] = []
    for rec in agg.values():
        # anytime touchdown = rushing TD + receiving TD (player scored).
        rec["anytime_td"] = (rec.get("rush_td") or 0) + (rec.get("rec_td") or 0)
        rows.append(rec)
    return rows


def _parse_hockey(summary: Dict[str, Any], date: str, stats_cfg: Dict[str, str]) -> List[Dict[str, Any]]:
    """Skater stats (hits/blocks/goals/assists/shots) from the forwards + defenses
    blocks (the 'skaters' block is a summary with no athletes)."""
    agg: Dict[str, Dict[str, Any]] = {}
    for team_block in ((summary.get("boxscore") or {}).get("players") or []):
        for grp in (team_block.get("statistics") or []):
            if (grp.get("name") or "").lower() not in ("forwards", "defenses", "defensemen"):
                continue
            labels = [str(l).upper() for l in (grp.get("labels") or [])]
            idx = {lab: labels.index(lab) for lab in stats_cfg if lab in labels}
            for ath in (grp.get("athletes") or []):
                nm = ((ath.get("athlete") or {}).get("displayName") or "").strip()
                stat_vals = ath.get("stats") or []
                if not nm or not stat_vals:
                    continue
                rec = agg.setdefault(nm, {"name": nm, "date": date})
                for lab, field in stats_cfg.items():
                    if lab in idx and idx[lab] < len(stat_vals):
                        v = _to_int(stat_vals[idx[lab]])
                        if v is not None:
                            rec[field] = v
    return list(agg.values())


def run(cfg: Dict[str, Any], days_back: int = 8, anchor_date: Optional[str] = None) -> Dict[str, Any]:
    espn_path = cfg["espn_path"]
    sport_key = cfg["sport_key"]
    kind = cfg.get("kind", "basketball")
    anchor = dt.date.fromisoformat(anchor_date) if anchor_date else dt.date.today()

    by_name: Dict[str, Dict[str, Any]] = {}
    games: List[Dict[str, Any]] = []
    seen_game = set()

    for eid in _completed_event_ids(espn_path, days_back, anchor):
        summ = _http(f"{BASE_URL}/{espn_path}/summary?event={eid}")
        if not summ:
            continue
        date, game = _game_result(summ)
        if game:
            gk = (game["date"], game["home_abbrev"], game["away_abbrev"])
            if gk not in seen_game:
                seen_game.add(gk)
                games.append(game)
        if kind == "football":
            rows = _parse_football(summ, date)
        elif kind == "hockey":
            rows = _parse_hockey(summ, date, cfg["stats"])
        else:
            rows = _parse_basketball(summ, date, cfg["stats"])
        for r in rows:
            key = r["name"].lower()
            prec = by_name.setdefault(key, {"name": r["name"], "games": []})
            if not any(g.get("date") == r.get("date") for g in prec["games"]):
                prec["games"].append({k: v for k, v in r.items() if k != "name"})

    now = dt.datetime.utcnow().isoformat(timespec="seconds")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f"{sport_key}_player_gamelogs.json"), "w") as f:
        json.dump({"generated_at": now, "sport": sport_key.upper(),
                   "n_players": len(by_name), "by_name": by_name}, f, indent=2)
    with open(os.path.join(DATA_DIR, f"{sport_key}_historical.json"), "w") as f:
        json.dump({"generated_at": now, "sport": sport_key.upper(),
                   "n_games": len(games), "games": games}, f, indent=2)
    return {"sport": sport_key, "n_players": len(by_name), "n_games": len(games)}


if __name__ == "__main__":
    import sys
    arg = (sys.argv[1].lower() if len(sys.argv) > 1 else "wnba")
    cfg = {"wnba": CFG_WNBA, "nba": CFG_NBA, "nfl": CFG_NFL, "nhl": CFG_NHL}.get(arg, CFG_WNBA)
    anchor = sys.argv[2] if len(sys.argv) > 2 else None
    r = run(cfg, anchor_date=anchor)
    print(f"[espn-box-logs] {r['sport']}: {r['n_players']} players, {r['n_games']} games "
          f"-> data/{r['sport'].lower()}_player_gamelogs.json + _historical.json")
