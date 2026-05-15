"""
EdgeStat -- pick-em (PrizePicks) integration.

Pulls PrizePicks' daily MLB projections (their lines, which differ from DK's),
runs our model at PP's line, and flags spots where PP is materially softer
than DK on the same player + market.

PrizePicks scoring (Power Plays, all legs must hit):
  2-leg  -> 3x   breakeven per leg ~= 57.7%
  3-leg  -> 5x   breakeven per leg ~= 58.5%
  4-leg  -> 10x  breakeven per leg ~= 56.2%
  5-leg  -> 20x  breakeven per leg ~= 54.9%
  6-leg  -> 25x  breakeven per leg ~= 55.9%

Practically: any leg the model says >= 60% is a candidate for PP entry.

Sleeper Picks needs auth (their public endpoint is SPA-rendered). TODO: add
once Brandon hands over a Bearer token from his account.

Writes data/pickem.json. The pickem.html page renders side-by-side comparison.
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore


PP_API = "https://api.prizepicks.com/projections"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pickem.json")

# Browser-style headers required (the bare requests UA gets 403'd by Cloudflare).
# Multiple variants so we can retry with different fingerprints when one fails.
PP_HEADER_VARIANTS = [
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://app.prizepicks.com",
        "Referer": "https://app.prizepicks.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
                      "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://app.prizepicks.com",
        "Referer": "https://app.prizepicks.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Origin": "https://app.prizepicks.com",
        "Referer": "https://app.prizepicks.com/",
    },
]
# Backwards-compat alias used elsewhere
PP_HEADERS = PP_HEADER_VARIANTS[0]

# PrizePicks stat_type -> our internal market key.
STAT_MAP = {
    "Pitcher Strikeouts": "pitcher_strikeouts",
    "Hits": "batter_hits",
    "Total Bases": "batter_total_bases",
    "Home Runs": "batter_home_runs",
    # The non-mapped PP markets (H+R+RBIs, Singles, Doubles, etc.) are still
    # surfaced raw -- the user can eyeball them even without a model projection.
}

# Per-leg breakeven probability required for the corresponding PP Power Play.
PP_BREAKEVEN_BY_LEGS = {2: 0.577, 3: 0.585, 4: 0.562, 5: 0.549, 6: 0.559}


def fetch_pp_projections() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (data, included). data = projections, included = players + game refs.

    Tries multiple header fingerprints because Cloudflare often blocks the first
    attempt from cloud-data-center IPs (GitHub Actions runners). Local machines
    typically succeed on the first try.
    """
    if requests is None:
        return [], []
    import time as _t
    last_status = None
    for i, headers in enumerate(PP_HEADER_VARIANTS):
        try:
            r = requests.get(PP_API, params={"league_id": 2, "per_page": 500},
                             headers=headers, timeout=15)
            last_status = r.status_code
            if r.ok:
                try:
                    j = r.json()
                except Exception:
                    continue
                if (j.get("data") or []):
                    return j.get("data", []), j.get("included", [])
        except Exception:
            pass
        # Backoff between variants
        _t.sleep(0.6 + i * 0.4)
    print(f"  [x] PrizePicks: all {len(PP_HEADER_VARIANTS)} header variants failed (last status: {last_status}). "
          f"Cloudflare is blocking this IP -- proxy or local-cron required.")
    return [], []


