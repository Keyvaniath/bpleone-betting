"""
EdgeStat -- Model Calibration Map (real outcomes; show-your-work transparency).

For every market family, compares what the MODEL predicted against what ACTUALLY
happened -- straight from the settled pick ledger, no synthetic data. This is the
evidence behind the High Confidence Board's two guards:

  - avg model-predicted prob vs realized hit rate  (the overconfidence gap)
  - net units / ROI over the sample
  - status:
      curated_out -- proven money-loser; HARD-EXCLUDED from the boards
      calibrated  -- >= CAL_MIN_N settled; board blends prob toward realized rate
      model_only  -- too few settled; board shows the raw model number (honest)

A professional desk publishes its calibration. If the model says 55% and 16%
actually happens, you should see that -- and see that we stopped betting it.

Output: data/calibration_map.json  ->  calibration-map.html
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List

import prob_calibration as pc

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "calibration_map.json")

MIN_N_RANK = 10   # only let well-sampled families drive the "most miscalibrated" sort


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _is_prizepicks(p) -> bool:
    """(2026-11-03) MLB-PP / PP_* rows are the UNVERIFIED locks-history import
    graded at PrizePicks' -136 break-even -- their own line, never in this map."""
    return (str(p.get("sport") or "").upper() == "MLB-PP"
            or str(p.get("market") or "").upper().startswith("PP_"))


def _price_class(p) -> str:
    """(2026-11-03) A timestamped book / B reconstructed book / C no book price."""
    c = ((p.get("price_provenance") or {}).get("class") or "C")
    return c if c in ("A", "B", "C") else "C"


