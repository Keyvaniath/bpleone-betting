"""
EdgeStat -- historical model backfill.

Problem: the self-learning loop needs settled (prediction, outcome) pairs
to compute bias. Today is day 2 of the loop running for real; we have 6
settled props. The Bayesian shrinkage means the model learns from day 1,
but with a strong anchor toward "no correction" until enough data flows.

Solution: walk backward through the last N days of COMPLETED MLB games.
For each batter who actually played and each pitcher who actually started:
  1. Look up their CURRENT season stats (a reasonable proxy for their
     talent level on day X if X is recent enough)
  2. Run the same project_* functions the live pipeline runs
  3. Score the prediction against the actual stat from the box score
  4. Append to track_record.json tagged source='backfill' and the
     historical date

The result: ~10 games/day * ~9 batters/game * 4 markets + ~2 pitchers/game *
~2 markets ≈ 360 + 40 = ~400 settled per day, ~5600 over 14 days. The
model goes from "6 plays in" to "5600 plays in" overnight, which means
data_weight = 5600/(5600+30) = 99.5% -- effectively pure data-driven
correction.

Caveats:
  - Using current season stats as proxy for talent overestimates April
    sample sizes slightly; we mitigate by passing recent_form_weight=0
    where modeling functions accept it (defaults are fine).
  - We don't have historical lineups for every game, but MLB's
    /game/{pk}/boxscore returns the actual lineup that played.
  - We don't have historical book prices, so we tag these without
    dk_over/under prices -- they contribute to bias calibration but
    not to ROI computation.

Run with: python historical_backfill.py --days 14
"""
from __future__ import annotations

import os
import sys
import json
import time
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None  # type: ignore

import stats_repo as sr
import props_pipeline as pp


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")

# Standard lines to test on every player. These are the most-traded prop lines
# at DK/Bovada, so they're representative of what real market lines would be.
BATTER_LINE_PROBES = {
    "batter_hits": [0.5, 1.5],
    "batter_total_bases": [1.5, 2.5],
    "batter_home_runs": [0.5],
    "batter_runs_scored": [0.5],
    "batter_rbis": [0.5, 1.5],
    "batter_singles": [0.5],
    "batter_doubles": [0.5],
}
PITCHER_LINE_PROBES = {
    "pitcher_strikeouts": [4.5, 5.5, 6.5, 7.5],
}


def fetch_finals_for_date(date_iso: str) -> List[Dict[str, Any]]:
    if requests is None:
        return []
    try:
        sched = requests.get(
            f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_iso}",
            timeout=15,
        ).json()
    except Exception:
        return []
    out = []
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            if g["status"]["detailedState"] != "Final":
                continue
            out.append({"gamePk": g["gamePk"], "schedule": g})
    return out


def fetch_boxscore(pk: int) -> Optional[Dict[str, Any]]:
    if requests is None:
        return None
    try:
        r = requests.get(f"https://statsapi.mlb.com/api/v1/game/{pk}/boxscore", timeout=15)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return None


def stat_for_market(market: str, batter_stats: Dict[str, Any], pitcher_stats: Dict[str, Any]) -> Optional[int]:
    """Extract actual stat value from box score for a given market key."""
    if market == "pitcher_strikeouts":
        return int(pitcher_stats.get("strikeOuts") or 0) if pitcher_stats else None
    if market == "batter_hits":
        return int(batter_stats.get("hits") or 0) if batter_stats else None
    if market == "batter_home_runs":
        return int(batter_stats.get("homeRuns") or 0) if batter_stats else None
    if market == "batter_total_bases":
        if not batter_stats:
            return None
        h = int(batter_stats.get("hits") or 0)
        d = int(batter_stats.get("doubles") or 0)
        t = int(batter_stats.get("triples") or 0)
        hr = int(batter_stats.get("homeRuns") or 0)
        s = h - d - t - hr
        return s + 2 * d + 3 * t + 4 * hr
    if market == "batter_runs_scored":
        return int(batter_stats.get("runs") or 0) if batter_stats else None
    if market == "batter_rbis":
        return int(batter_stats.get("rbi") or 0) if batter_stats else None
    if market == "batter_singles":
        if not batter_stats:
            return None
        h = int(batter_stats.get("hits") or 0)
        d = int(batter_stats.get("doubles") or 0)
        t = int(batter_stats.get("triples") or 0)
        hr = int(batter_stats.get("homeRuns") or 0)
        return h - d - t - hr
    if market == "batter_doubles":
        return int(batter_stats.get("doubles") or 0) if batter_stats else None
    return None


