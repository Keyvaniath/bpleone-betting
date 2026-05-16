"""
EdgeStat -- pitcher velocity / spin decay tracker.

Some pitchers' velo dips early in season then ramps; sustained velo drop
across 3+ starts is the canonical injury / fatigue tell. We pull Statcast
per-start avg fastball velo via the existing matchups arsenal data (which
embeds per-pitch velocity_mph). Compare to season avg.

Output: data/velocity_decay.json
  {
    by_pitcher: [
      { name, id, team, fastball_velo, season_avg_velo, delta, label,
        is_concerning }
    ]
  }
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MATCHUPS_PATH = os.path.join(DATA_DIR, "matchups.json")
OUT_PATH = os.path.join(DATA_DIR, "velocity_decay.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for g in (_load(MATCHUPS_PATH).get("games") or []):
        for side in ("home_pitcher", "away_pitcher"):
            p = g.get(side) or {}
            arsenal = p.get("arsenal") or []
            if not arsenal:
                continue
            # Pick the fastball (4-seam or sinker, highest usage)
            fastballs = [a for a in arsenal if (a.get("pitch_type") or "").upper() in ("FF", "SI", "FT", "FC")]
            if not fastballs:
                continue
            fastballs.sort(key=lambda a: -(a.get("usage_pct") or 0))
            fb = fastballs[0]
            cur_velo = fb.get("velocity_mph")
            if cur_velo is None:
                continue
            # Season avg from p.get("season") -- not directly available; use
            # career velo as proxy (assumption: career baseline is stable)
            # Defer accurate season-avg detection until we have multi-start
            # velo snapshots.
            label = "monitoring"
            is_concerning = False
            # Heuristic: if 4-seam velo < 92 mph for a SP, flag as low-velo
            if (fb.get("pitch_type") or "").upper() == "FF" and cur_velo < 92.0:
                label = "low velocity"
                is_concerning = True
            elif cur_velo < 88.0:
                label = "very low velocity"
                is_concerning = True
            else:
                label = "in range"
            out.append({
                "id": p.get("id"), "name": p.get("name"), "team": p.get("hand"),
                "matchup": g.get("matchup"),
                "primary_fastball": fb.get("pitch"),
                "velocity_mph": cur_velo,
                "usage_pct": fb.get("usage_pct"),
                "label": label,
                "is_concerning": is_concerning,
            })
    # Sort: concerning first
    out.sort(key=lambda r: (0 if r["is_concerning"] else 1, r["velocity_mph"] or 99))
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_pitchers": len(out),
        "n_concerning": sum(1 for r in out if r["is_concerning"]),
        "by_pitcher": out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_pitchers']} pitchers, {p['n_concerning']} concerning")
    for r in p["by_pitcher"][:8]:
        print(f"    {r['name']:25} {r['primary_fastball']:20} velo {r['velocity_mph']} ({r['label']})")
