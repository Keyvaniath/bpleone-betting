"""
EdgeStat -- regression test for the high-confidence board's real-outcome guards.

Proves the two guards in prob_calibration.py are NOT vacuous:
  1. CURATION drops a market family the settled ledger proves loses money.
  2. EMPIRICAL CALIBRATION blends a raw prob toward the family's realized rate,
     crushing overconfident rare-event OVERs toward what actually happens.
  3. The live board carries zero proven-negative plays.

Run standalone:  python verify_calibration.py   (exit 0 = all pass)
"""
from __future__ import annotations

import os
import json
import sys

import prob_calibration as pc
import high_confidence_board as hcb
import recalibration as rc

DATA = os.path.join(os.path.dirname(__file__), "..", "data")
fails = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{(' -- ' + detail) if detail else ''}")
    if not cond:
        fails.append(name)


pc.reset_caches()
neg = pc.proven_negative_families()
print(f"prob_calibration guards ({len(neg)} proven-negative families curated):\n")

# 1. CURATION -- a proven-negative family is dropped at the board layer.
out = []
hcb._add(out, sport="MLB", subject="Test Bleeder", matchup="X @ Y",
         market="to_hit_hr_yes", prob=0.68, fair=-180, family="batter", source="t")
check("curation drops to_hit_hr_yes (ledger: 14.7% hit, -122u)", len(out) == 0)

# 2. CALIBRATION MATH -- overconfident OVER blends toward realized (~16%).
cal_hr, meta_hr = pc.empirical_calibrate(0.65, "to_hit_hr_yes")
check("to_hit_hr_yes 0.65 -> below 0.30", cal_hr is not None and cal_hr < 0.30,
      f"got {None if cal_hr is None else round(cal_hr, 3)} (realized {meta_hr.get('realized')})")

# 3. CALIBRATION MATH -- a calibratable family returns the exact Bayesian blend.
raw = 0.70
cal_rn, meta_rn = pc.empirical_calibrate(raw, "to_score_run_no")
expected = (pc.PRIOR_K * raw + meta_rn.get("n", 0) * meta_rn.get("realized", 0)) / (pc.PRIOR_K + meta_rn.get("n", 0)) \
    if meta_rn.get("method") == "empirical" else None
check("to_score_run_no 0.70 is empirically calibrated to the Bayesian blend",
      meta_rn.get("method") == "empirical" and expected is not None and abs(cal_rn - expected) < 1e-9,
      f"{round(cal_rn, 4) if cal_rn else None} == {round(expected, 4) if expected else None}")

# 4. ADMISSION -- a clean model-only prop (no ledger history, not a loser) is admitted.
out = []
hcb._add(out, sport="MLB", subject="Test Clean", matchup="X @ Y",
         market="QUALITY_START_NO", prob=0.70, fair=-230, family="pitcher", source="t")
check("clean model-only pitcher prop admitted", len(out) == 1 and out[0].get("calibration") == "model_only")

# 5. PROB/ODDS CONSISTENCY -- displayed fair matches the displayed (calibrated) prob.
if out:
    p = out[0]
    implied = pc.prob_to_american(p["prob"])
    check("displayed fair_odds == prob_to_american(displayed prob)", p["fair_odds"] == implied,
          f"fair={p['fair_odds']} implied={implied}")

# 6. LIVE BOARD -- zero proven-negative plays actually shipped.
board = json.load(open(os.path.join(DATA, "high_confidence_board.json"), encoding="utf-8")).get("board", [])
viol = [p for p in board if pc.is_proven_negative(p.get("market"))]
check(f"live board has 0 proven-negative plays (board n={len(board)})", len(viol) == 0,
      ("offenders: " + ", ".join(p.get("market", "?") for p in viol)) if viol else "")

# 7. GUARD IS REAL -- the curation set is non-empty (something is actually guarded).
check("curation set non-empty", len(neg) > 0, f"{len(neg)} families")

# 8. OVERCONFIDENCE is a strict subset of proven-negative (a broken-prob family
#    must also be a money-loser) and narrower than it.
oc = pc.overconfident_families()
check("overconfident families subset of proven-negative", oc.issubset(neg) and 0 < len(oc) < len(neg),
      f"{len(oc)} overconfident of {len(neg)} curated")

# 9. The over/under distinction holds: a wildly overconfident OVER is flagged;
#    a family whose PROBABILITY is right but is priced short is NOT (could be +EV
#    at a soft line -- must survive for book-edge boards).
check("mlb_tb_1.5_over flagged overconfident", pc.is_overconfident("mlb_tb_1.5_over"))
check("k_1plus_yes NOT overconfident (priced-short, prob ~right)", not pc.is_overconfident("k_1plus_yes"))

# 10. SIDE/LINE-AWARE guard for raw book props (best_bets): reconstructs the
#     ledger family from (market, play, line). A broken OVER is flagged; the
#     profitable UNDER side and well-calibrated lines are not.
check("book prop total_bases OVER 1.5 flagged", pc.is_overconfident_play("batter_total_bases", "OVER", 1.5))
check("book prop total_bases UNDER 1.5 NOT flagged (profitable side)",
      not pc.is_overconfident_play("batter_total_bases", "UNDER", 1.5))
check("book prop home_runs OVER 0.5 NOT flagged (priced-short, prob ok)",
      not pc.is_overconfident_play("batter_home_runs", "OVER", 0.5))

# 11. GENERATOR-LEVEL RECALIBRATION genuinely improves calibration (ECE) AND
#     accuracy (Brier -- a proper score that punishes naive flattening), proving
#     it's real calibration, not just squashing probs toward the base rate.
rco = rc.run()
check("recalibration improves ECE", rco["ece_after"] < rco["ece_before"],
      f"{rco['ece_before']} -> {rco['ece_after']}")
check("recalibration improves Brier (not flattening)", rco["brier_after"] < rco["brier_before"],
      f"{rco['brier_before']} -> {rco['brier_after']}")

# 12. The transform is monotonic (a higher raw prob never maps to a lower
#     calibrated prob within a family) and identity for families with no history.
lo = rc.recalibrate(0.55, "mlb_tb_1.5_over")
hi = rc.recalibrate(0.78, "mlb_tb_1.5_over")
check("recalibration monotonic within a family", lo <= hi + 1e-9, f"{round(lo,3)} <= {round(hi,3)}")
check("recalibration is identity for an unknown family",
      abs(rc.recalibrate(0.70, "zzz_unknown_market_xyz") - 0.70) < 1e-9)

# 11. calibrate_play blends a raw book-prop prob toward its reconstructed family's
#     realized rate (the engine behind the PrizePicks value board). A raw 1.0 on a
#     family realizing ~0.96 should calibrate to near the realized rate, not stay 1.0.
cp, cm = pc.calibrate_play("batter_hrr", "UNDER", 4.5, 1.0)
check("calibrate_play(hrr under 4.5, raw 1.0) -> empirical near realized",
      cm.get("method") == "empirical" and cp is not None and cp < 1.0 and abs(cp - cm.get("realized", 0)) < 0.06,
      f"cal={None if cp is None else round(cp, 3)} realized={cm.get('realized')}")

if fails:
    print(f"\nFAILED: {len(fails)} check(s): {fails}")
    sys.exit(1)
print(f"\nALL CALIBRATION GUARDS PASS ({len(neg)} families curated, board clean).")
