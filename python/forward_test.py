"""
Prospective forward-test -- the no-hindsight capstone.

validate_curation_oos splits the EXISTING ledger train/test, so the "test"
window already existed when the split was drawn (quasi-out-of-sample). This module
is stricter: it FREEZES the curation cut-set on data up to a fixed ANCHOR date --
set ONCE, the first time this runs and then persisted -- and scores ONLY picks
settled on/after that anchor. Every measured outcome postdates the frozen rule, so
there is zero hindsight. It starts near-empty and accrues daily; that is the point.

The anchor + frozen cut-set live in data/forward_test.json and are reloaded every
run so the rule never refits. It re-anchors only if that artifact is missing (e.g.
deleted) -- which is why the seed artifact is committed alongside this module.
"""
import json
import os
import datetime
from prob_calibration import canon_market_family, market_family, CURATE_MIN_N, CURATE_MAX_NET

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "forward_test.json")
MIN_MEANINGFUL = 150  # below this many settled picks, stay "building" -- an ROI on <150 is noise
STABLE_N = 400        # below this, flag the shown number as a still-small, regressing sample


def _load_picks():
    d = json.load(open(LEDGER, encoding="utf-8"))
    return [p for p in (d.get("picks") or [])
            if p.get("settled") and p.get("result") in ("won", "lost", "push")
            and not p.get("voided")]


def _net(p):
    pu = p.get("payout_units")
    if pu is not None:
        return float(pu)
    r = p.get("result")
    return 0.91 if r == "won" else (-1.0 if r == "lost" else 0.0)


def _fams(p):
    m = p.get("market")
    return {canon_market_family(m), market_family(m)}


def _cut_set(picks):
    agg = {}
    for p in picks:
        nv = _net(p)
        for k in _fams(p):
            a = agg.setdefault(k, [0, 0.0])
            a[0] += 1
            a[1] += nv
    return sorted({k for k, (n, nt) in agg.items()
                   if n >= CURATE_MIN_N and nt <= CURATE_MAX_NET})


def _score(picks, cut):
    cutset = set(cut)
    incl = [p for p in picks if not (_fams(p) & cutset)]
    graded = [p for p in incl if p.get("result") in ("won", "lost")]
    n = len(graded)
    netu = sum(_net(p) for p in incl)
    wins = sum(1 for p in graded if p.get("result") == "won")
    return {"n": n, "net": round(netu, 1),
            "roi": round(100 * netu / n, 1) if n else 0.0,
            "hit": round(100 * wins / n, 1) if n else 0.0}


def build():
    picks = _load_picks()
    today = datetime.date.today().isoformat()

    # Reload the persisted anchor + frozen cut-set so the rule NEVER refits.
    prior = {}
    if os.path.exists(OUT):
        try:
            prior = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            prior = {}
    anchor = prior.get("anchor")
    frozen = prior.get("frozen_cut")
    if not anchor or not isinstance(frozen, list):
        # FIRST run: freeze the cut-set now on everything strictly before today.
        anchor = today
        pre = [p for p in picks if (p.get("date") or "") < anchor]
        frozen = _cut_set(pre)
        created = datetime.datetime.now().isoformat(timespec="seconds")
        pre_n = len(pre)
    else:
        created = prior.get("created_at") or anchor
        pre_n = prior.get("frozen_on_n")

    # Measure ONLY picks settled on/after the anchor, against the FROZEN cut-set.
    post = [p for p in picks if (p.get("date") or "") >= anchor]
    raw = _score(post, [])
    cur = _score(post, frozen)
    building = cur["n"] < MIN_MEANINGFUL
    small_sample = cur["n"] < STABLE_N

    if building:
        note = (f"Cut-set frozen on {anchor} ({len(frozen)} families) and never refit. "
                f"Scoring only picks settled on/after that date -- building: "
                f"{cur['n']}/{MIN_MEANINGFUL} settled so far.")
    else:
        tail = (" Still a small sample -- early prospective ROI is noisy; expect regression "
                "toward the held-out edge as it grows." if small_sample else "")
        note = (f"Cut-set frozen on {anchor} ({len(frozen)} families) and never refit. "
                f"{cur['n']} picks settled since: curated {cur['roi']:+.1f}% "
                f"vs raw {raw['roi']:+.1f}% -- zero hindsight." + tail)

    return {
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "anchor": anchor,
        "created_at": created,
        "frozen_on_n": pre_n,
        "frozen_cut_size": len(frozen),
        "frozen_cut": frozen,
        "n_settled_since": cur["n"],
        "raw_roi": raw["roi"], "raw_n": raw["n"],
        "curated_roi": cur["roi"], "curated_hit": cur["hit"], "curated_net": cur["net"],
        "building": building,
        "small_sample": small_sample,
        "min_meaningful": MIN_MEANINGFUL,
        "note": note,
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
    print(f"  anchor={p['anchor']} frozen={p['frozen_cut_size']} families | "
          f"since: n={p['n_settled_since']} curated={p['curated_roi']:+.1f}% "
          f"raw={p['raw_roi']:+.1f}% building={p['building']}")
