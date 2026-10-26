"""
EdgeStat -- one-shot moneyline re-price (2026-10-23).

WHY: boards that lacked a price filled in a placeholder -110 (todays_top_plays
_fair_odds_for_source), and the ledger graded those MLB moneylines at it. The
10/23 Alpha was "MIL ML @ -110" with DraftKings at MIL -192 -- a fake +12.9%
edge, and every win paid +0.91u instead of the real price. 77 settled
moneylines carried a placeholder or no price (76 curated).

WHAT: data/ml_reprice_2026_10.json (built from the git history of
espn_odds.json: the last pre-game DraftKings line at/before each pick, else
the first pre-game line after it) is applied to the working ledger AND the
cold archive:
  * repriced -> book_american = the real line, payout_units recomputed at it,
    a `repriced` audit record keeps the old payout. fair_american is left as
    recorded (the Alpha locks key on it); every grader now prices from
    book_american first (all_picks_tracker._price_american).
  * unpriced (no pre-game line exists anywhere) -> voided, reason 'unpriced
    moneyline', never resurrected and never guessed.
Pending MLB moneylines still on a placeholder get the live line now.

Runs once (marker data/ml_reprice_2026_10_done.json), just before the ledger
build in daily-pipeline.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SEED = os.path.join(DATA_DIR, "ml_reprice_2026_10.json")
# 2026-10-26 extension: the pipeline's OTHER placeholders -- `ml_away or 100`
# and `total or 8.5` -- which the -110 search missed (29 moneylines at a fake
# +100; 9 pod totals on an 8.5 line DraftKings never posted). Built by
# tools/build_reprice_plus100.py from the same espn_odds.json git history.
SEED_B = os.path.join(DATA_DIR, "ml_reprice_2026_10b.json")
# 2026-10-26 DK standard: every other settled MLB moneyline without a book
# price, graded at the DraftKings pre-game line (POD had been recorded at
# in-play Bovada prices -- +940 vs DK -137). Lowest precedence: A and B win.
SEED_C = os.path.join(DATA_DIR, "ml_reprice_2026_10c.json")
MARKER = os.path.join(DATA_DIR, "ml_reprice_2026_10_done.json")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
ARCHIVE = os.path.join(DATA_DIR, "ledger_archive.json")


def _load(p: str) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _dec(a) -> float:
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / abs(a)


_SEED_CACHE = None


def apply_ledger(picks, side_of) -> Dict[str, int]:
    """IDEMPOTENT, called by EVERY ledger build (all_picks_tracker.run).

    The one-shot version lost a race on its first CI run: live-games rebuilt
    the ledger from a checkout taken before the re-price and its commit
    overwrote the corrected rows. Applying the seed inside the build means any
    workflow's ledger carries the correction. Already-corrected rows are
    skipped; pending placeholder-priced moneylines get the live DK line so
    they can never settle at -110."""
    global _SEED_CACHE
    if _SEED_CACHE is None:
        _SEED_CACHE = {r["pick_id"]: r for r in (_load(SEED).get("rows") or [])}
        for path in (SEED_B, SEED_C):
            for r in (_load(path).get("rows") or []):
                _SEED_CACHE.setdefault(r["pick_id"], r)
    seed = _SEED_CACHE
    now = dt.datetime.now().isoformat(timespec="seconds")
    n = {"repriced": 0, "voided_unpriced": 0, "voided_unpriced_total": 0, "pending_priced": 0}
    for p in picks:
        r = seed.get(p.get("pick_id"))
        if r and not p.get("repriced") and not str(p.get("voided_reason") or "").startswith("unpriced"):
            if r["status"] == "repriced" and p.get("settled"):
                old = p.get("payout_units")
                dec = _dec(r["book_american"])
                p["book_american"] = r["book_american"]
                p["payout_units"] = (round(dec - 1, 4) if p.get("result") == "won"
                                     else (-1.0 if p.get("result") == "lost" else 0.0))
                p["repriced"] = {"at": now, "from_payout": old, "recorded_price": p.get("fair_american"),
                                 "book_snapshot_at": r.get("snapshot_at"), "chosen": r.get("chosen"),
                                 "reason": ((f"2026-10-26: graded at the recorded {r.get('old_fair')}; "
                                             "re-priced at the real DraftKings pre-game moneyline (the "
                                             "house standard)") if r.get("kind") == "dk_standard" else
                                            (f"{'2026-10-26' if r.get('kind') else '2026-10-23'}: graded at "
                                             f"a placeholder {r.get('old_fair') or -110} the board filled "
                                             "in when the line was missing; re-priced at the real "
                                             "DraftKings pre-game moneyline"))}
                n["repriced"] += 1
            elif r["status"] == "unpriced" and p.get("settled"):
                p["voided"] = True
                p["voided_at"] = now
                p["voided_reason"] = (f"unpriced moneyline: graded at a placeholder {r.get('old_fair') or -110} "
                                      "and no real pre-game line exists on record -- no honest payout")
                n["voided_unpriced"] += 1
            elif r["status"] == "unpriced_total" and p.get("settled"):
                real = r.get("real_total")
                p["voided"] = True
                p["voided_at"] = now
                p["voided_reason"] = ("unpriced total: graded at the pipeline's placeholder 8.5 line; "
                                      + (f"DraftKings' real total was {real}" if real is not None
                                         else "no real pre-game total exists on record")
                                      + " -- the bet's line never existed")
                n["voided_unpriced_total"] += 1
    book = (_load(os.path.join(DATA_DIR, "espn_odds.json")).get("by_matchup") or {})
    for p in picks:
        if p.get("settled") or p.get("voided") or p.get("book_american") is not None:
            continue
        if p.get("fair_american") not in (-110, 100, None):
            continue
        sd = side_of(p)
        if not sd:
            continue
        px = (book.get(str(p.get("player_or_matchup") or "")) or {}).get("ml_home" if sd == "home" else "ml_away")
        if px is not None:
            p["book_american"] = px
            n["pending_priced"] += 1
    return n


def run(force: bool = False) -> Dict[str, Any]:
    if os.path.exists(MARKER) and not force:
        m = _load(MARKER)
        print(f"[ml-reprice] already applied {m.get('ran_at')} -- skipping")
        return m
    seed = {r["pick_id"]: r for r in (_load(SEED).get("rows") or [])}
    now = dt.datetime.now().isoformat(timespec="seconds")
    tally = {"repriced": 0, "voided_unpriced": 0, "pending_priced": 0,
             "old_net": 0.0, "new_net": 0.0}

    def apply(p: Dict[str, Any]) -> bool:
        r = seed.get(p.get("pick_id"))
        if not r or p.get("repriced") or str(p.get("voided_reason") or "").startswith("unpriced"):
            return False
        if r["status"] == "repriced":
            old = p.get("payout_units")
            dec = _dec(r["book_american"])
            new = round(dec - 1, 4) if p.get("result") == "won" else (
                -1.0 if p.get("result") == "lost" else 0.0)
            p["book_american"] = r["book_american"]
            p["payout_units"] = new
            p["repriced"] = {"at": now, "from_payout": old, "recorded_price": p.get("fair_american"),
                             "book_snapshot_at": r.get("snapshot_at"), "chosen": r.get("chosen"),
                             "reason": ("2026-10-23: graded at a placeholder -110 the board filled in "
                                        "when the line was missing; re-priced at the real DraftKings "
                                        "pre-game moneyline")}
            tally["repriced"] += 1
            tally["old_net"] += float(old or 0)
            tally["new_net"] += new
        else:
            p["voided"] = True
            p["voided_at"] = now
            p["voided_reason"] = ("unpriced moneyline: graded at a placeholder -110 and no real "
                                  "pre-game line exists on record -- no honest payout")
            tally["voided_unpriced"] += 1
        return True

    led = _load(LEDGER)
    picks = led.get("picks") or []
    for p in picks:
        apply(p)
    # Pending moneylines still on a placeholder: price them from the live board.
    import all_picks_tracker as apt
    book = (_load(os.path.join(DATA_DIR, "espn_odds.json")).get("by_matchup") or {})
    for p in picks:
        if p.get("settled") or p.get("voided") or p.get("book_american") is not None:
            continue
        sd = apt._is_mlb_moneyline_market(p)
        if not sd or p.get("fair_american") not in (-110, None):
            continue
        ln = book.get(str(p.get("player_or_matchup") or "")) or {}
        px = ln.get("ml_home" if sd == "home" else "ml_away")
        if px is not None:
            p["book_american"] = px
            tally["pending_priced"] += 1
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(led, f, indent=2)

    arch = _load(ARCHIVE)
    n_arch = 0
    for r in (arch.get("picks") or []):
        n_arch += 1 if apply(r) else 0
    if n_arch:
        with open(ARCHIVE, "w", encoding="utf-8") as f:
            json.dump(arch, f, indent=0)

    payload = {"ran_at": now, "n_seed": len(seed), "archive_rows_touched": n_arch,
               **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in tally.items()}}
    with open(MARKER, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    import sys
    p = run(force="--force" in sys.argv)
    print(f"[ml-reprice] {p}")
