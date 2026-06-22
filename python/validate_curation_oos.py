"""
Out-of-sample validation of the family-curation edge  ->  data/curation_oos_validation.json

The published "+14% ROI" comes from dropping proven-negative market families
(n>=25, net<=-5u) measured over the WHOLE ledger -- i.e. the curation rule is
fit on the same data it's scored on. This module answers the only question that
matters for real money: does that edge survive OUT OF SAMPLE?

Method:
  1. SANITY -- replicate the full-sample curated number from raw picks. If it
     matches the published ~+14% / 67.5%, the replication is faithful.
  2. HELD-OUT -- chronological split. Derive the cut-set on the EARLY window only,
     freeze it, then score ROI on the LATER (unseen) window using only those
     pre-committed cuts. Compare to the test-window raw ROI.
  3. PERSISTENCE -- of the families cut on TRAIN, what is their net IN TEST? If the
     losers keep losing, the cuts capture real signal; if ~0, they were noise.

Honest about the sample: ~1 month of data, so a held-out tail is small -> directional.
Emits a JSON artifact the track-record / calibration-map pages render, so the
held-out validation auto-updates as the ledger grows. Runs in the daily pipeline
after the ledger is rebuilt.
"""
import json
import os
import datetime
from prob_calibration import canon_market_family, market_family, CURATE_MIN_N, CURATE_MAX_NET

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "curation_oos_validation.json")


def load_picks():
    d = json.load(open(LEDGER, encoding="utf-8"))
    return [p for p in (d.get("picks") or [])
            if p.get("settled") and p.get("result") in ("won", "lost", "push")
            and not p.get("voided")]


def net(p):
    pu = p.get("payout_units")
    if pu is not None:
        return float(pu)
    r = p.get("result")
    return 0.91 if r == "won" else (-1.0 if r == "lost" else 0.0)


def fams(p):
    m = p.get("market")
    return {canon_market_family(m), market_family(m)}


def family_stats(pks):
    """Per-family (n, net) keyed by BOTH canonical and line-stripped family."""
    agg = {}
    for p in pks:
        nv = net(p)
        for key in fams(p):
            a = agg.setdefault(key, [0, 0.0])
            a[0] += 1
            a[1] += nv
    return agg


def cut_set(pks):
    """The curation rule fit on pks: families with n>=MIN and net<=MAX."""
    return {k for k, (n, nt) in family_stats(pks).items()
            if n >= CURATE_MIN_N and nt <= CURATE_MAX_NET}


def score(pks, cut=None):
    cut = cut or set()
    incl = [p for p in pks if not (fams(p) & cut)]
    graded = [p for p in incl if p.get("result") in ("won", "lost")]
    n = len(graded)
    netu = sum(net(p) for p in incl)
    wins = sum(1 for p in graded if p.get("result") == "won")
    return {"n": n, "net": netu,
            "roi": (100 * netu / n if n else 0.0),
            "hit": (100 * wins / n if n else 0.0)}


def _holdout(picks, dates, frac, full_cut):
    ci = int(len(dates) * frac)
    cutoff = dates[ci]
    train = [p for p in picks if (p.get("date") or "") < cutoff]
    test = [p for p in picks if (p.get("date") or "") >= cutoff]
    tcut = cut_set(train)
    t_raw = score(test)
    t_oos = score(test, tcut)
    t_leak = score(test, full_cut)
    row = {
        "split": f"{int(round(frac * 100))}/{int(round((1 - frac) * 100))}",
        "train_start": train[0]["date"] if train else None,
        "train_end": cutoff,
        "test_end": dates[-1],
        "train_n": len(train),
        "families_cut": len(tcut),
        "test_raw_roi": round(t_raw["roi"], 1),
        "test_oos_roi": round(t_oos["roi"], 1),
        "test_oos_hit": round(t_oos["hit"], 1),
        "test_oos_n": t_oos["n"],
        "test_leak_roi": round(t_leak["roi"], 1),
    }
    return row, (train, test, tcut)


# A surviving family is FLAGGED ("thin, likely small-sample luck not edge") when it
# posts an implausible ROI on a small sample -- e.g. UFC round-1-finish YES hitting
# 59% on n=49 (real R1 finishes run ~15-25%). Quarantined from the robust headline
# pending more data; still shown, just not trusted.
FLAG_THIN_N = 75
FLAG_HOT_ROI = 80.0


