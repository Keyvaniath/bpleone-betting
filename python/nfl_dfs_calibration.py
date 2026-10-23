"""
EdgeStat -- NFL DFS calibration: what the lineup optimizer should maximize.

WHY (2026-10-23): published optimal lineups ran ~60 DK points/slate below
their projection. A full-pool backtest (every projected player on the Week
1-3 main slates vs his real box score, n=828, 634 who played) showed the
MODEL IS NOT BIASED ON AVERAGE (+0.2 pts/player) -- the gap is the
OPTIMIZER'S CURSE plus injuries:

  * The optimizer maximizes projection per salary, so it seats exactly the
    players whose projection most exceeds their DK salary -- and those are
    the over-estimates. Players projected at 3.0+ pts/$1k realized 0.83x
    their projection; players under 1.5 pts/$1k realized 1.58x. DK's salary
    is itself a sharp estimate; the model's disagreement with it is only
    partly signal.
  * Q-tagged players sat 25-53% of the time; D-tagged 100% (D was never
    excluded); untagged low-usage players ~25%.

FIX: the optimizer maximizes a CALIBRATED expectation instead of the raw
model mean:

    implied  = ppk[pos] * salary/1000                   (league pts per $1k)
    xfp      = p_play * (implied + w * (proj - implied))

with w (how much of the model's disagreement with salary to trust), ppk and
p_play (by injury tag x projection band) FITTED on scored pools.
Leave-one-week-out on Weeks 1-3: lineup bias -64.6 -> -7.3 pts/slate and
actual skill points 106.0 -> 111.7 (n=3 weeks -- directional, not proof).

SELF-REFITTING: nfl_dfs_receipts snapshots the WHOLE projected pool each
slate (data/nfl_dfs_pool_history.json) and scores every player once the
slate completes; `python nfl_dfs_calibration.py` refits from it (wired
before nfl_dfs in daily-pipeline). Below MIN_ROWS the seeded fit stands.
Output: data/nfl_dfs_calibration.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
POOL_HIST = os.path.join(DATA_DIR, "nfl_dfs_pool_history.json")
OUT = os.path.join(DATA_DIR, "nfl_dfs_calibration.json")

POSITIONS = ("QB", "RB", "WR", "TE")
MIN_ROWS = 300            # played player-weeks before a refit replaces the seed
W_BOUNDS = (0.15, 1.0)    # never ignore the model entirely, never trust it past 1:1
PRIOR_PLAY = 0.85         # p_play shrink target
PRIOR_K = 4               # pseudo-count on p_play cells
MAX_SLATES = 90           # pool-history retention (newest by slate start)

# Seed = the 2026-10-23 fit (Weeks 1-3, reconstructed from git history).
SEED = {
    "w": 0.324,
    "ppk": {"QB": 3.21, "RB": 1.96, "WR": 2.05, "TE": 2.29},
    "p_play": {"none|0": 0.75, "none|1": 0.87, "none|2": 0.95,
               "q|0": 0.51, "q|1": 0.75, "q|2": 0.77},
}


def _load(p: str) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(p: str, obj: Any) -> None:
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    os.replace(tmp, p)


def play_key(status: Any, proj: float) -> str:
    s = str(status or "").upper()
    tag = "q" if s == "Q" else "none"
    band = 0 if proj < 8 else (1 if proj < 14 else 2)
    return f"{tag}|{band}"


def load() -> Dict[str, Any]:
    """The calibration in force (fitted file, else the seed)."""
    c = _load(OUT)
    if c.get("w") is not None and c.get("ppk"):
        return c
    return dict(SEED, source="seed")


def expected(p: Dict[str, Any], cal: Dict[str, Any]) -> Tuple[float, float, float]:
    """(xfp, p_play, implied) for one projected skill player."""
    proj = float(p.get("proj") or 0.0)
    implied = float((cal.get("ppk") or {}).get(p.get("pos"), 2.1)) * float(p.get("salary") or 0) / 1000.0
    w = float(cal.get("w") or 1.0)
    pp = float((cal.get("p_play") or {}).get(play_key(p.get("status"), proj), PRIOR_PLAY))
    return pp * (implied + w * (proj - implied)), pp, implied


# ---------------------------------------------------------------------------
# pool history (written by nfl_dfs_receipts)
# ---------------------------------------------------------------------------

def snapshot_pool(dfs: Dict[str, Any], today: str) -> None:
    """Keep the latest PRE-KICKOFF projected pool for the current slate."""
    slate = dfs.get("slate") or {}
    start = str(slate.get("start") or "")[:10]
    gid = slate.get("draft_group_id")
    if not start or not gid or today >= start:
        return
    hist = _load(POOL_HIST)
    slates = hist.setdefault("slates", {})
    key = str(gid)
    if (slates.get(key) or {}).get("scored"):
        return
    slates[key] = {
        "start": start, "n_games": slate.get("n_games"),
        "snapshotted_at": dfs.get("generated_at"),
        "players": [{k: p.get(k) for k in ("name", "pos", "team", "salary", "status", "proj")}
                    for p in (dfs.get("projections") or []) if p.get("pos") in POSITIONS],
        "scored": False,
    }
    # Bounded: the newest MAX_SLATES pools (~30KB each) -- a season and change.
    if len(slates) > MAX_SLATES:
        for k in sorted(slates, key=lambda k: slates[k].get("start") or "")[:len(slates) - MAX_SLATES]:
            slates.pop(k, None)
    _write(POOL_HIST, hist)


def score_pools(gl_by_name: Dict[str, Any], today: str, span_days: int,
                norm, dk_points) -> int:
    """Score every unscored pool whose slate has fully played. A player with no
    box row in the window is recorded DNP (actual None) -- but only when the
    box index actually reaches the slate, else the pool waits."""
    hist = _load(POOL_HIST)
    slates = hist.get("slates") or {}
    dates = sorted({str(r.get("date"))[:10] for v in gl_by_name.values()
                    for r in (v if isinstance(v, list) else (v or {}).get("games") or [])
                    if r.get("date")})
    if not dates:
        return 0
    n = 0
    for key, s in slates.items():
        if s.get("scored"):
            continue
        start = s.get("start") or ""
        try:
            d0 = dt.date.fromisoformat(start)
            age = (dt.date.fromisoformat(today) - d0).days
        except Exception:
            continue
        if age < span_days or not (dates[0] <= start <= dates[-1]):
            continue
        for p in s.get("players") or []:
            v = gl_by_name.get(norm(p.get("name")))
            rows = v if isinstance(v, list) else ((v or {}).get("games") or [])
            hit = sorted((r for r in rows
                          if 0 <= (dt.date.fromisoformat(str(r.get("date"))[:10]) - d0).days < span_days),
                         key=lambda r: r.get("date"))
            p["played"] = bool(hit)
            p["actual"] = round(dk_points(hit[0]), 2) if hit else None
        s["scored"] = True
        s["scored_at"] = dt.datetime.now().isoformat(timespec="seconds")
        n += 1
    if n:
        _write(POOL_HIST, hist)
    return n


# ---------------------------------------------------------------------------
# fit
# ---------------------------------------------------------------------------

def _rows() -> List[Dict[str, Any]]:
    """One row per (player, NFL week): overlapping draft groups (Thu-Mon full
    slate vs Sunday main) price the same games, so keep the LARGEST slate."""
    slates = (_load(POOL_HIST).get("slates") or {}).values()
    best: Dict[Tuple[str, str], Tuple[int, Dict[str, Any]]] = {}
    for s in slates:
        if not s.get("scored"):
            continue
        try:
            wk = dt.date.fromisoformat(s["start"]).isocalendar()
            week = f"{wk[0]}-{wk[1]:02d}"
        except Exception:
            continue
        size = int(s.get("n_games") or 0)
        for p in s.get("players") or []:
            if p.get("proj") is None or not p.get("salary") or p.get("pos") not in POSITIONS:
                continue
            if str(p.get("status") or "").upper() in ("O", "OUT", "IR", "D"):
                continue                      # never playable -> not part of the fit
            k = (str(p.get("name")), week)
            if k not in best or size > best[k][0]:
                best[k] = (size, dict(p, week=week))
    return [v[1] for v in best.values()]


def fit(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    played = [r for r in rows if r.get("played")]
    ppk = {}
    for pos in POSITIONS:
        xs = [r for r in played if r["pos"] == pos]
        sal = sum(r["salary"] / 1000.0 for r in xs)
        ppk[pos] = round(sum(r["actual"] for r in xs) / sal, 3) if sal else SEED["ppk"][pos]
    num = den = 0.0
    for r in played:
        imp = ppk[r["pos"]] * r["salary"] / 1000.0
        x = r["proj"] - imp
        num += x * (r["actual"] - imp)
        den += x * x
    w = num / den if den else 1.0
    w = round(min(max(w, W_BOUNDS[0]), W_BOUNDS[1]), 3)
    cells: Dict[str, List[int]] = {}
    for r in rows:
        c = cells.setdefault(play_key(r.get("status"), r["proj"]), [0, 0])
        c[0] += 1 if r.get("played") else 0
        c[1] += 1
    p_play = {k: round((c[0] + PRIOR_K * PRIOR_PLAY) / (c[1] + PRIOR_K), 3) for k, c in cells.items()}
    return {"w": w, "ppk": ppk, "p_play": p_play}


def _bias_by_value(rows: List[Dict[str, Any]], cal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Realized/projected by model value band, raw vs calibrated (the evidence)."""
    out = []
    for lo, hi in ((0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 99)):
        xs = [r for r in rows if r.get("played") and lo <= r["proj"] / (r["salary"] / 1000.0) < hi]
        if not xs:
            continue
        act = sum(r["actual"] for r in xs)
        raw = sum(r["proj"] for r in xs)
        cal_ = sum(expected(r, dict(cal, p_play={}))[0] / PRIOR_PLAY for r in xs)  # played-only: no p_play
        out.append({"value_band": f"{lo}-{hi if hi < 99 else '+'}", "n": len(xs),
                    "realized_over_raw": round(act / raw, 3) if raw else None,
                    "realized_over_calibrated": round(act / cal_, 3) if cal_ else None})
    return out


