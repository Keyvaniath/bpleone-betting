"""
EdgeStat -- one-shot outcome backfill for the 9/22-10/22 pipeline outage.

WHY: for 30 days daily-pipeline skipped 234 of its 324 steps, including every
outcome feed (box scores for NFL/NBA/NHL/WNBA, results for golf/tennis/UFC/F1/
soccer, MLB player gamelogs). The heartbeat kept running the ledger build, so
picks aged past the 4-day mark with no outcome data and were VOIDED as
"unsettleable: no outcome feed" -- real picks with real results, wins and
losses alike, silently dropped from the record.

WHAT: re-run each outcome feed ONCE with a lookback that reaches the oldest
outage-voided pick, extend the MLB gamelog fetch to the voided picks' players,
then run the normal ledger build. The grader already reconsiders voided picks
(it only skips SETTLED ones) and _reconcile_settled_voids clears a stale void
once a real outcome lands -- so this module only has to put the outcome data
back within reach. Nothing is graded here; no result is inferred.

Picks whose outcome data is genuinely gone stay voided. Voids for other reasons
(duplicate wager, preseason, rlm date-conflation) are untouched.

Runs once: writes data/outage_backfill_2026_10.json and exits early on any
later run (wired into daily-pipeline just before the ledger build).
"""
from __future__ import annotations

import os
import json
import datetime as dt
from collections import Counter, defaultdict
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MARKER = os.path.join(DATA_DIR, "outage_backfill_2026_10.json")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUTAGE_START = "2026-09-18"     # 4 days before the first failed run (9/22)
OUTAGE_REASON = "unsettleable: no outcome feed"
# Bump when a grader fix lands that the long-window outcome data can still
# serve; the next run re-fetches once and keeps the earlier pass under
# `previous_passes`. v2 (2026-10-22): MLB run lines had no grading branch.
# v3 (2026-10-23): NFL names with hyphens (Smith-Njigba, Amon-Ra) never matched.
# v4 (2026-10-23): NFL DFS receipts rescore while the long box window is loaded.
BACKFILL_VERSION = 4


