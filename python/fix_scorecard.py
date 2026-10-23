"""
EdgeStat -- the 2026-10-23 fixes, graded on real results as they settle.

Each fix shipped that week was validated on PAST data (walk-forward / prior
seasons). Whether it holds up live is only answerable once new games are
played, so this module grades every fix against the version it replaced,
every pipeline run, and labels each one by sample size:

    pending  -- nothing settled yet under the new version
    early    -- some results, below the bar where a difference means anything
    graded   -- enough results to read the comparison

Nothing here is tuned or acted on automatically; it is the scorecard.
Output: data/fix_scorecard.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "fix_scorecard.json")

# Deploy time of the NBA/NHL live-baseline fix (commit 0f1fe4eae3's first run);
# picks recorded at/after it were priced on the blended baselines.
NBA_NHL_BASELINE_FROM = "2026-10-23T03:30:00"
GRADED_PROPS = 200      # settled props before a line is "graded"
GRADED_SLATES = 4       # scored DFS slates before the DFS fix is "graded"


def _load(name: str) -> Dict[str, Any]:
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _status(n: int, bar: int) -> str:
    return "pending" if n == 0 else ("graded" if n >= bar else "early")


def _record(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """W-L, ROI, and probability quality (Brier, log loss) of settled rows."""
    dec = [p for p in rows if p.get("result") in ("won", "lost")]
    w = sum(1 for p in dec if p["result"] == "won")
    net = round(sum(float(p.get("payout_units") or 0) for p in dec), 2)
    briers, lls = [], []
    for p in dec:
        try:
            pr = float(p.get("p_predicted") if p.get("p_predicted") is not None else p.get("prob"))
        except (TypeError, ValueError):
            continue
        if not 0 < pr < 1:
            continue
        y = 1.0 if p["result"] == "won" else 0.0
        briers.append((pr - y) ** 2)
        pc = min(max(pr, 1e-4), 1 - 1e-4)
        lls.append(-(y * math.log(pc) + (1 - y) * math.log(1 - pc)))
    n = len(dec)
    return {"n": n, "wins": w, "losses": n - w, "net_units": net,
            "roi_pct": round(net / n * 100, 2) if n else None,
            "hit_rate": round(w / n, 4) if n else None,
            "brier": round(sum(briers) / len(briers), 4) if briers else None,
            "log_loss": round(sum(lls) / len(lls), 4) if lls else None}


def _settled(picks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [p for p in picks if p.get("settled") and not p.get("voided")]


def run() -> Dict[str, Any]:
    picks = _load("all_picks_ledger.json").get("picks") or []
    settled = _settled(picks)
    fixes: List[Dict[str, Any]] = []

    # 1. NFL DFS: lineups built on calibrated xFP vs the raw model mean.
    rc = _load("nfl_dfs_receipts.json")
    byb = rc.get("cumulative_by_basis") or {}
    new = (byb.get("calibrated_v1") or {}).get("optimal") or {}
    old = (byb.get("model_raw") or {}).get("optimal") or {}
    n_new = int(new.get("n_slates") or 0)
    fixes.append({
        "fix": "NFL DFS lineups on calibrated xFP (optimizer's curse) + form rule v2",
        "question": "Do published lineups land near their projection, and score more?",
        "expected": "backtest: bias -64.6 -> ~+11 pts/slate, actual 106 -> ~131",
        "status": _status(n_new, GRADED_SLATES),
        "new": new or None, "old": old or None,
        "read": (None if not n_new else
                 f"calibrated: proj {new.get('avg_projected')} -> actual {new.get('avg_actual')} "
                 f"(bias {new.get('avg_bias')}) over {n_new} slate(s) vs raw-model bias "
                 f"{old.get('avg_bias')} over {old.get('n_slates')}"),
    })

    # 2. NFL props: form rule v2 (season-to-date) vs v1 (one-game form).
    import prob_calibration as pc
    v2 = [p for p in settled if pc.model_rule(p) == "form_v2"]
    v1 = [p for p in settled if pc.model_rule(p) == "form_v1"]
    r2, r1 = _record(v2), _record(v1)
    fixes.append({
        "fix": "NFL props priced on season-to-date form (v2) instead of last week's game (v1)",
        "question": "Are v2 props better calibrated (lower Brier) and less negative than v1?",
        "expected": "walk-forward DK-points MAE 6.12 -> 5.76, corr 0.48 -> 0.55",
        "status": _status(r2["n"], GRADED_PROPS),
        "new": r2, "old": r1,
        "read": (None if not r2["n"] else
                 f"v2 {r2['wins']}-{r2['losses']} ROI {r2['roi_pct']}% Brier {r2['brier']} vs "
                 f"v1 {r1['wins']}-{r1['losses']} ROI {r1['roi_pct']}% Brier {r1['brier']}"),
    })

    # 3/4. NBA and NHL props: live blended baselines + current teams vs the
    # hard-coded 2024-25 tables (split by when the pick was priced).
    for sport, exp in (("NBA", "next-10-game RMSE after 1 game: 6.45 -> 3.57 pts (K=5)"),
                       ("NHL", "skater stat RMSE 2-3x lower early season (K=30)")):
        rows = [p for p in settled if str(p.get("sport") or "").upper() == sport
                and str(p.get("source") or "").startswith(sport.lower() + "_")]
        new_rows = [p for p in rows if str(p.get("recorded_at") or "") >= NBA_NHL_BASELINE_FROM]
        old_rows = [p for p in rows if str(p.get("recorded_at") or "") < NBA_NHL_BASELINE_FROM]
        rn, ro = _record(new_rows), _record(old_rows)
        fixes.append({
            "fix": f"{sport} props on live blended baselines + current teams (was 2024-25 tables)",
            "question": "Are the new-baseline props better calibrated than the old-table ones?",
            "expected": exp,
            "status": _status(rn["n"], GRADED_PROPS),
            "new": rn, "old": ro,
            "read": (None if not rn["n"] else
                     f"new {rn['wins']}-{rn['losses']} Brier {rn['brier']} vs old "
                     f"{ro['wins']}-{ro['losses']} Brier {ro['brier']}"),
        })

    # 5. Settlement repairs (already measured -- carried for completeness).
    bf = _load("outage_backfill_2026_10.json")
    passes = [bf] + list(bf.get("previous_passes") or [])
    fixes.append({
        "fix": "Outage backfill + NFL/NHL/MLB grader repairs",
        "question": "How many outage-voided real picks were recovered?",
        "expected": "measured on day one",
        "status": "graded",
        "new": {"recovered_total": sum(int(p.get("n_recovered") or 0) for p in passes),
                "passes": len(passes)},
        "old": None,
        "read": f"{sum(int(p.get('n_recovered') or 0) for p in passes)} picks recovered over {len(passes)} pass(es)",
    })

    pending = [f["fix"] for f in fixes if f["status"] != "graded"]
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "fixes": fixes,
        "n_graded": sum(1 for f in fixes if f["status"] == "graded"),
        "n_total": len(fixes),
        "still_waiting_on_games": pending,
        "bars": {"props": GRADED_PROPS, "dfs_slates": GRADED_SLATES},
        "note": ("Every 2026-10-23 fix graded against the version it replaced, on results "
                 "settled since. 'graded' = enough results for the comparison to mean "
                 "something; until then the status says so. Nothing is auto-tuned from this."),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"[fix-scorecard] {p['n_graded']}/{p['n_total']} graded")
    for f in p["fixes"]:
        print(f"  [{f['status']:7s}] {f['fix']}")
        if f.get("read"):
            print(f"            {f['read']}")