def run() -> Dict[str, Any]:
    rows = _rows()
    n_played = sum(1 for r in rows if r.get("played"))
    weeks = sorted({r["week"] for r in rows})
    if n_played >= MIN_ROWS:
        cal = fit(rows)
        source = "fitted"
    else:
        cal = {k: SEED[k] for k in ("w", "ppk", "p_play")}
        source = "seed"
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source": source,
        **cal,
        "n_player_weeks": len(rows),
        "n_played": n_played,
        "weeks": weeks,
        "evidence_by_value_band": _bias_by_value(rows, cal) if rows else [],
        "formula": "xfp = p_play * (implied + w*(proj - implied)), implied = ppk[pos]*salary/1000",
        "note": ("The optimizer maximizes xfp, not the raw model mean: it seats the players "
                 "whose projection most exceeds salary, and those are the over-estimates "
                 "(the optimizer's curse). w = share of the model's disagreement with DK "
                 "salary that held up on scored pools; p_play = measured play rate by "
                 "injury tag x projection band."),
    }
    _write(OUT, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[nfl-dfs-cal] {p['source']}: w={p['w']} ppk={p['ppk']} "
          f"({p['n_played']} played player-weeks over {len(p['weeks'])} week(s))")
    for b in p["evidence_by_value_band"]:
        print(f"   value {b['value_band']:8s} n={b['n']:4d} realized/raw {b['realized_over_raw']} "
              f"realized/calibrated {b['realized_over_calibrated']}")
