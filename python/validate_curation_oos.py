"""
Out-of-sample validation of the family-curation edge.

The published "+14.1% ROI" comes from dropping proven-negative market families
(n>=25, net<=-5u) measured over the WHOLE ledger -- i.e. the curation rule is
fit on the same data it's scored on. This script answers the only question that
matters for real money: does that edge survive OUT OF SAMPLE?

Method:
  1. SANITY -- replicate the full-sample curated number from raw picks. If it
     matches the published ~+14.1% / 1469 bets / 67.5%, the replication is faithful.
  2. HELD-OUT -- chronological split. Derive the cut-set on the EARLY window only,
     freeze it, then score ROI on the LATER (unseen) window using only those
     pre-committed cuts. Compare to the test-window raw ROI.
  3. PERSISTENCE -- of the families cut on TRAIN, what is their net IN TEST? If the
     losers keep losing, the cuts capture real signal; if ~0, they were noise.

Honest about the sample: ~1 month of data, so a held-out tail is small -> directional.
"""
import json
import os
from prob_calibration import canon_market_family, market_family, CURATE_MIN_N, CURATE_MAX_NET

LEDGER = os.path.join(os.path.dirname(__file__), "..", "data", "all_picks_ledger.json")


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


def main():
    picks = load_picks()
    picks.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))
    dates = sorted({p.get("date") for p in picks if p.get("date")})
    print(f"Settled picks: {len(picks)}   span: {dates[0]} .. {dates[-1]}  ({len(dates)} days)")
    print("=" * 78)

    # 1) SANITY -- full-sample curated (in-sample, the published number)
    full_cut = cut_set(picks)
    raw = score(picks)
    cur = score(picks, full_cut)
    print("1) SANITY  (full-sample, in-sample -- should match published ~+14.1% / 1469 / 67.5%)")
    print(f"   raw firehose : n={raw['n']:5d}  roi={raw['roi']:+6.1f}%  hit={raw['hit']:.1f}%")
    print(f"   curated      : n={cur['n']:5d}  roi={cur['roi']:+6.1f}%  hit={cur['hit']:.1f}%  "
          f"(net {cur['net']:+.0f}u, {len(full_cut)} family-keys cut)")
    print("=" * 78)

    # 2) HELD-OUT -- multiple chronological splits
    print("2) HELD-OUT  (cut-set frozen on EARLY window, scored on UNSEEN later window)")
    for frac in (0.60, 0.70, 0.80):
        ci = int(len(dates) * frac)
        cutoff = dates[ci]
        train = [p for p in picks if (p.get("date") or "") < cutoff]
        test = [p for p in picks if (p.get("date") or "") >= cutoff]
        tcut = cut_set(train)
        t_raw = score(test)
        t_oos = score(test, tcut)          # honest OOS
        t_leak = score(test, full_cut)     # uses full-sample cuts = leakage, for ref
        print(f"   [{int(frac*100)}/{int((1-frac)*100)}] train {train[0]['date']}..{cutoff} "
              f"(n={len(train)}, {len(tcut)} cut)  |  test {cutoff}..{dates[-1]} (n={len(test)})")
        print(f"        TEST raw         : n={t_raw['n']:5d}  roi={t_raw['roi']:+6.1f}%  hit={t_raw['hit']:.1f}%")
        print(f"        TEST curated OOS : n={t_oos['n']:5d}  roi={t_oos['roi']:+6.1f}%  hit={t_oos['hit']:.1f}%   <== honest")
        print(f"        TEST curated leak: n={t_leak['n']:5d}  roi={t_leak['roi']:+6.1f}%  (full-sample cuts, ref)")
    print("=" * 78)

    # 3) PERSISTENCE -- do TRAIN-cut families keep losing in TEST? (70/30)
    ci = int(len(dates) * 0.70)
    cutoff = dates[ci]
    train = [p for p in picks if (p.get("date") or "") < cutoff]
    test = [p for p in picks if (p.get("date") or "") >= cutoff]
    tcut = cut_set(train)
    test_fs = family_stats(test)
    rows = []
    for fam in tcut:
        n, nt = test_fs.get(fam, [0, 0.0])
        rows.append((fam, n, nt))
    rows.sort(key=lambda r: r[2])
    kept_losing = sum(1 for _, n, nt in rows if n >= 5 and nt < 0)
    flipped = sum(1 for _, n, nt in rows if n >= 5 and nt > 0)
    test_net_of_cuts = sum(nt for _, n, nt in rows)
    print("3) PERSISTENCE  (families CUT on train -> their realized net in the TEST window)")
    print(f"   of {len(tcut)} cut family-keys: {kept_losing} kept losing, {flipped} flipped positive "
          f"(>=5 test bets); combined TEST net of cut families = {test_net_of_cuts:+.0f}u")
    print("   worst-persisting (still bleeding out-of-sample):")
    for fam, n, nt in rows[:6]:
        if n >= 3:
            print(f"      {fam[:46]:46s} test n={n:3d} net={nt:+6.1f}u")
    print("   any that FLIPPED positive (cut was noise / regime shift):")
    for fam, n, nt in [r for r in rows if r[2] > 0][:6]:
        if n >= 3:
            print(f"      {fam[:46]:46s} test n={n:3d} net={nt:+6.1f}u")


if __name__ == "__main__":
    main()