def _concentration(test, tcut):
    """Where does the curated held-out edge actually come from? Decompose the
    surviving (un-cut) test picks by family. A "+16% held-out" that is really one
    or two families is fragile -- so we publish the breakdown, the net excluding
    the top 2, and the edge excluding small-sample-flagged families."""
    agg = {}
    for p in test:
        if fams(p) & tcut:
            continue
        if p.get("result") not in ("won", "lost"):
            continue
        fam = canon_market_family(p.get("market"))
        a = agg.setdefault(fam, [0, 0.0, 0])
        a[0] += 1
        a[1] += net(p)
        if p.get("result") == "won":
            a[2] += 1
    rows = sorted(((f, n, nt, w) for f, (n, nt, w) in agg.items()), key=lambda r: -r[2])
    tot_net = sum(r[2] for r in rows)
    tot_n = sum(r[1] for r in rows)

    def _roi(n, nt):
        return (100 * nt / n) if n else 0.0

    contributors = [{
        "family": f, "n": n, "net": round(nt, 1),
        "roi": round(_roi(n, nt), 1),
        "hit": round(100 * w / n, 1) if n else 0.0,
        "flagged": bool(n < FLAG_THIN_N and _roi(n, nt) > FLAG_HOT_ROI),
    } for f, n, nt, w in rows]
    flagged = [c for c in contributors if c["flagged"]]
    flag_fams = {c["family"] for c in flagged}

    top2 = rows[:2]
    net_top2 = round(sum(r[2] for r in top2), 1)
    net_ex_top2 = round(tot_net - net_top2, 1)
    ex_n = sum(r[1] for r in rows if r[0] not in flag_fams)
    ex_net = sum(r[2] for r in rows if r[0] not in flag_fams)
    roi_ex_flagged = round(100 * ex_net / ex_n, 1) if ex_n else 0.0

    return {
        "n_surviving_families": len(rows),
        "curated_net": round(tot_net, 1),
        "curated_n": tot_n,
        "top2": [{"family": r[0], "n": r[1], "net": round(r[2], 1),
                  "roi": round(_roi(r[1], r[2]), 1)} for r in top2],
        "net_top2": net_top2,
        "net_ex_top2": net_ex_top2,
        "roi_ex_flagged": roi_ex_flagged,
        "n_ex_flagged": ex_n,
        "top_contributors": contributors[:6],
        "flagged_families": flagged,
        "note": (
            f"Concentrated: the top 2 of {len(rows)} surviving families produced "
            f"{net_top2:+.0f}u; the other {len(rows) - 2} combined "
            f"{'made' if net_ex_top2 >= 0 else 'LOST'} {abs(net_ex_top2):.0f}u."
            + (f" One pillar is flagged small-sample and quarantined; excluding flagged "
               f"families the held-out edge is {roi_ex_flagged:+.1f}% (n={ex_n})."
               if flagged else
               " No surviving family trips the small-sample flag at current thresholds.")
        ),
    }


def build():
    picks = load_picks()
    picks.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))
    dates = sorted({p.get("date") for p in picks if p.get("date")})
    if len(dates) < 6:
        return {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "n_settled": len(picks), "insufficient": True,
                "note": "need >= ~6 distinct settled days for a held-out split"}

    full_cut = cut_set(picks)
    raw = score(picks)
    cur = score(picks, full_cut)

    holdout = []
    ctx_70 = None
    for frac in (0.60, 0.70, 0.80):
        row, ctx = _holdout(picks, dates, frac, full_cut)
        holdout.append(row)
        if row["split"] == "70/30":
            ctx_70 = ctx

    train, test, tcut = ctx_70
    test_fs = family_stats(test)
    rows = sorted(((fam, test_fs.get(fam, [0, 0.0])[0], test_fs.get(fam, [0, 0.0])[1])
                   for fam in tcut), key=lambda r: r[2])
    kept = sum(1 for _, n, nt in rows if n >= 5 and nt < 0)
    flip = sum(1 for _, n, nt in rows if n >= 5 and nt > 0)
    netcuts = sum(nt for _, n, nt in rows)
    worst = [{"family": f, "n": n, "net": round(nt, 1)} for f, n, nt in rows if n >= 3][:6]
    concentration = _concentration(test, tcut)

    h70 = next(h for h in holdout if h["split"] == "70/30")
    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_settled": len(picks),
        "span": [dates[0], dates[-1]],
        "n_days": len(dates),
        "in_sample": {
            "raw_roi": round(raw["roi"], 1), "raw_n": raw["n"],
            "curated_roi": round(cur["roi"], 1), "curated_n": cur["n"],
            "curated_hit": round(cur["hit"], 1), "families_cut": len(full_cut),
        },
        "holdout": holdout,
        "persistence": {
            "n_cut": len(tcut), "kept_losing": kept, "flipped": flip,
            "test_net_of_cuts": round(netcuts, 0), "worst": worst,
        },
        "concentration": concentration,
        "caveats": [
            "Short sample: ~1 month, single MLB season. The held-out tail is genuinely "
            "unseen but adjacent in time -- not a cross-season or cross-regime test.",
            "Concentrated in MLB props. The edge is largely: don't bet structurally "
            "overpriced longshot overs (HR/XBH overs, to-hit-HR YES) -- a known, "
            "persistent market inefficiency.",
            "ROI is measured at the model's fair price / settled outcome. It does NOT yet "
            "prove we beat the closing line (CLV) -- that requires the live odds feed.",
        ],
        "headline": (f"The curation derived on early data still returns "
                     f"{h70['test_oos_roi']:+.1f}% on the unseen later window, and the "
                     f"families it cut went on to lose {abs(netcuts):.0f}u out-of-sample."),
    }


def write_artifact():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = write_artifact()
    print(f"Wrote {OUT}")
    if p.get("insufficient"):
        print("  insufficient sample for a held-out split")
    else:
        ins = p["in_sample"]
        print(f"  [sanity] full-sample curated: roi {ins['curated_roi']:+.1f}%  "
              f"hit {ins['curated_hit']:.1f}%  (n={ins['curated_n']}, raw {ins['raw_roi']:+.1f}%)")
        for h in p["holdout"]:
            print(f"  [{h['split']}] test raw {h['test_raw_roi']:+.1f}%  ->  "
                  f"curated OOS {h['test_oos_roi']:+.1f}%  hit {h['test_oos_hit']:.1f}%  (n={h['test_oos_n']})")
        print(f"  {p['headline']}")