def _index_players(included: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """{ppid (string): {name, team, position, ...}}"""
    out: Dict[str, Dict[str, Any]] = {}
    for x in included:
        if x.get("type") != "new_player":
            continue
        out[x["id"]] = x.get("attributes", {})
    return out


def _index_games(included: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for x in included:
        if x.get("type") == "game":
            out[x["id"]] = x.get("attributes", {})
    return out


def parse_projections() -> List[Dict[str, Any]]:
    """Return list of {player, line, stat_type, market, start_time, status, ...} for all MLB props."""
    data, included = fetch_pp_projections()
    players = _index_players(included)
    games = _index_games(included)
    out = []
    for p in data:
        a = p["attributes"]
        rel = p.get("relationships", {})
        player_ref = (rel.get("new_player", {}) or {}).get("data") or {}
        ppid = player_ref.get("id")
        player_attrs = players.get(ppid, {}) if ppid else {}
        game_ref = (rel.get("game", {}) or {}).get("data") or {}
        game_attrs = games.get(game_ref.get("id", ""), {})
        out.append({
            "ppid": ppid,
            "player": player_attrs.get("name"),
            "team": player_attrs.get("team"),
            "position": player_attrs.get("position"),
            "stat_type": a.get("stat_type"),
            "market": STAT_MAP.get(a.get("stat_type")),
            "line": a.get("line_score"),
            "start_time": a.get("start_time"),
            "status": a.get("status"),
            "description": a.get("description"),
            "game_info": game_attrs.get("home_team", "") + " vs " + game_attrs.get("away_team", ""),
        })
    return out


# -------------------- Side-by-side vs DK --------------------

def _load_dk_props() -> List[Dict[str, Any]]:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "props.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f).get("top_edges", [])
    except Exception:
        return []


def _project_at_line(market: str, pid: int, line: float, lineup_order: Optional[int] = None) -> float:
    """Re-run our model at a specific line. Returns model_prob_over."""
    try:
        from props_pipeline import (project_pitcher_ks, project_batter_hr,
                                    project_batter_hits, project_batter_tb)
        if market == "pitcher_strikeouts":
            p, _ = project_pitcher_ks(pid, line)
        elif market == "batter_home_runs":
            p, _ = project_batter_hr(pid, line, lineup_order)
        elif market == "batter_hits":
            p, _ = project_batter_hits(pid, line, lineup_order)
        elif market == "batter_total_bases":
            p, _ = project_batter_tb(pid, line, lineup_order)
        else:
            return 0.5
        return p
    except Exception:
        return 0.5


def build_pickem() -> Dict[str, Any]:
    pp = parse_projections()
    if not pp:
        return {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "book": "prizepicks", "warning": "PrizePicks API returned no data",
                "props": []}

    # Filter to pre_game props in markets we model.
    modeled = [p for p in pp if p.get("status") == "pre_game" and p.get("market")]
    # Filter to those with a matchable player ID.
    try:
        from props_pipeline import resolve_player_id
    except Exception:
        resolve_player_id = lambda name: None  # noqa

    dk_props = _load_dk_props()
    # Index DK props by (player_id, market) -> {line, dk_over, dk_under, model_prob_over}
    dk_index: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for r in dk_props:
        if r.get("player_id") and r.get("market"):
            dk_index[(r["player_id"], r["market"])] = r

    out: List[Dict[str, Any]] = []
    for p in modeled:
        pid = resolve_player_id(p["player"]) if p.get("player") else None
        if not pid or not isinstance(p.get("line"), (int, float)):
            continue
        # Project at PP's line.
        prob_over = _project_at_line(p["market"], pid, float(p["line"]))
        prob_under = 1.0 - prob_over
        # Compare to DK if same market is priced.
        dk = dk_index.get((pid, p["market"]))
        dk_line = dk.get("line") if dk else None
        delta = (p["line"] - dk_line) if (dk_line is not None) else None
        # Side recommendation: hit PP's softer line if line moved your way.
        if dk_line is not None and delta is not None:
            if delta < 0:
                favor = "OVER"   # PP line lower than DK -> easier to go over on PP
                pp_advantage = -delta
            elif delta > 0:
                favor = "UNDER"
                pp_advantage = delta
            else:
                favor = None
                pp_advantage = 0
        else:
            favor = None
            pp_advantage = None

        # PP "qualifies as power-play leg" if model prob >= breakeven for some legs count.
        qualifies = {legs: round(prob_over, 4) for legs in PP_BREAKEVEN_BY_LEGS
                     if prob_over >= PP_BREAKEVEN_BY_LEGS[legs]}
        qualifies_under = {legs: round(prob_under, 4) for legs in PP_BREAKEVEN_BY_LEGS
                           if prob_under >= PP_BREAKEVEN_BY_LEGS[legs]}

        out.append({
            "player": p["player"],
            "team": p.get("team"),
            "player_id": pid,
            "market": p["market"],
            "stat_type": p["stat_type"],
            "pp_line": p["line"],
            "dk_line": dk_line,
            "delta": round(delta, 2) if delta is not None else None,
            "model_prob_over": round(prob_over, 4),
            "model_prob_under": round(prob_under, 4),
            "pp_softer_for": favor,           # OVER/UNDER -- which side benefits from PP's line vs DK
            "pp_advantage": pp_advantage,
            "power_play_qualifies_over": qualifies,
            "power_play_qualifies_under": qualifies_under,
        })

    # Sort: PP-advantaged + high model prob first.
    def score(r):
        pa = r.get("pp_advantage") or 0
        best_prob = max(r["model_prob_over"], r["model_prob_under"])
        return (pa * 10) + best_prob
    out.sort(key=score, reverse=True)

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "book": "prizepicks",
        "raw_pp_props": len(pp),
        "modeled_props": len(out),
        "pp_breakeven_by_legs": PP_BREAKEVEN_BY_LEGS,
        "props": out,
        "raw_unmodeled_count": sum(1 for p in pp if p.get("status") == "pre_game" and not p.get("market")),
    }


def write_pickem(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote pickem -> {path}")
    print(f"  Raw PP props: {payload.get('raw_pp_props', 0)}")
    print(f"  Modeled props: {payload.get('modeled_props', 0)}")
    high_conf = [p for p in payload.get("props", [])
                 if p["model_prob_over"] >= 0.6 or p["model_prob_under"] >= 0.6]
    print(f"  Power-play eligible (>= 60% one side): {len(high_conf)}")
    # Show top side-by-side comparisons
    softer = [p for p in payload.get("props", []) if p.get("pp_advantage")]
    if softer:
        print(f"  PP-softer-than-DK: {len(softer)}")
        for p in softer[:5]:
            print(f"    {p['player']:24} {p['stat_type']:22} PP={p['pp_line']:>5} DK={p['dk_line']:>5} delta={p['delta']:>+5} favor={p['pp_softer_for']}")


if __name__ == "__main__":
    payload = build_pickem()
    write_pickem(payload)
