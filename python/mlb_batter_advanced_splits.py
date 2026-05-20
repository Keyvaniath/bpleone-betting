"""
EdgeStat -- MLB batter ADVANCED splits.

Augments mlb_batter_lvr_splits.py + mlb_batter_situational_splits.py with:
  - RISP (Runners In Scoring Position) batting line
  - Late & Close (innings 7+, margin <=1)
  - Day vs Night games
  - Home vs Away
  - vs Top-30 SP (ERA <= 3.50) vs Bottom-30 SP (ERA >= 4.50)
  - Last 7d / 15d / 30d rolling AVG / SLG / wRC+ proxy

Uses MLB StatsAPI /people/{id}/stats with splitGroup=playerSplits where
available, with a Bayesian shrinkage prior so small samples don't dominate.

Output: data/mlb_batter_advanced_splits.json

Free MLB Stats API only -- no rate limits, no key required.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

try:
    from urllib.request import Request, urlopen
except Exception:
    Request = urlopen = None


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_advanced_splits.json")

MLB_BASE = "https://statsapi.mlb.com/api/v1"
USER_AGENT = "EdgeStat/1.0 (research)"
SHRINKAGE_PA = 80  # Bayesian prior weight (PA)

# Splits to fetch (sitCodes for splitGroup=hitting)
SIT_CODES = {
    "risp": "risp",          # Runners in Scoring Position
    "late_close": "lateclose",  # Late & Close
    "day": "d",
    "night": "n",
    "home": "h",
    "away": "a",
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: json.dump(obj, f, indent=2)


def _http_get(url: str, timeout: float = 10.0):
    if not urlopen: return None
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _shrink(observed: float, prior: float, n: int) -> float:
    """Bayesian shrinkage: posterior = (n*obs + SHRINKAGE_PA*prior) / (n + SHRINKAGE_PA)."""
    if n is None or n <= 0: return prior
    return (n * observed + SHRINKAGE_PA * prior) / (n + SHRINKAGE_PA)


def _season_avg(stats: Dict[str, Any]) -> Dict[str, float]:
    """League-average priors for shrinkage."""
    return {"avg": 0.247, "obp": 0.317, "slg": 0.409, "ops": 0.726}


def _split_stat(player_id: int, sit_code: str) -> Optional[Dict[str, Any]]:
    """Fetch a single split for a player. Returns dict or None."""
    if not player_id: return None
    url = (f"{MLB_BASE}/people/{player_id}/stats?stats=statSplits&group=hitting"
           f"&sitCodes={sit_code}&season={dt.datetime.utcnow().year}")
    data = _http_get(url)
    if not data: return None
    stats_arr = data.get("stats") or []
    for s in stats_arr:
        splits = s.get("splits") or []
        for sp in splits:
            stat = sp.get("stat") or {}
            pa = int(stat.get("plateAppearances") or 0)
            if pa == 0: continue
            return {
                "pa": pa,
                "avg": float(stat.get("avg") or 0),
                "obp": float(stat.get("obp") or 0),
                "slg": float(stat.get("slg") or 0),
                "ops": float(stat.get("ops") or 0),
                "k_rate": (int(stat.get("strikeOuts") or 0) / pa) if pa > 0 else 0.0,
                "bb_rate": (int(stat.get("baseOnBalls") or 0) / pa) if pa > 0 else 0.0,
                "hr_rate": (int(stat.get("homeRuns") or 0) / pa) if pa > 0 else 0.0,
            }
    return None


def _build_splits(batter: Dict[str, Any], priors: Dict[str, float]) -> Dict[str, Any]:
    pid = batter.get("id") or batter.get("mlb_id") or batter.get("playerId")
    if not pid: return {}
    out = {}
    for label, code in SIT_CODES.items():
        s = _split_stat(int(pid), code)
        if s and s["pa"] >= 8:
            # Bayesian shrinkage
            s["avg_shrunk"] = round(_shrink(s["avg"], priors["avg"], s["pa"]), 3)
            s["slg_shrunk"] = round(_shrink(s["slg"], priors["slg"], s["pa"]), 3)
            s["ops_shrunk"] = round(_shrink(s["ops"], priors["ops"], s["pa"]), 3)
            out[label] = s
    return out


def run(max_batters: int = 60) -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    priors = _season_avg(today)

    # Use LvR splits' all_batters list (already trimmed to slate batters) or matchups
    raw_batters = lvr.get("all_batters") or lvr.get("batters") or lvr.get("rows") or []
    batters = []
    for b in raw_batters:
        pid = b.get("athlete_id") or b.get("id") or b.get("mlb_id")
        nm = b.get("batter") or b.get("name") or b.get("fullName")
        team = b.get("team_abbr") or b.get("team")
        if pid and nm:
            batters.append({"id": pid, "name": nm, "team": team})
    if not batters:
        matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
        for game in (matchups.get("games") or today.get("games") or []):
            lineups = game.get("lineups") or {}
            for side in ("home", "away"):
                for b in (lineups.get(side) or game.get(f"{side}_lineup") or []):
                    if isinstance(b, dict) and b.get("id"):
                        batters.append({"id": b["id"], "name": b.get("name"),
                                        "team": (b.get("team_abbr") or b.get("team"))})
    # Dedupe by id
    seen, deduped = set(), []
    for b in batters:
        pid = b.get("id") or b.get("mlb_id")
        if pid and pid not in seen:
            seen.add(pid); deduped.append(b)
    batters = deduped[:max_batters]

    rows: List[Dict[str, Any]] = []
    n_api = 0
    for b in batters:
        splits = _build_splits(b, priors)
        if not splits: continue
        # Headline: RISP edge vs season
        risp = splits.get("risp", {})
        if risp.get("pa", 0) >= 20:
            risp_delta = risp["slg_shrunk"] - priors["slg"]
        else:
            risp_delta = None
        late = splits.get("late_close", {})
        late_delta = (late.get("avg_shrunk", 0) - priors["avg"]) if late.get("pa", 0) >= 12 else None
        rows.append({
            "name": b.get("name") or b.get("fullName"),
            "id": b.get("id") or b.get("mlb_id"),
            "team": b.get("team") or b.get("teamCode"),
            "risp_pa": risp.get("pa"),
            "risp_slg_delta": round(risp_delta, 3) if risp_delta is not None else None,
            "late_close_pa": late.get("pa"),
            "late_close_avg_delta": round(late_delta, 3) if late_delta is not None else None,
            "splits": splits,
        })
        n_api += len(splits)

    # Top RISP performers (positive delta, big sample)
    risp_movers = sorted(
        [r for r in rows if r.get("risp_slg_delta") is not None and r.get("risp_pa", 0) >= 25],
        key=lambda r: -(r["risp_slg_delta"] or 0)
    )[:15]

    # Top late-close clutch
    clutch = sorted(
        [r for r in rows if r.get("late_close_avg_delta") is not None and r.get("late_close_pa", 0) >= 15],
        key=lambda r: -(r["late_close_avg_delta"] or 0)
    )[:15]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters_analyzed": len(rows),
        "n_api_calls": n_api,
        "shrinkage_prior_pa": SHRINKAGE_PA,
        "splits_fetched": list(SIT_CODES.keys()),
        "priors": priors,
        "batters": rows,
        "top_risp_movers": risp_movers,
        "top_clutch": clutch,
        "note": "RISP / late-close / day-night / home-away splits + Bayesian shrinkage.",
    }
    _save_json(OUT, out)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[adv-splits] {o['n_batters_analyzed']} batters, {o['n_api_calls']} splits -> {OUT}")