def _load(p: str) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _outage_voids(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [p for p in picks
            if p.get("voided") and not p.get("settled")
            and str(p.get("voided_reason") or "").startswith(OUTAGE_REASON)
            and str(p.get("date") or "") >= OUTAGE_START]


def _tally(picks: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    t: Dict[str, Counter] = defaultdict(Counter)
    for p in _outage_voids(picks):
        t[str(p.get("sport")).upper()]["voided"] += 1
    return {k: dict(v) for k, v in t.items()}



def _regrade_nhl_settled() -> Dict[str, Any]:
    """Correct NHL picks the old grader settled WRONG (found 2026-10-22).

    Two grading bugs produced recorded results that the box score contradicts:
      * favourite puck lines (HOME/AWAY_MINUS_1.5) were never matched by the
        puck-line regex, fell through on their '_pl_' source name, and were
        graded as +1.5 -- too generous every time;
      * skater props took the FIRST box row within +/-2 days in list order
        (newest first), so across a back-to-back a prop could be graded on the
        adjacent night's game (e.g. a 10/15 hits prop settled on 10/17's line).
    Only picks where the fixed grader returns a DEFINITE, DIFFERENT result are
    changed; each keeps a `regraded` audit record (old result + payout, reason,
    timestamp). Picks the current data can't grade are left exactly as recorded.
    """
    import all_picks_tracker as apt
    led = _load(LEDGER)
    picks = led.get("picks") or []
    games = _load(os.path.join(DATA_DIR, "nhl_historical.json")).get("games") or []
    by = {apt._norm_name(k): v for k, v in
          (_load(os.path.join(DATA_DIR, "nhl_player_gamelogs.json")).get("by_name") or {}).items()}
    changed = []
    now = dt.datetime.now().isoformat(timespec="seconds")
    for p in picks:
        if str(p.get("sport")).upper() != "NHL" or not p.get("settled") or p.get("voided"):
            continue
        if p.get("regraded"):
            continue
        q = dict(p)
        new = apt._grade_nhl_pick(q, by, games)
        if new is None or new == p.get("result"):
            continue
        dec = apt._american_to_decimal(p.get("fair_american")) or 1.91
        new_pay = round(dec - 1, 4) if new == "won" else (-1.0 if new == "lost" else 0.0)
        p["regraded"] = {"from_result": p.get("result"), "from_payout": p.get("payout_units"),
                         "at": now,
                         "reason": ("2026-10-22 NHL grader fix: favourite puck lines were graded "
                                    "as +1.5, and skater props could be graded on an adjacent "
                                    "night's game; re-graded against the box score for the "
                                    "pick's own date")}
        p["result"] = new
        p["payout_units"] = new_pay
        if q.get("outcome"):
            p["outcome"] = q["outcome"]
        changed.append({"date": p.get("date"), "pick": p.get("player_or_matchup"),
                        "market": p.get("market"), "from": p["regraded"]["from_result"],
                        "to": new})
    if changed:
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump(led, f, indent=2)
    return {"n_regraded": len(changed),
            "won_to_lost": sum(1 for c in changed if c["from"] == "won" and c["to"] == "lost"),
            "lost_to_won": sum(1 for c in changed if c["from"] == "lost" and c["to"] == "won"),
            "picks": changed}


def run(force: bool = False) -> Dict[str, Any]:
    prev = _load(MARKER) if os.path.exists(MARKER) else {}
    if prev and not force and int(prev.get("version") or 1) >= BACKFILL_VERSION:
        print(f"[outage-backfill] v{prev.get('version') or 1} already ran {prev.get('ran_at')} -- skipping")
        return prev
    history_passes = list(prev.pop("previous_passes", []) or []) + ([prev] if prev else [])

    led = _load(LEDGER)
    before = led.get("picks") or []
    voids = _outage_voids(before)
    if not voids:
        payload = {"ran_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "version": BACKFILL_VERSION, "previous_passes": history_passes,
                   "n_outage_voids_before": 0, "note": "nothing to backfill"}
        with open(MARKER, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return payload

    oldest = min(str(p.get("date"))[:10] for p in voids)
    days_back = (dt.date.today() - dt.date.fromisoformat(oldest)).days + 2
    print(f"[outage-backfill] {len(voids)} outage-voided picks, oldest {oldest} "
          f"-> outcome lookback {days_back} days")
    feeds: Dict[str, Any] = {}

    # 1. Box scores (player stat lines + finals) for the basketball/football/
    #    hockey graders.
    import espn_box_logs as ebl
    for key, cfg in (("wnba", ebl.CFG_WNBA), ("nba", ebl.CFG_NBA),
                     ("nfl", ebl.CFG_NFL), ("nhl", ebl.CFG_NHL)):
        try:
            r = ebl.run(cfg, days_back=days_back)
            feeds[f"box_{key}"] = r.get("n_games")
        except Exception as e:
            feeds[f"box_{key}"] = f"ERROR {e!r}"

    # 1b. NFL DFS receipts: rescore scorer-v1 slates while the long box window
    #     is loaded (v3, 2026-10-23 -- see nfl_dfs_receipts._rescore_pass).
    try:
        import nfl_dfs_receipts as ndr
        rr = ndr.run()
        feeds["nfl_dfs_receipts"] = {"rescored": rr.get("n_slates_rescored"),
                                     "retracted": rr.get("n_slates_retracted"),
                                     "cumulative": rr.get("cumulative")}
    except Exception as e:
        feeds["nfl_dfs_receipts"] = f"ERROR {e!r}"

    # 2. Event results (golf, tennis, UFC, F1, soccer).
    import espn_event_results as eer
    for key, fn in (("golf", eer.fetch_golf), ("tennis", eer.fetch_tennis),
                    ("ufc", eer.fetch_ufc), ("f1", eer.fetch_f1),
                    ("soccer", eer.fetch_soccer)):
        try:
            r = fn(days_back=days_back)
            feeds[f"events_{key}"] = (r.get("n_tournaments") or r.get("n_matches")
                                      or r.get("n_fights") or r.get("n_events"))
        except Exception as e:
            feeds[f"events_{key}"] = f"ERROR {e!r}"

    # 3. Game finals (game-line settlement) with the long window.
    import historical_games as hg
    for sport_key, espn_path, _days in hg.SPORTS:
        try:
            data = hg.fetch_sport_history(sport_key, espn_path, days_back)
            with open(os.path.join(DATA_DIR, f"historical_{sport_key}.json"), "w") as f:
                json.dump({"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                           **data}, f, indent=2)
            feeds[f"finals_{sport_key}"] = data.get("n_games")
        except Exception as e:
            feeds[f"finals_{sport_key}"] = f"ERROR {e!r}"

    # 4. MLB player gamelogs: the fetch universe is "pending ledger players",
    #    which excludes VOIDED picks -- so the outage-voided props' players would
    #    never be fetched. Add them for this one run.
    import player_gamelogs as pg
    _orig = pg._pending_ledger_players
    extra = []
    seen = set()
    for p in voids:
        if str(p.get("sport") or "").upper() not in ("MLB", "MLB-PP"):
            continue
        nm = str(p.get("player_or_matchup") or "").strip()
        if not nm or "@" in nm or nm.lower() in seen:
            continue
        seen.add(nm.lower())
        kind = "pitcher" if "pitcher" in str(p.get("market") or "").lower() else "batter"
        extra.append({"name": nm, "kind": kind})
    pg._pending_ledger_players = lambda: _orig() + extra
    try:
        r = pg.run()
        feeds["mlb_gamelogs"] = r.get("n_players")
    except Exception as e:
        feeds["mlb_gamelogs"] = f"ERROR {e!r}"
    finally:
        pg._pending_ledger_players = _orig

    # 5. Correct NHL picks the old grader settled against the wrong market or
    #    the wrong night (needs the long-window NHL box data fetched above).
    nhl_fix = _regrade_nhl_settled()
    print(f"[outage-backfill] NHL regrade: {nhl_fix['n_regraded']} corrected "
          f"(won->lost {nhl_fix['won_to_lost']}, lost->won {nhl_fix['lost_to_won']})")

    # 6. The normal ledger build: settles what now has an outcome, then
    #    reconciles the stale voids away.
    import all_picks_tracker as apt
    apt.run()

    after = _load(LEDGER).get("picks") or []
    by_id = {p.get("pick_id"): p for p in after}
    recovered: Dict[str, Counter] = defaultdict(Counter)
    for v in voids:
        a = by_id.get(v.get("pick_id"))
        sp = str(v.get("sport")).upper()
        if a and a.get("settled") and not a.get("voided"):
            recovered[sp][a.get("result") or "?"] += 1
        elif a and str(a.get("voided_reason") or "").startswith("preseason"):
            recovered[sp]["preseason_void"] += 1   # retired by the window rule, not missing data
        else:
            recovered[sp]["still_void"] += 1
    payload = {
        "ran_at": dt.datetime.now().isoformat(timespec="seconds"),
        "version": BACKFILL_VERSION,
        "previous_passes": history_passes,
        "outage": "2026-09-22 -> 2026-10-22 (daily-pipeline cascade)",
        "n_outage_voids_before": len(voids),
        "oldest_pick": oldest,
        "lookback_days": days_back,
        "feeds": feeds,
        "by_sport": {k: dict(v) for k, v in recovered.items()},
        "n_recovered": sum(v[r] for v in recovered.values() for r in v
                           if r not in ("still_void", "preseason_void")),
        "nhl_regrade": nhl_fix,
        "note": ("Outcome feeds re-run once with a long lookback so picks voided only "
                 "because the feeds were dark could be graded on their real results. "
                 "Grading used the normal settlement code; nothing was inferred. Picks "
                 "whose outcome data no longer exists stay voided."),
    }
    with open(MARKER, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    import sys
    p = run(force="--force" in sys.argv)
    print(f"[outage-backfill] recovered {p.get('n_recovered', 0)} of "
          f"{p.get('n_outage_voids_before', 0)} outage-voided picks")
    for sp, c in sorted((p.get("by_sport") or {}).items()):
        print(f"    {sp:8s} {c}")