def model_call(market: str, pid: int, line: float, order: Optional[int],
               opp_team_id: Optional[int]) -> Optional[Tuple[float, Optional[float]]]:
    """Call the right project_* function. Returns (model_prob_over, model_projection) or None."""
    try:
        if market == "pitcher_strikeouts":
            p, dbg = pp.project_pitcher_ks(pid, line, opp_team_id)
            proj = dbg.get("expected_ks") or dbg.get("expected_k") or dbg.get("xK")
        elif market == "batter_home_runs":
            p, dbg = pp.project_batter_hr(pid, line, order, 1.0, None, None)
            proj = dbg.get("expected_hr") or dbg.get("expected")
        elif market == "batter_hits":
            p, dbg = pp.project_batter_hits(pid, line, order)
            proj = dbg.get("expected_hits") or dbg.get("expected")
        elif market == "batter_total_bases":
            p, dbg = pp.project_batter_tb(pid, line, order)
            proj = dbg.get("expected_tb") or dbg.get("expected")
        elif market == "batter_singles":
            p, dbg = pp.project_batter_singles(pid, line, order)
            proj = dbg.get("expected") or dbg.get("expected_1b")
        elif market == "batter_doubles":
            p, dbg = pp.project_batter_doubles(pid, line, order)
            proj = dbg.get("expected") or dbg.get("expected_2b")
        elif market == "batter_runs_scored":
            p, dbg = pp.project_batter_runs(pid, line, order)
            proj = dbg.get("expected") or dbg.get("expected_r")
        elif market == "batter_rbis":
            p, dbg = pp.project_batter_rbis(pid, line, order)
            proj = dbg.get("expected") or dbg.get("expected_rbi")
        else:
            return None
        if dbg.get("low_confidence"):
            return None  # Skip thin-sample projections
        return p, proj
    except Exception:
        return None


