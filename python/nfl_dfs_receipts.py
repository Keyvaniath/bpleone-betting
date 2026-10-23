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
import nfl_dfs_calibration as ndc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DFS_PATH = os.path.join(DATA_DIR, "nfl_dfs.json")
GL_PATH = os.path.join(DATA_DIR, "nfl_player_gamelogs.json")
STATE_PATH = os.path.join(DATA_DIR, "nfl_state.json")
HIST_PATH = os.path.join(DATA_DIR, "nfl_historical.json")
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


SLATE_SPAN_DAYS = 6   # DK's weekly Main slate runs Thu night -> Mon night
BOX_LOG_DAYS = 8      # espn_box_logs nfl days_back -- older box rows are gone


def _gamelog_row(gl_by_name: Dict[str, Any], player: str, slate_date: str,
                 window_days: int = SLATE_SPAN_DAYS) -> Optional[Dict[str, Any]]:
    """The player's box-score row for the slate. THE MULTI-DAY SLATE (2026-09-08):
    DraftKings dates its weekly Main group by its FIRST kickoff -- Week 1's
    16-game slate is stamped 09-09 (Thursday) though 13 of its games play
    Sunday 09-13 and one Monday. A 3-day window would have missed every Sunday
    and Monday player. The window now spans the whole slate."""
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


_DK_TO_ESPN = {"WAS": "WSH", "JAC": "JAX", "LA": "LAR"}


def _dst_actual(team: str, slate_date: str) -> Optional[float]:
    """Partial DST score: points-allowed tier from the schedule finals.

    FINALS SOURCE (2026-10-23): this read only nfl_state.json, which holds the
    CURRENT week -- by scoring day (6 days after the slate opens) the slate's
    games had rotated out, so every DST slot said "unscored (no final found)"
    while its projection still counted in proj_total (~6 pts of phantom
    bias per slate). nfl_historical.json (dated finals) is read first now."""
    try:
        d0 = dt.date.fromisoformat(slate_date[:10])
    except Exception:
        return None
    t = _DK_TO_ESPN.get(team, team)
    games = (list(_load(HIST_PATH).get("games") or [])
             + list(_load(STATE_PATH).get("games") or []))
    for g in games:
        gd = str(g.get("date") or "")[:10]
        try:
            off = (dt.date.fromisoformat(gd) - d0).days
        except Exception:
            continue
        if not (0 <= off < SLATE_SPAN_DAYS):     # same Thu->Mon window as players
            continue
        ha, aa = str(g.get("home_abbrev") or "").upper(), str(g.get("away_abbrev") or "").upper()
        if t not in (ha, aa):
            continue
        hs, as_ = g.get("home_score"), g.get("away_score")
        if hs is None or as_ is None:
            continue
        pa = float(as_ if t == ha else hs)
        return _dst_pa_points(pa)
    return None


def _score_lineups(entry: Dict[str, Any], sdate: str,
                   gl_by_name: Dict[str, Any]):
    """Score every build of one frozen slate -> (builds_out, any_scored)."""
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
        # Like-for-like bias: a slot whose actual is unknown (DST with no
        # final) must not contribute its projection either.
        proj_scored = sum(float(x.get("proj") or 0) for x in slots_out if x.get("actual") is not None)
        builds_out[bname] = {
            "proj_total": b.get("proj_total"),
            "proj_scored": round(proj_scored, 2),
            "proj_basis": b.get("proj_basis") or "model_raw",
            "actual_total": round(actual_total, 2),
            "salary_used": b.get("salary_used"),
            "n_dnp": n_dnp,
            "slots": slots_out,
        }
    return builds_out, any_scored


