"""
Prospective forward-test -- the no-hindsight capstone.

validate_curation_oos splits the EXISTING ledger train/test, so the "test"
window already existed when the split was drawn (quasi-out-of-sample). This module
is stricter: it FREEZES the curation cut-set on data up to a fixed ANCHOR date --
set ONCE, the first time this runs and then persisted -- and scores ONLY picks
settled on/after that anchor. Every measured outcome postdates the frozen rule, so
there is zero hindsight. It starts near-empty and accrues daily; that is the point.

The anchors + frozen cut-sets live in data/forward_test.json and are reloaded every
run so the rules never refit. It re-anchors only if that artifact is missing (e.g.
deleted) -- which is why the seed artifact is committed alongside this module.

LADDER (added 2026-07-02, once experiment #1 crossed STABLE_N): instead of one
frozen experiment, this now maintains a WALK-FORWARD LADDER of them. When the newest
rung has matured (>= STABLE_N settled) and is >= MIN_GAP_DAYS old, the next run
auto-freezes a NEW rung with the cut-set derived from all data before that day. Each
rung is scored forever against its own frozen rule on picks settled on/after its own
anchor. Over time this becomes a track record OF THE METHOD -- repeated, independent
zero-hindsight validations -- rather than one possibly-lucky window. Top-level fields
keep mirroring rung #1 (the longest history) for front-end compatibility.
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
MIN_GAP_DAYS = 7      # never freeze rungs closer together than this
MAX_RUNGS = 12        # keep the artifact + card bounded (~ a season of rungs)


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


def _days_between(a, b):
    try:
        return (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    except Exception:
        return 0


def build():
    picks = _load_picks()
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().isoformat(timespec="seconds")

    # Reload persisted state so the frozen rules NEVER refit.
    prior = {}
    if os.path.exists(OUT):
        try:
            prior = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            prior = {}

    # --- assemble the ladder's FROZEN state (anchors + cut-sets only) ---
    experiments = []
    for e in (prior.get("experiments") or []):
        if e.get("anchor") and isinstance(e.get("frozen_cut"), list):
            experiments.append({"anchor": e["anchor"],
                                "created_at": e.get("created_at") or e["anchor"],
                                "frozen_on_n": e.get("frozen_on_n"),
                                "frozen_cut": e["frozen_cut"]})
    # migrate the original single-anchor artifact into rung #1
    if not experiments and prior.get("anchor") and isinstance(prior.get("frozen_cut"), list):
        experiments.append({"anchor": prior["anchor"],
                            "created_at": prior.get("created_at") or prior["anchor"],
                            "frozen_on_n": prior.get("frozen_on_n"),
                            "frozen_cut": prior["frozen_cut"]})
    experiments.sort(key=lambda e: e["anchor"])

    # --- auto-freeze the next rung when the newest one has matured ---
    def _n_since(exp):
        return _score([p for p in picks if (p.get("date") or "") >= exp["anchor"]],
                      exp["frozen_cut"])["n"]
    newest = experiments[-1] if experiments else None
    should_freeze = (
        newest is None
        or (newest["anchor"] < today
            and _days_between(newest["anchor"], today) >= MIN_GAP_DAYS
            and _n_since(newest) >= STABLE_N
            and len(experiments) < MAX_RUNGS)
    )
    if should_freeze:
        pre = [p for p in picks if (p.get("date") or "") < today]
        experiments.append({"anchor": today, "created_at": now,
                            "frozen_on_n": len(pre), "frozen_cut": _cut_set(pre)})

    # --- score every rung against its own frozen rule, zero hindsight ---
    scored = []
    for e in experiments:
        post = [p for p in picks if (p.get("date") or "") >= e["anchor"]]
        raw = _score(post, [])
        cur = _score(post, e["frozen_cut"])
        scored.append({**e,
                       "frozen_cut_size": len(e["frozen_cut"]),
                       "n_settled_since": cur["n"],
                       "raw_roi": raw["roi"], "raw_n": raw["n"],
                       "curated_roi": cur["roi"], "curated_hit": cur["hit"],
                       "curated_net": cur["net"],
                       "building": cur["n"] < MIN_MEANINGFUL,
                       "small_sample": cur["n"] < STABLE_N})

    # rung #1 (longest history) stays the flagship number + the top-level mirror
    head = scored[0]
    anchor, frozen = head["anchor"], head["frozen_cut"]
    cur_n, cur_roi, raw_roi = head["n_settled_since"], head["curated_roi"], head["raw_roi"]
    n_beat = sum(1 for e in scored
                 if not e["building"] and e["curated_roi"] > e["raw_roi"])
    n_meaningful = sum(1 for e in scored if not e["building"])

    if head["building"]:
        note = (f"Cut-set frozen on {anchor} ({len(frozen)} families) and never refit. "
                f"Scoring only picks settled on/after that date -- building: "
                f"{cur_n}/{MIN_MEANINGFUL} settled so far.")
    else:
        tail = (" Still a small sample -- early prospective ROI is noisy; expect regression "
                "toward the held-out edge as it grows." if head["small_sample"] else "")
        note = (f"Cut-set frozen on {anchor} ({len(frozen)} families) and never refit. "
                f"{cur_n} picks settled since: curated {cur_roi:+.1f}% "
                f"vs raw {raw_roi:+.1f}% -- zero hindsight." + tail)

    return {
        "updated_at": now,
        "anchor": anchor,
        "created_at": head["created_at"],
        "frozen_on_n": head["frozen_on_n"],
        "frozen_cut_size": head["frozen_cut_size"],
        "frozen_cut": frozen,
        "n_settled_since": cur_n,
        "raw_roi": raw_roi, "raw_n": head["raw_n"],
        "curated_roi": cur_roi, "curated_hit": head["curated_hit"],
        "curated_net": head["curated_net"],
        "building": head["building"],
        "small_sample": head["small_sample"],
        "min_meaningful": MIN_MEANINGFUL,
        "note": note,
        # the walk-forward ladder
        "experiments": scored,
        "n_experiments": len(scored),
        "ladder_beat_raw": n_beat,
        "ladder_meaningful": n_meaningful,
        "ladder_note": ("Walk-forward ladder: a NEW cut-set is frozen (never refit) each time the "
                        f"newest rung matures (>= {STABLE_N} settled, >= {MIN_GAP_DAYS}d apart). Each rung is "
                        "scored only on picks settled after its own anchor -- repeated, independent "
                        "zero-hindsight validations of the method, not one window."),
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
    print(f"  ladder: {p['n_experiments']} rung(s), {p['ladder_beat_raw']}/{p['ladder_meaningful']} "
          f"meaningful rungs beat raw")
    for e in p["experiments"]:
        print(f"  rung {e['anchor']}: cut={e['frozen_cut_size']} | n={e['n_settled_since']} "
              f"curated={e['curated_roi']:+.1f}% raw={e['raw_roi']:+.1f}% "
              f"{'(building)' if e['building'] else ('(small)' if e['small_sample'] else '')}")
