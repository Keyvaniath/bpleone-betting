"""
Family durability scorecard -> data/family_durability.json

durable_edge_analysis deep-dives ONE family (mlb_hrr_3.5_under). This generalizes
the question -- "where does the alpha actually live, and is it stable?" -- across
EVERY surviving market family (i.e., not curation-cut) with a real sample:

  - per-family bootstrap 95% CI on ROI (resampling per-pick payouts, fixed seed)
  - temporal split-half stability: ROI on the chronological first vs second half
  - an honest tier from those two, not from the headline ROI:
      DURABLE    CI lower bound > 0 AND both halves positive AND n >= DURABLE_N
      PROMISING  ROI > 0 AND (CI_lo > 0 OR both halves positive), n >= MIN_N
      FRAGILE    ROI > 0 but the CI spans zero and the halves disagree
      NEGATIVE   ROI <= 0 (survivors that are merely not-bad-enough to cut)

Ranked by CI lower bound (the conservative estimate) -- a family is only as good
as the worst its sample plausibly allows. This systematizes the concentration
finding: instead of "the edge is carried by ~2 families", it names each carrier
and says whether it has held up over time.

Runs in the daily pipeline after the ledger build. Zero paid data.
"""
import json
import os
import random
import datetime
from prob_calibration import canon_market_family, proven_negative_families

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "family_durability.json")

MIN_N = 40        # below this a family isn't worth tiering at all
DURABLE_N = 100   # DURABLE additionally requires a real sample
B = 1000          # bootstrap resamples (fixed seed -> deterministic artifact)


def _net(p):
    pu = p.get("payout_units")
    if pu is not None:
        return float(pu)
    return 0.91 if p.get("result") == "won" else (-1.0 if p.get("result") == "lost" else 0.0)


def _roi(nets):
    return round(100.0 * sum(nets) / len(nets), 1) if nets else 0.0


def _boot_ci(nets, seed=7):
    rng = random.Random(seed)
    n = len(nets)
    rois = []
    for _ in range(B):
        s = [nets[rng.randrange(n)] for _ in range(n)]
        rois.append(100.0 * sum(s) / n)
    rois.sort()
    return round(rois[int(0.025 * B)], 1), round(rois[int(0.975 * B)], 1)


def build():
    d = json.load(open(LEDGER, encoding="utf-8"))
    settled = [p for p in (d.get("picks") or [])
               if p.get("settled") and p.get("result") in ("won", "lost")
               and not p.get("voided")]
    settled.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))

    cut = set(proven_negative_families())
    by_fam = {}
    for p in settled:
        fam = canon_market_family(p.get("market"))
        if not fam or fam == "?" or fam in cut:
            continue
        by_fam.setdefault(fam, []).append(p)

    rows = []
    for fam, pks in by_fam.items():
        if len(pks) < MIN_N:
            continue
        nets = [_net(p) for p in pks]
        wins = sum(1 for p in pks if p.get("result") == "won")
        half = len(pks) // 2
        h1, h2 = _roi(nets[:half]), _roi(nets[half:])
        lo, hi = _boot_ci(nets)
        roi = _roi(nets)
        both_pos = h1 > 0 and h2 > 0
        if roi <= 0:
            tier = "NEGATIVE"
        elif lo > 0 and both_pos and len(pks) >= DURABLE_N:
            tier = "DURABLE"
        elif lo > 0 or both_pos:
            tier = "PROMISING"
        else:
            tier = "FRAGILE"
        rows.append({
            "family": fam, "n": len(pks),
            "hit": round(wins / len(pks), 3),
            "net_units": round(sum(nets), 1), "roi": roi,
            "ci_lo": lo, "ci_hi": hi,
            "h1_roi": h1, "h2_roi": h2, "both_halves_positive": both_pos,
            "tier": tier,
        })
    rows.sort(key=lambda r: -r["ci_lo"])

    tiers = {}
    for r in rows:
        tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1

    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_settled_total": len(settled),
        "n_families_cut": len(cut),
        "n_families_evaluated": len(rows),
        "min_n": MIN_N, "durable_n": DURABLE_N,
        "tiers": tiers,
        "families": rows,
        "method_note": ("Every surviving (non-cut) family with n >= %d graded picks, ranked by the "
                        "LOWER bound of a %d-resample bootstrap 95%% CI on ROI. DURABLE = CI floor "
                        "above zero AND positive in both chronological halves AND n >= %d. A big "
                        "headline ROI with a CI spanning zero or a losing second half is FRAGILE, "
                        "not edge." % (MIN_N, B, DURABLE_N)),
        "caveats": [
            "Bootstrap CIs treat picks as independent; correlated slates (same game/day) understate variance.",
            "Split-half stability is a coarse regime check, not a forecast.",
            "Families below n=%d are unscored -- absence here is not endorsement." % MIN_N,
            "All numbers are 1u-flat on the ledger's recorded payouts.",
        ],
    }


def run():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT} | {p['n_families_evaluated']} families tiered: {p['tiers']}")
    for r in p["families"][:8]:
        print(f"  [{r['tier']:9}] {r['family']:32} n={r['n']:4} roi={r['roi']:+6.1f}% "
              f"CI[{r['ci_lo']:+.1f},{r['ci_hi']:+.1f}] halves {r['h1_roi']:+.1f}/{r['h2_roi']:+.1f}")
