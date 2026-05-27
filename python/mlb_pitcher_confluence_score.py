"""
EdgeStat -- MLB pitcher confluence score (composite ranking).

Single composite score per pitcher derived from all pitcher synthesizers:
  - mlb_pitcher_edge_composite (base edge composite)
  - mlb_dominant_outing_alerts (positive signal count)
  - mlb_pitcher_fade_alerts (negative signal count -- subtracts)
  - mlb_pitcher_lineup_adjusted (K/outs/ER deltas)
  - mlb_pitcher_form_tracker (form trend)
  - mlb_pitcher_recent_vs_lineup_quality (recent form vs lineup quality)

Score formula:
  positive = dominant_signals * 2 + form_score
  negative = fade_signals * 2
  score = edge_composite + positive - negative + matchup_delta

PITCHER_LOCK = score >= 12; PITCHER_STRONG = 8-11; PITCHER_NEUTRAL = 4-7;
PITCHER_FADE = < 4.

Output: data/mlb_pitcher_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    edge = _load(os.path.join(DATA_DIR, "mlb_pitcher_edge_composite.json"))
    dom = _load(os.path.join(DATA_DIR, "mlb_dominant_outing_alerts.json"))
    fade = _load(os.path.join(DATA_DIR, "mlb_pitcher_fade_alerts.json"))
    lineup_adj = _load(os.path.join(DATA_DIR, "mlb_pitcher_lineup_adjusted.json"))
    form = _load(os.path.join(DATA_DIR, "mlb_pitcher_form_tracker.json"))
    recent = _load(os.path.join(DATA_DIR, "mlb_pitcher_recent_vs_lineup_quality.json"))

    # Build pitcher indexes
    edge_idx = {_norm(r.get("pitcher")): r for r in (edge.get("rows") or []) if isinstance(r, dict)}
    dom_idx = {_norm(a.get("pitcher")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}
    fade_idx = {_norm(a.get("pitcher")): a for a in (fade.get("alerts") or []) if isinstance(a, dict)}
    lineup_idx = {_norm(r.get("pitcher")): r for r in (lineup_adj.get("rows") or []) if isinstance(r, dict)}
    form_idx = {_norm(r.get("pitcher")): r for r in (form.get("rows") or []) if isinstance(r, dict)}
    recent_idx = {_norm(r.get("pitcher")): r for r in (recent.get("rows") or []) if isinstance(r, dict)}

    all_pitchers = (set(edge_idx) | set(dom_idx) | set(fade_idx)
                    | set(lineup_idx) | set(form_idx) | set(recent_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_pitchers:
        e = edge_idx.get(name, {})
        d = dom_idx.get(name, {})
        f = fade_idx.get(name, {})
        l = lineup_idx.get(name, {})
        fr = form_idx.get(name, {})
        rcnt = recent_idx.get(name, {})

        edge_score = _safe(e.get("score") or e.get("composite_score") or e.get("edge_score"))
        dom_signals = int(d.get("n_positive_signals", 0) or 0)
        fade_signals = int(f.get("n_negative_signals", 0) or 0)

        # Lineup-adjusted K delta (positive = better)
        delta_K = _safe((l.get("delta") or {}).get("K"))

        # Form: positive trend => higher
        form_class = (fr.get("trend") or fr.get("form") or "").upper()
        form_score = 1 if "HOT" in form_class or "POSITIVE" in form_class else (
            -1 if "COLD" in form_class or "NEGATIVE" in form_class else 0)

        # Recent vs lineup quality
        recent_score = _safe(rcnt.get("composite") or rcnt.get("score"))

        positive = dom_signals * 2 + max(form_score, 0) + max(delta_K * 2, 0)
        negative = fade_signals * 2 + max(-form_score, 0) + max(-delta_K * 2, 0)
        score = edge_score + positive - negative + recent_score

        # Baseline edge_composite ~60. Require a secondary signal aligned in the
        # positive direction to elevate above NEUTRAL. Form / dom signals / lineup
        # delta must STRICTLY positive (not just non-negative).
        has_secondary_lock_signal = (dom_signals >= 4
                                     or form_score > 0
                                     or delta_K >= 0.5
                                     or recent_score > 2)
        has_secondary_strong_signal = (dom_signals >= 2
                                       or form_score > 0
                                       or delta_K >= 0.2
                                       or recent_score > 0.5)

        if score >= 72 and has_secondary_lock_signal:
            tier = "PITCHER_LOCK"
        elif score >= 62 and has_secondary_strong_signal:
            tier = "PITCHER_STRONG"
        elif score <= 35 or (fade_signals >= 4):
            tier = "PITCHER_FADE"
        else:
            tier = "PITCHER_NEUTRAL"

        rows.append({
            "pitcher": (e.get("pitcher") or d.get("pitcher") or f.get("pitcher")
                        or l.get("pitcher") or fr.get("pitcher")
                        or rcnt.get("pitcher") or name.title()),
            "matchup": (e.get("matchup") or d.get("matchup") or l.get("matchup")
                        or fr.get("matchup") or ""),
            "team": e.get("team") or d.get("team") or l.get("team"),
            "edge_score": round(edge_score, 2),
            "dom_signals": dom_signals,
            "fade_signals": fade_signals,
            "delta_K_lineup_adj": round(delta_K, 2),
            "form_class": form_class or None,
            "recent_score": round(recent_score, 2),
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "PITCHER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "PITCHER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "PITCHER_FADE"),
        "method_note": "Composite per-pitcher score from edge_composite + "
                       "dom_signals*2 - fade_signals*2 + max(0,form_score) + "
                       "max(0,delta_K*2) - max(0,negative) + recent_score. "
                       "LOCK >= 12; STRONG 8-11; NEUTRAL 4-7; FADE < 4.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "PITCHER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "PITCHER_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-confluence] {o['n_pitchers']} pitchers "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