def run() -> Dict[str, Any]:
    pc.reset_caches()
    all_picks = _load(LEDGER).get("picks") or []
    # (2026-11-03) PrizePicks rows leave the calibration map entirely.
    picks = [p for p in all_picks if not _is_prizepicks(p)]
    n_pp_excluded = sum(1 for p in all_picks if _is_prizepicks(p)
                        and not p.get("voided") and p.get("result") in ("won", "lost"))
    neg = pc.proven_negative_families()
    overconf = pc.overconfident_families()

    agg: Dict[str, Dict[str, float]] = {}
    for p in picks:
        if p.get("voided") or p.get("result") not in ("won", "lost"):   # ledger uses won/lost/push/pending
            continue
        fam = pc.canon_market_family(p.get("market"))
        pred = p.get("p_predicted")
        if pred is None:
            pred = p.get("prob")
        try:
            pred = float(pred)
        except (TypeError, ValueError):
            pred = None
        a = agg.setdefault(fam, {"n": 0, "wins": 0, "pred_sum": 0.0, "pred_n": 0, "net": 0.0})
        a["n"] += 1
        a["wins"] += 1 if p.get("result") == "won" else 0
        if pred is not None:
            a["pred_sum"] += pred
            a["pred_n"] += 1
        try:
            a["net"] += float(p.get("payout_units"))
        except (TypeError, ValueError):
            pass

    rows: List[Dict[str, Any]] = []
    tot_n = tot_pred = tot_wins = 0.0
    for fam, a in agg.items():
        n = int(a["n"])
        if n <= 0:
            continue
        realized = a["wins"] / n
        avg_pred = (a["pred_sum"] / a["pred_n"]) if a["pred_n"] else None
        status = "curated_out" if fam in neg else ("calibrated" if n >= pc.CAL_MIN_N else "model_only")
        # WHY a family is curated, the honest distinction:
        #   overconfident -- the model's probability itself is broken (realized far
        #                    below predicted); the "edge" is fake at ANY price.
        #   priced_short  -- the probability is ~right but the bet loses at our fair
        #                    price (could still be +EV at a soft book line).
        if fam in overconf:
            miscalibration = "overconfident"
        elif status == "curated_out":
            miscalibration = "priced_short"
        else:
            miscalibration = "ok"
        rows.append({
            "family": fam,
            "n_settled": n,
            "avg_model_pred": round(avg_pred, 4) if avg_pred is not None else None,
            "realized_hit_rate": round(realized, 4),
            "overconfidence_gap": round(avg_pred - realized, 4) if avg_pred is not None else None,
            "net_units": round(a["net"], 2),
            "roi_pct": round(100 * a["net"] / n, 1),
            "status": status,
            "miscalibration": miscalibration,
        })
        if avg_pred is not None:
            tot_n += n
            tot_pred += a["pred_sum"]
            tot_wins += a["wins"]

    # Most-miscalibrated first (well-sampled families only drive the ranking).
    rows.sort(key=lambda r: -((abs(r["overconfidence_gap"]) if r["overconfidence_gap"] is not None else 0)
                              if r["n_settled"] >= MIN_N_RANK else -1))

    # GUARD IMPACT -- the bottom line: what curation does to the book's ROI.
    def _agg(keep):
        n = w = 0
        net = 0.0
        cls: Dict[str, int] = {}
        for p in picks:
            if p.get("voided") or p.get("result") not in ("won", "lost"):
                continue
            if not keep(pc.canon_market_family(p.get("market"))):
                continue
            n += 1
            w += 1 if p.get("result") == "won" else 0
            c = _price_class(p)
            cls[c] = cls.get(c, 0) + 1
            try:
                net += float(p.get("payout_units"))
            except (TypeError, ValueError):
                pass
        return {"n": n, "net_units": round(net, 1),
                "roi_pct": round(100 * net / n, 1) if n else None,
                "hit_rate": round(w / n, 4) if n else None,
                "price_classes": cls}   # (2026-11-03) how much of it is at a real book price
    guard_impact = {
        "all": _agg(lambda f: True),
        "after_curation": _agg(lambda f: f not in neg),
        "curated_out": _agg(lambda f: f in neg),
        # (2026-11-03) honest label: the cut-set is fit on these same outcomes and
        # nearly every row is graded at the model's own fair odds (class C).
        "basis": "in-sample, model-fair-odds replay -- the cut is fit on these same "
                 "outcomes and most rows carry no sportsbook price (class C); "
                 "MLB-PP excluded. Not a betting ROI.",
    }

    # DESK-LEVEL honesty: raw vs curated net per whole sport. The family net above
    # governs MARKETS; this catches a desk whose thin outright markets escape it
    # (e.g. F1's POLE/TOP_3/TOP_6). A desk negative even AFTER curation has no
    # profitable subset to publish -- shown so the money map is the same one we
    # audit internally, not a cherry-pick.
    desk_report = pc.sport_curation_report()
    # (2026-11-03) MLB-PP leaves the desk map (unverified, not bettable), and a
    # desk is only "profitable" when every settled pick carries a sportsbook
    # price (class A/B). A positive replay at the model's own fair odds is
    # relabelled "positive_model_odds" -- calibration, not a betting result.
    desk_cls: Dict[str, Dict[str, int]] = {}
    for p in picks:
        if not p.get("settled") or p.get("voided") or p.get("result") not in ("won", "lost", "push"):
            continue
        s = str(p.get("sport") or "?").upper()
        c = _price_class(p)
        dc = desk_cls.setdefault(s, {})
        dc[c] = dc.get(c, 0) + 1
    desks = []
    for s, a in desk_report.items():
        if s == "MLB-PP":
            continue
        row = {"sport": s, **a}
        cls = desk_cls.get(s, {})
        row["price_classes"] = cls
        row["all_book_priced"] = bool(cls) and not cls.get("C")
        if row.get("status") == "profitable" and not row["all_book_priced"]:
            row["status"] = "positive_model_odds"
        desks.append(row)
    desks.sort(key=lambda d: -(d.get("net_curated") or 0))
    desk_curation = {
        "basis": "in-sample, model-fair-odds replay (MLB-PP excluded)",   # (2026-11-03)
        "summary": {
            "n_desks": len(desks),
            "profitable": sorted([d["sport"] for d in desks if d.get("status") == "profitable"]),
            "positive_model_odds": sorted([d["sport"] for d in desks
                                           if d.get("status") == "positive_model_odds"]),
            "underperforming": sorted([d["sport"] for d in desks
                                       if d.get("status") in ("underperforming", "proven_negative")]),
            "proven_negative_desks": sorted(pc.proven_negative_sports()),
        },
        "desks": desks,
    }

    n_cur = sum(1 for r in rows if r["status"] == "curated_out")
    n_cal = sum(1 for r in rows if r["status"] == "calibrated")
    n_mod = sum(1 for r in rows if r["status"] == "model_only")
    n_overconf = sum(1 for r in rows if r["miscalibration"] == "overconfident")
    net_protected = round(sum(r["net_units"] for r in rows if r["status"] == "curated_out"), 1)
    overall_pred = round(tot_pred / tot_n, 4) if tot_n else None
    overall_real = round(tot_wins / tot_n, 4) if tot_n else None

    result = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_families": len(rows),
        "n_curated_out": n_cur,
        "n_calibrated": n_cal,
        "n_model_only": n_mod,
        "n_overconfident": n_overconf,
        "n_prizepicks_excluded": n_pp_excluded,   # (2026-11-03) MLB-PP not in this map
        "units_protected_by_curation": net_protected,
        "guard_impact": guard_impact,
        "desk_curation": desk_curation,
        "overall_avg_model_pred": overall_pred,
        "overall_realized_hit_rate": overall_real,
        "overall_overconfidence_gap": round(overall_pred - overall_real, 4) if overall_pred and overall_real else None,
        "method_note": "Per market family, the model's average predicted probability vs the "
                       "realized hit rate over all settled bets in that family. Positive "
                       "overconfidence_gap = the model was too high. Families proven to lose "
                       "money are curated out of the boards; well-sampled families have their "
                       "displayed probabilities calibrated toward the realized rate.",
        "families": rows,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result


if __name__ == "__main__":
    o = run()
    print(f"[calibration-map] {o['n_families']} families | {o['n_curated_out']} curated out "
          f"({o['units_protected_by_curation']}u of losses avoided) | {o['n_calibrated']} calibrated | "
          f"{o['n_model_only']} model-only")
    gap = o.get("overall_overconfidence_gap")
    print(f"  overall: model predicts {o['overall_avg_model_pred']}, realized {o['overall_realized_hit_rate']} "
          f"(gap {gap:+})" if gap is not None else "  overall: insufficient data")
    print("  most miscalibrated (well-sampled):")
    for r in [x for x in o["families"] if x["n_settled"] >= 10][:6]:
        print(f"    {r['family']:24s} n={r['n_settled']:4d} model={r['avg_model_pred']} "
              f"real={r['realized_hit_rate']} gap={r['overconfidence_gap']:+} [{r['status']}]")
