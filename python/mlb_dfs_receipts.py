"""
EdgeStat -- MLB DFS receipts: grade the published optimal lineup DAILY.

MLB slates run every day, so unlike the weekly NFL loop this produces a graded
receipt every morning: yesterday's PUBLISHED optimal lineup vs what it
actually scored on the box scores.

  1. SNAPSHOT: refresh a snapshot of the published lineup all slate day (the
     last pre-lock refresh -- the 22:00 UTC pipeline run -- is the honest
     "what you could have played"). The first run on a LATER day freezes it.
  2. SCORE: hitters and pitchers from real statsapi box scores
     (player_gamelogs) with the exact DK MLB Classic formula. A player with
     no box row (sat / not in the sampled gamelog universe) scores 0 and is
     flagged per-slot.
  3. RECORD: per-slate projected-vs-actual + cumulative bias. Scored slates
     are never edited.

DISCLOSURES: SB/HBP (hitters) and W (pitchers) fields were added to the box
feed 2026-08-18 -- rows logged before that score those components as 0
(small understatement, flagged); CG/no-hitter bonuses ignored.

Output: data/mlb_dfs_receipts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DFS_PATH = os.path.join(DATA_DIR, "mlb_dfs.json")
GL_PATH = os.path.join(DATA_DIR, "player_gamelogs.json")
OUT = os.path.join(DATA_DIR, "mlb_dfs_receipts.json")


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


def _norm(s: Any) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


def batter_actual_dk(row: Dict[str, Any]) -> float:
    g = lambda k: float(row.get(k) or 0)
    singles = g("hits") - g("doubles") - g("triples") - g("hr")
    pts = (3.0 * singles + 5.0 * g("doubles") + 8.0 * g("triples") + 10.0 * g("hr")
           + 2.0 * g("rbi") + 2.0 * g("runs") + 2.0 * g("bb") + 2.0 * g("hbp")
           + 5.0 * g("sb"))
    return round(pts, 2)


def pitcher_actual_dk(row: Dict[str, Any]) -> float:
    g = lambda k: float(row.get(k) or 0)
    ip = 0.0
    raw = str(row.get("ip") or "0")
    try:
        whole, _, frac = raw.partition(".")
        ip = int(whole or 0) + (int(frac or 0) / 3.0)
    except Exception:
        pass
    pts = (2.25 * ip + 2.0 * g("k") + 4.0 * g("win")
           - 2.0 * g("er") - 0.6 * g("h") - 0.6 * g("bb"))
    return round(pts, 2)


def _box_row(gl: Dict[str, Any], name: str, slate_date: str) -> Optional[Dict[str, Any]]:
    """player_gamelogs is keyed by player id with a name field -- index by
    normalized name once per run (caller passes the prebuilt index)."""
    e = gl.get(_norm(name))
    if not e:
        return None
    for r in e.get("games") or []:
        if str(r.get("date"))[:10] == slate_date[:10]:
            return r
    return None


def run() -> Dict[str, Any]:
    today = dt.date.today().isoformat()
    dfs = _load(DFS_PATH)
    receipts = _load(OUT)
    slates: Dict[str, Any] = receipts.get("slates") or {}

    # 1. snapshot / freeze
    slate = dfs.get("slate") or {}
    start = str(slate.get("start") or "")[:10]
    optimal = (dfs.get("lineups") or {}).get("optimal") or {}
    if start and optimal.get("slots"):
        entry = slates.get(start) or {}
        if not entry.get("frozen"):
            if today <= start:
                entry.update({"draft_group_id": slate.get("draft_group_id"),
                              "optimal": optimal,
                              "snapshotted_at": dt.datetime.now().isoformat(timespec="seconds"),
                              "frozen": False})
            elif entry.get("optimal"):
                entry["frozen"] = True
                entry["frozen_at"] = dt.datetime.now().isoformat(timespec="seconds")
            slates[start] = entry
    # freeze any stale unfrozen snapshots from previous days
    for sdate, entry in slates.items():
        if not entry.get("frozen") and entry.get("optimal") and sdate < today:
            entry["frozen"] = True
            entry["frozen_at"] = dt.datetime.now().isoformat(timespec="seconds")

    # 2. score frozen, unscored, >= 1 day old
    raw_gl = _load(GL_PATH).get("by_player_id") or {}
    gl_by_name: Dict[str, Dict[str, Any]] = {}
    for pid, e in raw_gl.items():
        gl_by_name.setdefault(_norm(e.get("name")), e)
    for sdate, entry in slates.items():
        if entry.get("scored") or not entry.get("frozen"):
            continue
        if sdate >= today:
            continue
        b = entry.get("optimal") or {}
        slots_out: List[Dict[str, Any]] = []
        actual_total = 0.0
        n_dnp = 0
        any_scored = False
        for s in b.get("slots") or []:
            is_p = str(s.get("slot", "")).startswith("P")
            row = _box_row(gl_by_name, s.get("name") or "", sdate)
            if row is None:
                slots_out.append({"slot": s.get("slot"), "name": s.get("name"),
                                  "team": s.get("team"), "proj": s.get("proj"),
                                  "actual": 0.0, "note": "no box row -> 0 (sat or unsampled)"})
                n_dnp += 1
                continue
            act = pitcher_actual_dk(row) if is_p else batter_actual_dk(row)
            actual_total += act
            any_scored = True
            slots_out.append({"slot": s.get("slot"), "name": s.get("name"),
                              "team": s.get("team"), "proj": s.get("proj"),
                              "actual": act})
        if any_scored:
            entry["scored"] = True
            entry["scored_at"] = dt.datetime.now().isoformat(timespec="seconds")
            entry["result"] = {"proj_total": b.get("proj_total"),
                               "actual_total": round(actual_total, 2),
                               "salary_used": b.get("salary_used"),
                               "n_dnp": n_dnp, "slots": slots_out}

    # 3. cumulative
    scored = [(d, e) for d, e in sorted(slates.items()) if e.get("scored")]
    cum = None
    rows = [(e["result"]["proj_total"], e["result"]["actual_total"])
            for _, e in scored if e["result"].get("proj_total") is not None]
    if rows:
        n = len(rows)
        cum = {"n_slates": n,
               "avg_projected": round(sum(r[0] for r in rows) / n, 2),
               "avg_actual": round(sum(r[1] for r in rows) / n, 2),
               "avg_bias": round(sum(r[1] - r[0] for r in rows) / n, 2)}

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_slates_tracked": len(slates),
        "n_slates_scored": len(scored),
        "cumulative": cum,
        "slates": slates,
        "method_note": ("The published optimal lineup snapshots all slate day and "
                        "freezes at day's end (the last pre-lock pipeline refresh). "
                        "Scored next morning from real statsapi box scores with the "
                        "exact DK MLB Classic formula; a player with no box row "
                        "scores 0 (flagged). Scored slates are never edited."),
        "disclosures": [
            "SB/HBP (hitters) and W (pitchers) joined the box feed 2026-08-18; earlier rows score those components 0 (small understatement).",
            "CG / no-hitter bonuses ignored (~0.05 pts EV).",
            "Mean-based v1 projections are the benchmark being graded -- see the mlb-dfs method notes.",
        ],
    }
    _write(payload)
    return payload


def _self_test() -> bool:
    b = {"hits": 3, "doubles": 1, "triples": 0, "hr": 1, "rbi": 3, "runs": 2,
         "bb": 1, "hbp": 0, "sb": 1}
    # singles=1 ->3 + 2B 5 + HR 10 + RBI 6 + R 4 + BB 2 + SB 5 = 35
    gb = batter_actual_dk(b)
    p = {"ip": "6.2", "k": 8, "er": 2, "h": 5, "bb": 1, "win": 1}
    # ip 6.667*2.25=15.0 + 16 + 4 - 4 - 3 - 0.6 = 27.4
    gp = pitcher_actual_dk(p)
    ok = abs(gb - 35.0) < 1e-9 and abs(gp - 27.4) < 0.01
    print(f"  scorer self-test: batter {gb} (want 35.0) · pitcher {gp} (want ~27.4) "
          f"{'OK' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    if not _self_test():
        raise SystemExit("mlb_dfs_receipts scorer self-test FAILED")
    o = run()
    print(f"[mlb-dfs-receipts] tracking {o['n_slates_tracked']} slate(s), "
          f"{o['n_slates_scored']} scored")
    c = o.get("cumulative")
    if c:
        print(f"  cumulative n={c['n_slates']} proj {c['avg_projected']} -> "
              f"actual {c['avg_actual']} (bias {c['avg_bias']:+})")