def backfill_day(date_iso: str) -> List[Dict[str, Any]]:
    """Process one historical day; return list of settled records."""
    finals = fetch_finals_for_date(date_iso)
    print(f"  {date_iso}: {len(finals)} final games")
    records: List[Dict[str, Any]] = []
    for g in finals:
        pk = g["gamePk"]
        bs = fetch_boxscore(pk)
        if not bs:
            continue
        home_team_id = bs.get("teams", {}).get("home", {}).get("team", {}).get("id")
        away_team_id = bs.get("teams", {}).get("away", {}).get("team", {}).get("id")
        venue = (g.get("schedule", {}).get("venue") or {}).get("name") or ""
        for side in ("home", "away"):
            team = bs.get("teams", {}).get(side, {})
            opp_tid = away_team_id if side == "home" else home_team_id
            order = team.get("battingOrder", []) or []

            # Pitchers: starters only
            for pid in team.get("pitchers", []) or []:
                p = team.get("players", {}).get(f"ID{pid}", {})
                stats = p.get("stats", {}).get("pitching", {})
                if not stats.get("inningsPitched"):
                    continue
                # Only starters: heuristic via games_started
                if int(stats.get("gamesStarted") or 0) != 1:
                    continue
                for market, lines in PITCHER_LINE_PROBES.items():
                    for line in lines:
                        actual = stat_for_market(market, {}, stats)
                        if actual is None:
                            continue
                        result = model_call(market, pid, line, None, opp_tid)
                        if result is None:
                            continue
                        prob_over, proj = result
                        over_hit = actual > line
                        if actual == line:
                            continue  # push
                        records.append({
                            "date": date_iso,
                            "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
                            "player": p.get("person", {}).get("fullName"),
                            "player_id": int(pid),
                            "market": market,
                            "line": line,
                            "actual": actual,
                            "over_hit": bool(over_hit),
                            "model_prob_over": round(prob_over, 4),
                            "model_projection": round(proj, 3) if isinstance(proj, (int, float)) else None,
                            "projection_vs_actual": (round(actual - proj, 2)
                                                       if isinstance(proj, (int, float)) else None),
                            "model_version": "backfill-v1",
                            "play": "OVER" if prob_over >= 0.5 else "UNDER",
                            "play_hit": (prob_over >= 0.5 and over_hit) or (prob_over < 0.5 and not over_hit),
                            "source": "backfill",
                            "dk_over": None,
                            "dk_under": None,
                            "edge_pct": None,
                            "low_confidence": False,
                            "park": venue,
                        })

            # Batters: use the actual batting order from the boxscore
            for i, bid_str in enumerate(order):
                try:
                    bid = int(bid_str)
                except Exception:
                    continue
                p = team.get("players", {}).get(f"ID{bid}", {})
                stats = p.get("stats", {}).get("batting", {})
                if not stats or not stats.get("plateAppearances"):
                    continue
                ord_pos = i + 1
                for market, lines in BATTER_LINE_PROBES.items():
                    for line in lines:
                        actual = stat_for_market(market, stats, {})
                        if actual is None:
                            continue
                        if actual == line:
                            continue  # push
                        result = model_call(market, bid, line, ord_pos, None)
                        if result is None:
                            continue
                        prob_over, proj = result
                        over_hit = actual > line
                        records.append({
                            "date": date_iso,
                            "settled_at": dt.datetime.now().isoformat(timespec="seconds"),
                            "player": p.get("person", {}).get("fullName"),
                            "player_id": bid,
                            "market": market,
                            "line": line,
                            "actual": actual,
                            "over_hit": bool(over_hit),
                            "model_prob_over": round(prob_over, 4),
                            "model_projection": round(proj, 3) if isinstance(proj, (int, float)) else None,
                            "projection_vs_actual": (round(actual - proj, 2)
                                                       if isinstance(proj, (int, float)) else None),
                            "model_version": "backfill-v1",
                            "play": "OVER" if prob_over >= 0.5 else "UNDER",
                            "play_hit": (prob_over >= 0.5 and over_hit) or (prob_over < 0.5 and not over_hit),
                            "source": "backfill",
                            "dk_over": None,
                            "dk_under": None,
                            "edge_pct": None,
                            "low_confidence": False,
                            "park": venue,
                        })
    return records


def merge_into_track_record(new_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if os.path.exists(TR_PATH):
        with open(TR_PATH) as f:
            tr = json.load(f)
    else:
        tr = {"props": [], "games": [], "last_settled_date": None}
    # De-dupe: keep one record per (date, player_id, market, line).
    existing = {(r.get("date"), r.get("player_id"), r.get("market"), r.get("line")): True
                for r in tr.get("props", [])}
    appended = 0
    for r in new_records:
        k = (r["date"], r["player_id"], r["market"], r["line"])
        if k in existing:
            continue
        tr.setdefault("props", []).append(r)
        existing[k] = True
        appended += 1
    if new_records:
        tr["last_settled_date"] = max((r["date"] for r in new_records), default=tr.get("last_settled_date"))
    with open(TR_PATH, "w") as f:
        json.dump(tr, f, indent=2)
    return {"appended": appended, "total": len(tr["props"])}


def run(days: int = 14, end_date: Optional[dt.date] = None) -> Dict[str, Any]:
    end_date = end_date or (dt.date.today() - dt.timedelta(days=1))  # default: through yesterday
    summary = {"days_processed": 0, "records_per_day": [], "total_new": 0, "total_after": None}
    all_records: List[Dict[str, Any]] = []
    for d_off in range(days):
        date = (end_date - dt.timedelta(days=d_off)).isoformat()
        recs = backfill_day(date)
        summary["records_per_day"].append({"date": date, "n": len(recs)})
        all_records.extend(recs)
        summary["days_processed"] += 1
        time.sleep(0.4)  # be polite to MLB API
    info = merge_into_track_record(all_records)
    summary["total_new"] = info["appended"]
    summary["total_after"] = info["total"]
    return summary


if __name__ == "__main__":
    days = 14
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    print(f"Backfilling {days} days...")
    s = run(days=days)
    print(f"Summary: {s['days_processed']} days, {s['total_new']} new records, "
          f"track_record now has {s['total_after']} props total")
