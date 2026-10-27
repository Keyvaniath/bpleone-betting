"""
EdgeStat -- Play-of-the-Day P&L tracker (PRIMARY accuracy metric).

This is Brandon's accuracy benchmark: ONE pick per day, the highest-edge
ML / total play from today.json, recorded with a permanent ID. Graded by
the all-picks ledger (source "pod") since 2026-10-26. All-time + last-30-day W-L,
net units (assumes flat 1u stake), ROI%.

What makes this DIFFERENT from locks_of_day:
   exactly 1 pick per day (not 5)
   GAME-level only (no PrizePicks) -- the settlement is reliable
   flat 1u stake (no Kelly inflation)
   no calibration shrinkage on probability (we're tracking what was
     ACTUALLY called, not what the model "should have called")

Output: data/pod_pl.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "pod_pl.json")
MAX_HISTORY = 365   # ~1 year of daily PODs


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _today_date_str() -> str:
    return dt.date.today().isoformat()


def _american_to_decimal(american):
    if american is None or not isinstance(american, (int, float)): return None
    if american >= 0: return 1 + american / 100
    return 1 + 100 / abs(american)


def _pick_today_pod() -> Optional[Dict[str, Any]]:
    """Pick the day's POD = highest-edge ML or game total from today.json.

    Brandon wants ONLY game-level picks (no player props) for P&L
    accuracy -- player props need per-player gamelogs to settle, and
    he wants the single best ML/TOTAL of the day as the benchmark.

    GUARD: if today.json is stale (generated_at older than 6 hours OR
    not from today's date), we refuse to lock in a POD -- better to
    have no POD recorded than to lock in a stale one.
    """
    today = _load(os.path.join(DATA_DIR, "today.json"))
    if not today: return None

    # Staleness check: today.json's generated_at must be from today
    today_str = dt.date.today().isoformat()
    gen_at = (today.get("generated_at") or "")[:10]
    if gen_at and gen_at != today_str:
        # today.json is from a different date -- don't record stale POD
        return None
    # Also check age in hours
    try:
        gen_dt = dt.datetime.fromisoformat(today.get("generated_at"))
        age_hours = (dt.datetime.now() - gen_dt).total_seconds() / 3600
        if age_hours > 6: return None    # too stale
    except Exception:
        pass

    best = None
    for g in (today.get("games") or []):
        recos = g.get("recommendations") or []
        for r in recos:
            label = (r.get("label") or "").upper()
            # Only ML or OVER/UNDER markets
            if not ("_ML" in label or "OVER_" in label or "UNDER_" in label):
                continue
            edge = r.get("edge_pct") or 0
            if best is None or edge > (best.get("edge_pct") or 0):
                best = {
                    "matchup": g.get("matchup"),
                    "label": label,
                    "model_prob": r.get("model_prob"),
                    "market_price": r.get("market_price"),
                    "edge_pct": edge,
                    "confidence": r.get("confidence"),
                    "first_pitch_str": g.get("time"),   # e.g. "8:40p ET"
                    "gamePk": g.get("gamePk"),          # MLB game ID for exact matching
                }
    return best


def run() -> Dict[str, Any]:
    state = _load(OUT)
    history = state.get("history") or []
    existing_by_date = {p.get("date"): p for p in history}
    today_str = _today_date_str()

    # Record today's POD if not already done
    n_added = 0
    if today_str not in existing_by_date:
        pod = _pick_today_pod()
        if pod and pod.get("matchup") and pod.get("label"):
            decimal_odds = _american_to_decimal(pod.get("market_price")) or 1.91
            # PRICE SANITY: during odds-feed outages the upstream POD can carry a
            # garbage price (2026-07-12: TEX_ML "priced" +2100 with model 52% ->
            # "edge 1053%" -> settled as a +21u phantom on the homepage record).
            # A POD is a high-confidence play; if the price implies a longshot
            # (>+1000) or an absurd model edge (>100%), the PRICE is what's
            # broken -- record at the model's fair price instead and flag it.
            mp = pod.get("model_prob")
            price_suspect = False
            implied_edge = (mp * decimal_odds - 1) if (mp and decimal_odds) else 0
            if decimal_odds > 11.0 or implied_edge > 1.0:
                price_suspect = True
                decimal_odds = round(1.0 / mp, 3) if mp and mp > 0.05 else 1.91
            entry = {
                "date": today_str,
                "recorded_at": dt.datetime.now().isoformat(timespec="seconds"),
                "matchup": pod.get("matchup"),
                "label": pod.get("label"),
                "model_prob": pod.get("model_prob"),
                "market_price": pod.get("market_price"),
                "decimal_odds": round(decimal_odds, 3),
                "raw_edge_pct": pod.get("edge_pct"),   # tracking what was called, not "true" edge
                "price_suspect": price_suspect,
                "settled": False,
                "result": "pending",
                "payout_units": None,
                "settled_at": None,
            }
            history.append(entry)
            n_added = 1

    # GRADE FROM THE LEDGER (2026-10-26). pod_pl used to grade itself --
    # matchup-string matching against a rolling scores window (wrong games of a
    # series: 9/01 CHW ML "won" when CHW lost 3-6), its own recorded prices
    # (in-play +940, placeholder +100/-110, 8.5 totals) and the off-day
    # DEMO_SLATE game. The ledger harvests todays_pod as source "pod" and grades
    # it at the house price against verified finals, with every restatement
    # applied, so each entry now MIRRORS its ledger row. Entries the ledger never
    # carried take data/pod_pl_regrade_2026_10.json (tools/build_pod_pl_regrade.py).
    # Nothing is graded here any more; an entry without either stays pending.
    n_newly_settled = 0
    led = _load(os.path.join(DATA_DIR, "all_picks_ledger.json")).get("picks") or []
    arch = _load(os.path.join(DATA_DIR, "ledger_archive.json")).get("picks") or []
    by_key: Dict[tuple, Dict[str, Any]] = {}
    for r in list(arch) + list(led):   # working ledger last: it wins
        if r.get("source") == "pod" or "pod" in (r.get("also_sources") or []):
            by_key[(str(r.get("date"))[:10], r.get("player_or_matchup"), r.get("market"))] = r
    seed = {(r["date"], r["matchup"], r["label"]): r
            for r in (_load(os.path.join(DATA_DIR, "pod_pl_regrade_2026_10.json")).get("rows") or [])}
    for pod in history:
        k = (pod.get("date"), pod.get("matchup"), pod.get("label"))
        r, sd = by_key.get(k), seed.get(k)
        was = (pod.get("settled"), pod.get("result"), pod.get("payout_units"))
        if r is not None:
            pod["graded_by"] = "ledger"
            if r.get("voided"):
                pod.update(settled=True, result="void", payout_units=0.0,
                           void_reason=r.get("voided_reason"))
            elif r.get("settled") and r.get("result") in ("won", "lost", "push"):
                pod.update(settled=True, result=r["result"], payout_units=r.get("payout_units"),
                           book_american=r.get("book_american"))
                pod.pop("void_reason", None)
            else:
                pod.update(settled=False, result="pending", payout_units=None)
        elif sd is not None:
            pod["graded_by"] = "regrade_2026_10"
            if sd["status"] == "void":
                pod.update(settled=True, result="void", payout_units=0.0, void_reason=sd.get("reason"))
            else:
                pod.update(settled=True, result=sd["result"], payout_units=sd["payout_units"],
                           book_american=sd.get("book_american"))
        if (pod.get("settled"), pod.get("result"), pod.get("payout_units")) != was:
            if pod.get("settled") and not was[0]:
                n_newly_settled += 1
            if pod.get("settled") and not pod.get("settled_at"):
                pod["settled_at"] = dt.datetime.now().isoformat(timespec="seconds")
        # stale self-grading artefacts from the old path
        for f in ("payout_corrected", "correction_note"):
            pod.pop(f, None)

    # Cap
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    # Aggregate
    voided = [p for p in history if p.get("result") == "void"]
    settled = [p for p in history if p.get("settled") and p.get("result") in ("won", "lost", "push")]
    pending = [p for p in history if not p.get("settled")]
    wins = sum(1 for p in settled if p["result"] == "won")
    losses = sum(1 for p in settled if p["result"] == "lost")
    pushes = sum(1 for p in settled if p["result"] == "push")
    n_decided = wins + losses
    hit_rate = round(wins / n_decided, 4) if n_decided > 0 else None
    net_units = round(sum((p.get("payout_units") or 0) for p in settled), 3)
    n_risked = sum(1 for p in settled if p["result"] != "push")   # 1u per pick
    roi_pct = round(net_units / n_risked * 100, 2) if n_risked > 0 else None

    # Last 30 days
    today = dt.date.today()
    last_30 = []
    for p in settled:
        try:
            d = dt.date.fromisoformat(p.get("date") or "")
            if (today - d).days <= 30:
                last_30.append(p)
        except Exception:
            continue
    l30_wins = sum(1 for p in last_30 if p["result"] == "won")
    l30_losses = sum(1 for p in last_30 if p["result"] == "lost")
    l30_net = round(sum((p.get("payout_units") or 0) for p in last_30), 3)
    l30_decided = l30_wins + l30_losses

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "stake_assumption": "1u flat per pick",
        "total_pods": len(history),
        "n_settled": len(settled),
        "n_pending": len(pending),
        "n_void": len(voided),
        "graded_by": ("the all-picks ledger (house price = DraftKings pre-game line, verified "
                      "finals, every restatement applied); since 2026-10-26"),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "net_units": net_units,
        "roi_pct": roi_pct,
        "last_30_days": {
            "wins": l30_wins,
            "losses": l30_losses,
            "net_units": l30_net,
            "hit_rate": round(l30_wins / l30_decided, 4) if l30_decided > 0 else None,
        },
        "n_added_this_run": n_added,
        "n_newly_settled_this_run": n_newly_settled,
        "todays_pod": next((p for p in history if p["date"] == today_str), None),
        "history": history,
        "note": ("Play of the Day P&L: ONE pick per day, ML or game-total "
                  "only. Flat 1u stake. The single accuracy benchmark -- "
                  "no Kelly inflation, no PrizePicks, no aggregated 5-locks. "
                  "Brandon's primary track record."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"POD P&L: {p['total_pods']} total PODs ({p['n_settled']} settled, {p['n_pending']} pending)")
    print(f"  This run: +{p['n_added_this_run']} new, +{p['n_newly_settled_this_run']} newly settled")
    if p["hit_rate"] is not None:
        print(f"  All-time: {p['wins']}-{p['losses']}-{p['pushes']} ({p['hit_rate']*100:.1f}%) | net {p['net_units']:+.2f}u | ROI {p['roi_pct']:+.1f}%")
    else:
        print(f"  All-time: 0-0 (no settled outcomes yet)")
    l30 = p["last_30_days"]
    if l30["hit_rate"] is not None:
        print(f"  Last 30d: {l30['wins']}-{l30['losses']} ({l30['hit_rate']*100:.1f}%) | net {l30['net_units']:+.2f}u")
    if p["todays_pod"]:
        t = p["todays_pod"]
        print(f"\n  Today's POD: {t['matchup']} {t['label']} @ {t['market_price']} (model {(t.get('model_prob') or 0)*100:.0f}%) -- {t['result'].upper()}")
