"""
EdgeStat -- NFL DFS receipts: grade the PUBLISHED lineups against real box scores.

The DFS desk publishes three lineups per slate (optimal / ceiling / cash). This
module makes those claims accountable, the same way the pick ledger makes the
betting record accountable:

  1. SNAPSHOT: while a slate is upcoming, keep refreshing a snapshot of the
     currently-published lineups (injuries/salaries reprice all week -- the
     honest benchmark is the LAST version you could actually have played).
     The moment the slate date arrives, the snapshot FREEZES -- published is
     published, exactly like the Alpha pick locks.
  2. SCORE: once the slate is >= 1 day old, score every skill slot from the
     real box scores (nfl_player_gamelogs, fed by espn_box_logs) using the
     same DK Classic formula as the projections (full PPR, 4pt pass TD,
     100/300-yard bonuses). DST is scored PARTIALLY (points-allowed tier only,
     from the schedule finals) and labeled as such -- sacks/turnovers have no
     free feed; the partial number understates real DST scores by ~4-6.
  3. RECORD: per-slate projected-vs-actual per build + a cumulative bias
     table. Published on nfl-dfs.html ("Receipts"). Never edited after
     scoring.

DISCLOSURES (also in the payload): fumbles/2-pt conversions absent from the
gamelog feed (~0.1-0.3 pts/slot); a player with NO gamelog row on slate day
scores 0 (DNP/inactive -- exactly what your DFS entry would have scored);
DST partial as above.

Output: data/nfl_dfs_receipts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import nfl_baselines as nb

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DFS_PATH = os.path.join(DATA_DIR, "nfl_dfs.json")
GL_PATH = os.path.join(DATA_DIR, "nfl_player_gamelogs.json")
STATE_PATH = os.path.join(DATA_DIR, "nfl_state.json")
OUT = os.path.join(DATA_DIR, "nfl_dfs_receipts.json")

# DK DST points-allowed tiers (whole-tier, not interpolated -- actual PA is known).
def _dst_pa_points(pa: float) -> float:
    if pa == 0: return 10.0
    if pa <= 6: return 7.0
    if pa <= 13: return 4.0
    if pa <= 20: return 1.0
    if pa <= 27: return 0.0
    if pa <= 34: return -1.0
    return -4.0


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(obj: Any) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def actual_dk_points(row: Dict[str, Any]) -> float:
    """DK Classic points from one real box-score gamelog row (skill player)."""
    g = lambda k: float(row.get(k) or 0)
    fp = (0.04 * g("pass_yds") + 4.0 * g("pass_td") - 1.0 * g("pass_int")
          + (3.0 if g("pass_yds") >= 300 else 0.0)
          + 0.10 * g("rush_yds") + 6.0 * g("rush_td")
          + (3.0 if g("rush_yds") >= 100 else 0.0)
          + 1.00 * g("rec") + 0.10 * g("rec_yds") + 6.0 * g("rec_td")
          + (3.0 if g("rec_yds") >= 100 else 0.0))
    return round(fp, 2)


def _gamelog_row(gl_by_name: Dict[str, Any], player: str, slate_date: str,
                 window_days: int = 3) -> Optional[Dict[str, Any]]:
    """The player's box-score row for the slate (a Sun main slate's games all
    fall on slate_date, but Thu/Mon slates and date drift get a small window)."""
    e = gl_by_name.get(nb.norm_name(player))
    rows = e if isinstance(e, list) else ((e or {}).get("games") or [])
    try:
        d0 = dt.date.fromisoformat(slate_date[:10])
    except Exception:
        return None
    best = None
    for r in rows:
        try:
            d = dt.date.fromisoformat(str(r.get("date"))[:10])
        except Exception:
            continue
        if 0 <= (d - d0).days < window_days:
            if best is None or r.get("date") < best.get("date"):
                best = r
    return best


def _dst_actual(team: str, slate_date: str) -> Optional[float]:
    """Partial DST score: points-allowed tier from the schedule finals."""
    state = _load(STATE_PATH)
    for g in state.get("games") or []:
        gd = str(g.get("date") or "")[:10]
        if gd != slate_date[:10]:
            continue
        mu = str(g.get("matchup") or "")
        # matchup carries full names; match by abbrev via the game's abbrev
        # fields when present, else skip (historical file rotates fast).
        ha, aa = str(g.get("home_abbrev") or "").upper(), str(g.get("away_abbrev") or "").upper()
        if team not in (ha, aa):
            continue
        hs, as_ = g.get("home_score"), g.get("away_score")
        if hs is None or as_ is None:
            return None
        pa = float(as_ if team == ha else hs)
        return _dst_pa_points(pa)
    return None


def run() -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    dfs = _load(DFS_PATH)
    receipts = _load(OUT)
    slates: Dict[str, Any] = receipts.get("slates") or {}

    # 1. SNAPSHOT / FREEZE the currently-published slate.
    slate = dfs.get("slate") or {}
    start = str(slate.get("start") or "")[:10]
    lineups = dfs.get("lineups") or {}
    if start and lineups:
        entry = slates.get(start) or {}
        if not entry.get("frozen"):
            if today < start:
                entry.update({
                    "draft_group_id": slate.get("draft_group_id"),
                    "lineups": lineups,
                    "snapshotted_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "frozen": False,
                })
            elif entry.get("lineups"):
                # slate day arrived -- freeze the last pre-kickoff snapshot
                entry["frozen"] = True
                entry["frozen_at"] = dt.datetime.now().isoformat(timespec="seconds")
            else:
                # first sight ON slate day (no earlier snapshot): freeze current
                entry.update({
                    "draft_group_id": slate.get("draft_group_id"),
                    "lineups": lineups,
                    "snapshotted_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "frozen": True,
                    "frozen_at": dt.datetime.now().isoformat(timespec="seconds"),
                })
            slates[start] = entry

    # 2. SCORE frozen slates that are >= 1 day old and unscored.
    gl_by_name = _load(GL_PATH).get("by_name") or {}
    for sdate, entry in slates.items():
        if entry.get("scored") or not entry.get("frozen"):
            continue
        try:
            age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(sdate)).days
        except Exception:
            continue
        if age < 1:
            continue
        builds_out: Dict[str, Any] = {}
        any_scored = False
        for bname, b in (entry.get("lineups") or {}).items():
            slots_out: List[Dict[str, Any]] = []
            actual_total = 0.0
            n_dnp = 0
            for s in b.get("slots") or []:
                if s.get("pos") == "DST":
                    act = _dst_actual(str(s.get("team") or "").upper(), sdate)
                    slots_out.append({"slot": s.get("slot"), "name": s.get("name"),
                                      "team": s.get("team"), "proj": s.get("proj"),
                                      "actual": act,
                                      "note": "partial: PA tier only" if act is not None
                                              else "unscored (no final found)"})
                    if act is not None:
                        actual_total += act
                        any_scored = True
                    continue
                row = _gamelog_row(gl_by_name, s.get("name") or "", sdate)
                if row is None:
                    slots_out.append({"slot": s.get("slot"), "name": s.get("name"),
                                      "team": s.get("team"), "proj": s.get("proj"),
                                      "actual": 0.0, "note": "DNP/no box row -> 0"})
                    n_dnp += 1
                    continue
                act = actual_dk_points(row)
                actual_total += act
                any_scored = True
                slots_out.append({"slot": s.get("slot"), "name": s.get("name"),
                                  "team": s.get("team"), "proj": s.get("proj"),
                                  "actual": act})
            builds_out[bname] = {
                "proj_total": b.get("proj_total"),
                "actual_total": round(actual_total, 2),
                "salary_used": b.get("salary_used"),
                "n_dnp": n_dnp,
                "slots": slots_out,
            }
        if any_scored:
            entry["scored"] = True
            entry["scored_at"] = dt.datetime.now().isoformat(timespec="seconds")
            entry["results"] = builds_out

    # 3. CUMULATIVE record across scored slates.
    scored = [(d, e) for d, e in sorted(slates.items()) if e.get("scored")]
    cum: Dict[str, Any] = {}
    for bname in ("optimal", "ceiling", "cash"):
        rows = [(e["results"][bname]["proj_total"], e["results"][bname]["actual_total"])
                for _, e in scored if bname in (e.get("results") or {})
                and e["results"][bname].get("proj_total") is not None]
        if rows:
            n = len(rows)
            cum[bname] = {
                "n_slates": n,
                "avg_projected": round(sum(r[0] for r in rows) / n, 2),
                "avg_actual": round(sum(r[1] for r in rows) / n, 2),
                "avg_bias": round(sum(r[1] - r[0] for r in rows) / n, 2),
            }

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_slates_tracked": len(slates),
        "n_slates_scored": len(scored),
        "cumulative": cum,
        "slates": slates,
        "method_note": ("Published lineups snapshot all week and FREEZE at the slate "
                        "date (the last version you could actually have played). "
                        "Skill slots score from real box scores with the same DK "
                        "formula as the projections; a DNP scores 0 -- exactly what "
                        "your entry would have scored. DST is PARTIAL (points-allowed "
                        "tier only; no free sacks/turnovers feed) and understates real "
                        "DST scores by roughly 4-6 points. Scored slates are never "
                        "edited."),
        "disclosures": [
            "Fumbles lost / 2-pt conversions are absent from the box feed (~0.1-0.3 pts/slot).",
            "DST actuals are partial (PA tier only) and labeled per-slot.",
            "A projected player with no box row on slate day scores 0 (DNP) -- disclosed per-slot.",
        ],
    }
    receipts_out = payload
    _write(receipts_out)
    return receipts_out


def _self_test() -> bool:
    """Scorer vs a hand-computed example."""
    row = {"pass_yds": 305, "pass_td": 2, "pass_int": 1, "rush_yds": 42,
           "rush_td": 1, "rec": 0, "rec_yds": 0, "rec_td": 0}
    # 305*.04=12.2 +8 -1 +3(300 bonus) +4.2 +6 = 32.4
    got = actual_dk_points(row)
    ok = abs(got - 32.4) < 1e-9
    row2 = {"rec": 8, "rec_yds": 112, "rec_td": 1, "rush_yds": 4}
    # 8 + 11.2 + 6 + 3(100 bonus) + 0.4 = 28.6
    got2 = actual_dk_points(row2)
    ok2 = abs(got2 - 28.6) < 1e-9
    print(f"  scorer self-test: QB {got} (want 32.4) {'OK' if ok else 'FAIL'} · "
          f"WR {got2} (want 28.6) {'OK' if ok2 else 'FAIL'}")
    return ok and ok2


if __name__ == "__main__":
    if not _self_test():
        raise SystemExit("nfl_dfs_receipts scorer self-test FAILED")
    o = run()
    print(f"[dfs-receipts] tracking {o['n_slates_tracked']} slate(s), "
          f"{o['n_slates_scored']} scored")
    for b, c in (o.get("cumulative") or {}).items():
        print(f"  {b:8s} n={c['n_slates']} proj {c['avg_projected']} -> "
              f"actual {c['avg_actual']} (bias {c['avg_bias']:+})")
