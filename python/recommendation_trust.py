"""
EdgeStat -- recommendation trust scoring.

Tracks the model's own track record at making suggestions. Each cron:
  1. Snapshots today's param_recommendations.json into recommendation_history.json
     (deduped by key+suggested_value so repeating the same rec doesn't double-count)
  2. For each historical recommendation, checks config_history.json to see
     if the operator APPLIED the change (key + matching new value)
  3. For applied recs, joins with override_effects.json to determine
     whether the change improved / degraded / was flat / insufficient_data
  4. Computes a "model trust score" = % of applied recs that resulted in
     'improved' verdict (out of applied recs with concluded effects)

The point: build empirical credibility for the recommender over time.
If trust score is high, Brandon can apply recommendations more confidently.
If low, the recommender needs refinement.

Output: data/recommendation_trust.json
  {
    "generated_at": "...",
    "n_total_recs": 47,             # all-time unique recommendations made
    "n_applied":    12,             # operator took the rec
    "n_ignored":    35,             # never applied
    "n_concluded":  9,              # applied recs with sufficient post-window data
    "n_improved":   6,              # of concluded, improved metrics
    "n_degraded":   1,              # of concluded, degraded metrics
    "n_flat":       2,              # of concluded, no movement
    "trust_score":  0.667,          # n_improved / n_concluded (when n_concluded >= 3)
    "tier":         "trusted",      # one of trusted / mixed / unproven
    "history": [
      {
        "first_seen_ts": "2026-05-10T10:00:00",
        "key": "calibration.n_prior_default",
        "suggested": 5,
        "severity": "medium",
        "applied_ts": "2026-05-12T13:42:00",   # null if not yet applied
        "verdict":   "improved",                # null if not yet concluded
        "brier_delta": -0.012,
        "hit_rate_delta": 0.014
      },
      ...
    ]
  }

/config surfaces a "Model Trust" pill: trust_score + tier + n_concluded.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REC_PATH = os.path.join(DATA_DIR, "param_recommendations.json")
HIST_PATH = os.path.join(DATA_DIR, "recommendation_history.json")
CFG_HIST_PATH = os.path.join(DATA_DIR, "config_history.json")
EFFECTS_PATH = os.path.join(DATA_DIR, "override_effects.json")
OUT_PATH = os.path.join(DATA_DIR, "recommendation_trust.json")

MAX_HISTORY = 200


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _hash_rec(r: Dict[str, Any]) -> str:
    """A rec is the same as a previous one if same key + same suggested value."""
    return f"{r.get('key')}|{json.dumps(r.get('suggested'), sort_keys=True)}"


def _parse_ts(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None


def run() -> Dict[str, Any]:
    today_recs = (_load(REC_PATH).get("recommendations") or [])
    history = _load(HIST_PATH).get("history") or []
    cfg_hist_entries = (_load(CFG_HIST_PATH).get("entries") or [])
    effects_changes = (_load(EFFECTS_PATH).get("changes") or [])

    now = dt.datetime.now().isoformat(timespec="seconds")

    # Build a set of (hash) for what's already in history so we don't duplicate
    seen_hashes = {h.get("hash") for h in history}
    for r in today_recs:
        h = _hash_rec(r)
        if h in seen_hashes:
            continue
        history.append({
            "hash": h,
            "first_seen_ts": now,
            "key": r.get("key"),
            "suggested": r.get("suggested"),
            "current_when_seen": r.get("current"),
            "severity": r.get("severity"),
            "direction": r.get("direction"),
            "rationale": r.get("rationale"),
            "applied_ts": None,
            "applied_value": None,
            "verdict": None,
            "brier_delta": None,
            "hit_rate_delta": None,
        })
        seen_hashes.add(h)

    history = history[-MAX_HISTORY:]

    # For each historical rec, check if config_history shows the change being applied
    # We consider a rec applied if there's an override_added/changed entry where:
    #   - key matches AND
    #   - new value == suggested value AND
    #   - timestamp >= first_seen_ts
    for rec in history:
        if rec.get("applied_ts"):
            continue
        first_seen = _parse_ts(rec.get("first_seen_ts"))
        if not first_seen:
            continue
        for e in cfg_hist_entries:
            if e.get("key") != rec.get("key"):
                continue
            e_ts = _parse_ts(e.get("ts"))
            if not e_ts or e_ts < first_seen:
                continue
            if json.dumps(e.get("new"), sort_keys=True) == json.dumps(rec.get("suggested"), sort_keys=True):
                rec["applied_ts"] = e.get("ts")
                rec["applied_value"] = e.get("new")
                break

    # For applied recs, join with override_effects to capture the verdict
    # Match on (key, applied_ts) -- both should be present in override_effects
    for rec in history:
        if not rec.get("applied_ts") or rec.get("verdict"):
            continue
        for c in effects_changes:
            if c.get("key") != rec.get("key"):
                continue
            if c.get("ts") == rec.get("applied_ts"):
                rec["verdict"] = c.get("verdict")
                rec["brier_delta"] = c.get("brier_delta")
                rec["hit_rate_delta"] = c.get("hit_rate_delta")
                break

    # Stats
    n_total = len(history)
    n_applied = sum(1 for r in history if r.get("applied_ts"))
    n_ignored = n_total - n_applied
    concluded = [r for r in history if r.get("verdict") in ("improved", "degraded", "flat")]
    n_concluded = len(concluded)
    n_improved = sum(1 for r in concluded if r["verdict"] == "improved")
    n_degraded = sum(1 for r in concluded if r["verdict"] == "degraded")
    n_flat     = sum(1 for r in concluded if r["verdict"] == "flat")

    trust_score = round(n_improved / n_concluded, 3) if n_concluded >= 3 else None
    if trust_score is None:
        tier = "unproven"
    elif trust_score >= 0.6:
        tier = "trusted"
    elif trust_score >= 0.4:
        tier = "mixed"
    else:
        tier = "unreliable"

    payload = {
        "generated_at": now,
        "n_total_recs": n_total,
        "n_applied": n_applied,
        "n_ignored": n_ignored,
        "n_concluded": n_concluded,
        "n_improved": n_improved,
        "n_degraded": n_degraded,
        "n_flat": n_flat,
        "trust_score": trust_score,
        "tier": tier,
        "history": history[-50:],   # last 50 for UI
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump({"history": history}, f, indent=2)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  total recs: {p['n_total_recs']}  applied: {p['n_applied']}  ignored: {p['n_ignored']}")
    print(f"  concluded: {p['n_concluded']}  improved: {p['n_improved']}  degraded: {p['n_degraded']}  flat: {p['n_flat']}")
    if p["trust_score"] is not None:
        print(f"  trust_score: {p['trust_score']}  tier: {p['tier']}")
    else:
        print(f"  trust_score: n/a (need {3 - p['n_concluded']} more concluded recs)  tier: {p['tier']}")