def _norm_index(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Box-log rows keyed by nb.norm_name; on a collision keep the fuller log."""
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        nk = nb.norm_name(k)
        cur = out.get(nk)
        n_new = len(v if isinstance(v, list) else (v or {}).get("games") or [])
        n_cur = len(cur if isinstance(cur, list) else (cur or {}).get("games") or []) if cur else -1
        if n_new > n_cur:
            out[nk] = v
    return out


SCORER_VERSION = 2


LONG_WINDOW_DAYS = 30   # a box index this wide = the outage backfill's long fetch


def _rescore_pass(slates: Dict[str, Any], gl_by_name: Dict[str, Any],
                  box_from: Optional[str], box_to: Optional[str] = None) -> None:
    """One disclosed correction (2026-10-23) for slates scored by scorer v1,
    whose name lookup zeroed every punctuated/suffixed player. Where the box
    feed still covers the slate, it is RESCORED with the old totals kept under
    `rescored.previous`; where the rows have aged out it is RETRACTED (kept for
    audit, excluded from the cumulative) -- a receipt known to be wrong is not
    left standing, and it is never guessed."""
    now = dt.datetime.now().isoformat(timespec="seconds")
    for sdate, entry in slates.items():
        if not entry.get("scored") or entry.get("retracted"):
            continue
        if int(entry.get("scorer_version") or 1) >= SCORER_VERSION:
            continue
        prev = {b: {"actual_total": r.get("actual_total"), "n_dnp": r.get("n_dnp")}
                for b, r in (entry.get("results") or {}).items()}
        # v1 was exact for plain names (normalized == raw key); only a DNP on a
        # punctuated/suffixed name can be wrong. Untouched slates are verified.
        touched = any(str(x.get("note") or "").startswith("DNP")
                      and nb.norm_name(x.get("name")) != str(x.get("name") or "").lower().strip()
                      for r in (entry.get("results") or {}).values() for x in (r.get("slots") or []))
        if not touched:
            entry["scorer_version"] = SCORER_VERSION
            continue
        if box_from and box_from <= sdate:
            builds_out, any_scored = _score_lineups(entry, sdate, gl_by_name)
            if any_scored:
                entry["results"] = builds_out
                entry["scorer_version"] = SCORER_VERSION
                entry["rescored"] = {"at": now, "previous": prev,
                                     "reason": ("scorer v1 looked players up by normalized name against "
                                                "raw box keys, so punctuated/suffixed names (Amon-Ra St. "
                                                "Brown, De'Von Achane, Marvin Harrison Jr.) scored 0")}
                continue
        # Retract only when a LONG box window is loaded and still can't reach
        # the slate (the rows are gone for good). On an ordinary run the feed
        # holds ~8 days, so an older slate just waits for the backfill's pass.
        try:
            span = (dt.date.fromisoformat(box_to) - dt.date.fromisoformat(box_from)).days
        except Exception:
            span = 0
        if span < LONG_WINDOW_DAYS:
            continue
        entry["retracted"] = True
        entry["retracted_at"] = now
        entry["retracted_reason"] = ("scored by scorer v1, which zeroed punctuated/suffixed player "
                                     "names; the box scores have aged out of the feed, so it cannot "
                                     "be rescored -- retracted rather than left wrong")
        entry["scorer_version"] = SCORER_VERSION



def run() -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    dfs = _load(DFS_PATH)
    receipts = _load(OUT)
    slates: Dict[str, Any] = receipts.get("slates") or {}

    # 0. Full projected pool (every player, not just the 8 seated) -> the
    #    calibration's training data (nfl_dfs_calibration).
    ndc.snapshot_pool(dfs, today)

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

    # 1b. FREEZE STALE SNAPSHOTS (2026-10-22). The freeze above only touches
    # the CURRENT slate, so a snapshot whose slate date passed while this module
    # wasn't running (the 9/22-10/22 cascade) stayed unfrozen forever and was
    # never even considered for scoring. Any past-dated snapshot freezes as-is:
    # it is still the last version that was published.
    for sdate, entry in slates.items():
        if entry.get("frozen") or not entry.get("lineups"):
            continue
        if sdate < today:
            entry["frozen"] = True
            entry["frozen_at"] = dt.datetime.now().isoformat(timespec="seconds")
            entry["frozen_note"] = "frozen late: slate date passed while the module was not running"

    # 2. SCORE frozen slates that are >= 1 day old and unscored.
    # NAME KEYS (2026-10-23): nfl_player_gamelogs keys are RAW box names
    # ("amon-ra st. brown", "marvin harrison jr.", "de'von achane") but the
    # lookup used nb.norm_name(player) -- so every player with punctuation or
    # a suffix scored "DNP -> 0" (one Week-1 lineup lost Achane, Smith-Njigba
    # and Wan'Dale Robinson that way). Index by the normalized name instead.
    gl_by_name = _norm_index(_load(GL_PATH).get("by_name") or {})
    _bd = sorted({str(r.get("date"))[:10] for v in gl_by_name.values()
                  for r in (v if isinstance(v, list) else (v or {}).get("games") or [])
                  if r.get("date")})
    _rescore_pass(slates, gl_by_name, _bd[0] if _bd else None, _bd[-1] if _bd else None)
    for sdate, entry in slates.items():
        if entry.get("scored") or entry.get("unscoreable") or not entry.get("frozen"):
            continue
        try:
            age = (dt.date.fromisoformat(today) - dt.date.fromisoformat(sdate)).days
        except Exception:
            continue
        # Wait for the WHOLE slate to play. Scoring at age>=1 would have graded
        # Week 1 on Friday morning: the Thursday players score, `any_scored`
        # flips, every Sunday/Monday starter is written down as "DNP -> 0", and
        # the slate is frozen as scored forever -- a corrupted receipt by
        # construction. The slate is only complete SLATE_SPAN_DAYS after its
        # first kickoff (Thu -> Mon), so that is the earliest honest scoring day.
        if age < SLATE_SPAN_DAYS:
            continue
        builds_out, any_scored = _score_lineups(entry, sdate, gl_by_name)
        if any_scored:
            entry["scored"] = True
            entry["scored_at"] = dt.datetime.now().isoformat(timespec="seconds")
            entry["results"] = builds_out
            entry["scorer_version"] = SCORER_VERSION
        elif age > SLATE_SPAN_DAYS + BOX_LOG_DAYS:
            # TERMINAL, NOT RETRIED FOREVER (2026-10-22). The box-score feed
            # (espn_box_logs nfl) keeps ~8 days; once a slate's last game is
            # older than that and nothing scored, the box rows are gone for
            # good. Four slates (9/17-9/24) froze during the 30-day pipeline
            # cascade and could never be graded. Disclose them, never guess.
            entry["unscoreable"] = True
            entry["unscoreable_reason"] = (
                "box scores aged out of the ~8-day feed window before this slate "
                "could be graded (the 9/22-10/22 pipeline outage) -- never scored, "
                "never guessed")

    n_pools = ndc.score_pools(gl_by_name, today, SLATE_SPAN_DAYS, nb.norm_name, actual_dk_points)

    # 3. CUMULATIVE record across scored slates.
    scored = [(d, e) for d, e in sorted(slates.items())
              if e.get("scored") and not e.get("retracted")]
    # Per build AND per projection basis (2026-10-23): slates built on the raw
    # model mean ('model_raw') and on the calibrated xfp ('calibrated_v1')
    # answer different questions and are never averaged together. The
    # top-level `cumulative` is the CURRENT basis; `cumulative_by_basis`
    # keeps the old one on the record.
    by_basis: Dict[str, Dict[str, Any]] = {}
    for bname in ("optimal", "ceiling", "cash"):
        groups: Dict[str, List[Any]] = {}
        for _, e in scored:
            r = (e.get("results") or {}).get(bname)
            if not r or r.get("proj_total") is None:
                continue
            proj = r.get("proj_scored")
            if proj is None:      # scored before proj_scored existed: derive it
                sl = r.get("slots") or []
                proj = (sum(float(x.get("proj") or 0) for x in sl if x.get("actual") is not None)
                        if sl else r["proj_total"])
            groups.setdefault(r.get("proj_basis") or "model_raw", []).append((proj, r["actual_total"]))
        for basis, rows in groups.items():
            n = len(rows)
            by_basis.setdefault(basis, {})[bname] = {
                "n_slates": n,
                "avg_projected": round(sum(r[0] for r in rows) / n, 2),
                "avg_actual": round(sum(r[1] for r in rows) / n, 2),
                "avg_bias": round(sum(r[1] - r[0] for r in rows) / n, 2),
            }
    cum: Dict[str, Any] = by_basis.get("calibrated_v1") or by_basis.get("model_raw") or {}

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_slates_tracked": len(slates),
        "n_slates_scored": len(scored),
        "n_slates_retracted": sum(1 for e in slates.values() if e.get("retracted")),
        "n_slates_rescored": sum(1 for e in slates.values() if e.get("rescored")),
        "cumulative": cum,
        "cumulative_basis": "calibrated_v1" if by_basis.get("calibrated_v1") else "model_raw",
        "cumulative_by_basis": by_basis,
        "n_pools_scored_this_run": n_pools,
        "slates": slates,
        "method_note": ("Published lineups snapshot all week and FREEZE at the slate "
                        "date (the last version you could actually have played). "
                        "Skill slots score from real box scores with the same DK "
                        "formula as the projections; a DNP scores 0 -- exactly what "
                        "your entry would have scored. DST is PARTIAL (points-allowed "
                        "tier only; no free sacks/turnovers feed) and understates real "
                        "DST scores by roughly 4-6 points. Scored slates are never "
                        "edited -- with ONE disclosed exception (2026-10-23): scorer v1 "
                        "zeroed players whose names carry punctuation or a suffix; "
                        "those slates were rescored where box scores survive (old "
                        "totals kept under 'rescored') and retracted where they don't."),
        "disclosures": [
            "Fumbles lost / 2-pt conversions are absent from the box feed (~0.1-0.3 pts/slot).",
            "DST actuals are partial (PA tier only) and labeled per-slot.",
            "A projected player with no box row on slate day scores 0 (DNP) -- disclosed per-slot.",
            "Bias compares like for like: a slot with no actual (DST without a final) is excluded from the projected side too (proj_scored).",
            "From 2026-10-23 lineups are built and graded on the CALIBRATED expectation (proj_basis calibrated_v1); earlier slates were graded on the raw model mean (model_raw) and stay on the record under cumulative_by_basis, never averaged with the new basis.",
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
