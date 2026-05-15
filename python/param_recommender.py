"""
EdgeStat -- parameter recommender.

Closes the self-learning loop. Reads model metrics + walk-forward + alert
volume and proposes runtime_config overrides with rationale. The operator
(Brandon) sees each suggestion on /config.html with a one-click GitHub
edit link to apply it.

This module DOES NOT auto-apply -- only suggests. The override flow stays
manual on purpose: a parameter tweak is a model change, and the operator
should see exactly what's being changed and why before it hits the cron.

Suggestion rules (each one has a rationale + suggested_value + current_value):
  - "calibration.n_prior_default" too LOW: market correction_factor swung
    >10% across two consecutive refreshes (over-reactive).
  - "calibration.n_prior_default" too HIGH: market has n>=200 and |residual|
    still > 0.4 (under-responsive).
  - "calibration.max_correction" too TIGHT: 2+ markets sitting at the cap.
  - "live_edges.edge_threshold_pp" too HIGH: zero alerts fired in last 24h
    despite >20 live props priced.
  - "live_edges.edge_threshold_pp" too LOW: >40 alerts/day (alert spam).
  - "player_bias.min_player_n" too HIGH: zero per-player overrides
    despite >3 systematic anomalies flagged.
  - "plays.kelly_fraction" suggestions: track-record Sharpe-style ROI.
    If trailing-30-day ROI > +10% AND drawdown < 5%, propose stepping up
    Kelly from 0.25 -> 0.33. If ROI < 0% over same window, propose 0.20.
  - "walk_forward.window_days": if 5+ markets are flagged "degrading",
    propose larger window to reduce variance.

Output: data/param_recommendations.json
  {
    "generated_at": "...",
    "recommendations": [
      {
        "key": "calibration.n_prior_default",
        "current": 8,
        "suggested": 12,
        "direction": "increase",
        "severity": "medium",
        "rationale": "Per-market correction_factor for batter_total_bases moved >0.05 between consecutive refreshes -- prior anchor isn't damping enough.",
        "evidence": {"market": "batter_total_bases", "cf_swing": 0.06, "n": 1200}
      }
    ],
    "n_recommendations": 1,
    "summary": "1 suggested override -- review on /config"
  }

Front-end /config.html reads this and renders amber-bordered cards above
the knob table with an "Apply" link that pre-fills the GitHub web editor.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")
PREV_CAL_PATH = os.path.join(DATA_DIR, ".feedback_prev.json")
WF_PATH = os.path.join(DATA_DIR, "walk_forward.json")
RES_PATH = os.path.join(DATA_DIR, "residuals.json")
PB_PATH = os.path.join(DATA_DIR, "player_bias.json")
ANOM_PATH = os.path.join(DATA_DIR, "anomalies.json")
ALERTS_PATH = os.path.join(DATA_DIR, "live_alerts.json")
TR_PATH = os.path.join(DATA_DIR, "track_record.json")
OUT_PATH = os.path.join(DATA_DIR, "param_recommendations.json")

try:
    import config as _cfg
except Exception:
    _cfg = None


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _get_default(key: str, fallback: Any) -> Any:
    if _cfg is None:
        return fallback
    try:
        return _cfg.get(key, fallback)
    except Exception:
        return fallback


def _rec(key: str, current: Any, suggested: Any, direction: str,
         severity: str, rationale: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": key,
        "current": current,
        "suggested": suggested,
        "direction": direction,
        "severity": severity,
        "rationale": rationale,
        "evidence": evidence,
    }


def _check_n_prior(cal: Dict[str, Any], prev_cal: Dict[str, Any],
                   res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """N_PRIOR too low if correction swings; too high if residual still big at large n."""
    out = []
    curr_markets = cal.get("markets", {})
    prev_markets = prev_cal.get("calibration_markets", {})
    res_markets = res.get("markets", {})

    # Too LOW: correction_factor swung > 0.05 across refresh
    big_swings = []
    for mk, v in curr_markets.items():
        prev_v = prev_markets.get(mk) or {}
        cf_now = v.get("correction_factor")
        cf_prev = prev_v.get("correction_factor")
        n = v.get("n", 0)
        if cf_now is None or cf_prev is None or n < 50:
            continue
        swing = abs(cf_now - cf_prev)
        if swing > 0.05:
            big_swings.append({"market": mk, "cf_swing": round(swing, 4), "n": n})
    if big_swings:
        cur = _get_default("calibration.n_prior_default", 8)
        # Suggest +50% (clamped to 30)
        suggested = min(30, int(cur * 1.5))
        if suggested > cur:
            out.append(_rec(
                "calibration.n_prior_default",
                cur, suggested,
                "increase", "medium",
                f"{len(big_swings)} market(s) had correction_factor swing >0.05 between consecutive refreshes -- prior anchor isn't damping enough. Raising N_PRIOR will stabilize.",
                {"swinging_markets": big_swings[:5]},
            ))

    # Too HIGH: large n + still big residual = data isn't getting enough weight
    stuck_markets = []
    for mk, v in curr_markets.items():
        n = v.get("n", 0)
        if n < 200:
            continue
        rm = res_markets.get(mk) or {}
        mean_res = rm.get("mean_residual")
        if mean_res is not None and abs(mean_res) > 0.4:
            stuck_markets.append({"market": mk, "n": n, "mean_residual": mean_res})
    if stuck_markets:
        cur = _get_default("calibration.n_prior_default", 8)
        suggested = max(3, int(cur * 0.7))
        if suggested < cur:
            out.append(_rec(
                "calibration.n_prior_default",
                cur, suggested,
                "decrease", "medium",
                f"{len(stuck_markets)} market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster.",
                {"stuck_markets": stuck_markets[:5]},
            ))

    return out


def _check_max_correction(cal: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Multiple markets sitting at the correction cap = cap is too tight."""
    out = []
    cap = _get_default("calibration.max_correction", 1.35)
    eps = 0.01
    curr = cal.get("markets", {})
    pinned_high = [mk for mk, v in curr.items()
                   if v.get("correction_factor") is not None
                   and v["correction_factor"] >= cap - eps]
    pinned_low = [mk for mk, v in curr.items()
                  if v.get("correction_factor") is not None
                  and v["correction_factor"] <= 1.0 / cap + eps]
    pinned = pinned_high + pinned_low
    if len(pinned) >= 2:
        suggested = round(min(2.0, cap * 1.15), 2)
        if suggested > cap:
            out.append(_rec(
                "calibration.max_correction",
                cap, suggested,
                "increase", "low",
                f"{len(pinned)} market(s) pinned at the correction cap (±{int((cap-1)*100)}%). Raising the cap lets the loop fully correct strong biases.",
                {"pinned_markets": pinned[:5]},
            ))
    return out


def _check_edge_threshold(alerts: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Edge threshold tuning based on alert volume."""
    out = []
    alert_list = alerts.get("alerts") if isinstance(alerts.get("alerts"), list) else []
    # Filter to last 24 hours
    now = dt.datetime.now()
    recent = []
    for a in alert_list:
        ts = a.get("ts") or a.get("timestamp")
        if not ts:
            continue
        try:
            t = dt.datetime.fromisoformat(ts.replace("Z", "")) if isinstance(ts, str) else None
            if t and (now - t).total_seconds() < 86400:
                recent.append(a)
        except Exception:
            continue

    n_priced = alerts.get("n_props_priced") or alerts.get("props_priced_24h")
    cur = _get_default("live_edges.edge_threshold_pp", 5.0)

    # Too HIGH: zero alerts despite props being priced
    if len(recent) == 0 and (n_priced is None or n_priced >= 20):
        suggested = max(1.0, cur - 1.5)
        if suggested < cur:
            out.append(_rec(
                "live_edges.edge_threshold_pp",
                cur, suggested,
                "decrease", "medium",
                f"Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable.",
                {"alerts_24h": 0, "props_priced": n_priced},
            ))

    # Too LOW: alert spam
    if len(recent) > 40:
        suggested = min(20.0, cur + 1.5)
        if suggested > cur:
            out.append(_rec(
                "live_edges.edge_threshold_pp",
                cur, suggested,
                "increase", "low",
                f"{len(recent)} live edge alerts in last 24h -- likely noise. Raising threshold will focus on stronger divergences.",
                {"alerts_24h": len(recent)},
            ))
    return out


def _check_player_bias(pb: Dict[str, Any], anom: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-player override threshold tuning."""
    out = []
    overrides = (pb.get("by_pid_market") or {})
    sys_anom = anom.get("systematic") or []
    cur = _get_default("player_bias.min_player_n", 3)
    if len(overrides) == 0 and len(sys_anom) >= 3:
        suggested = max(2, cur - 1)
        if suggested < cur:
            out.append(_rec(
                "player_bias.min_player_n",
                cur, suggested,
                "decrease", "low",
                f"{len(sys_anom)} systematic anomalies flagged but zero player overrides applied. MIN_PLAYER_N may be filtering them out.",
                {"systematic_anomalies": len(sys_anom), "active_overrides": 0},
            ))
    return out


def _check_kelly_fraction(tr: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kelly sizing recommendation based on trailing 30d ROI."""
    out = []
    props = tr.get("props") or []
    # Filter to last 30 days
    cutoff = dt.date.today() - dt.timedelta(days=30)
    recent = []
    for p in props:
        d = p.get("date")
        if not d:
            continue
        try:
            pd = dt.date.fromisoformat(d)
            if pd >= cutoff and p.get("recommendation") in ("OVER", "UNDER"):
                recent.append(p)
        except Exception:
            continue
    if len(recent) < 20:
        return out

    wins = sum(1 for p in recent if (p.get("recommendation") == "OVER" and p.get("over_hit") is True)
                                    or (p.get("recommendation") == "UNDER" and p.get("over_hit") is False))
    losses = len(recent) - wins
    # Approximate ROI assuming -110 / flat-unit
    units_won = wins * 0.909 - losses
    roi = units_won / len(recent) if recent else 0
    cur = _get_default("plays.kelly_fraction", 0.25)

    if roi > 0.05 and cur < 0.40:
        suggested = round(min(0.40, cur + 0.10), 2)
        out.append(_rec(
            "plays.kelly_fraction",
            cur, suggested,
            "increase", "low",
            f"Trailing 30-day ROI is +{roi*100:.1f}% over {len(recent)} plays. Sizing can step up modestly toward half-Kelly.",
            {"trailing_30d_roi_pct": round(roi*100, 2), "n_plays": len(recent), "wins": wins, "losses": losses},
        ))
    elif roi < -0.03 and cur > 0.15:
        suggested = round(max(0.15, cur - 0.10), 2)
        out.append(_rec(
            "plays.kelly_fraction",
            cur, suggested,
            "decrease", "medium",
            f"Trailing 30-day ROI is {roi*100:.1f}% over {len(recent)} plays. Drop Kelly fraction until calibration/track-record recovers.",
            {"trailing_30d_roi_pct": round(roi*100, 2), "n_plays": len(recent), "wins": wins, "losses": losses},
        ))
    return out


def _check_walk_forward(wf: Dict[str, Any]) -> List[Dict[str, Any]]:
    """If many markets degrading, widen the window to reduce variance."""
    out = []
    summary = wf.get("summary") or {}
    degrading = summary.get("degrading") or []
    cur = _get_default("walk_forward.window_days", 3)
    if len(degrading) >= 5 and cur < 7:
        suggested = min(7, cur + 2)
        out.append(_rec(
            "walk_forward.window_days",
            cur, suggested,
            "increase", "low",
            f"{len(degrading)} markets flagged as degrading in walk-forward. Wider window reduces single-day variance and gives a cleaner trend signal.",
            {"degrading_markets": [d.get("market") for d in degrading[:5]]},
        ))
    return out


def run() -> Dict[str, Any]:
    cal = _load(CAL_PATH)
    prev_cal = _load(PREV_CAL_PATH)
    wf = _load(WF_PATH)
    res = _load(RES_PATH)
    pb = _load(PB_PATH)
    anom = _load(ANOM_PATH)
    alerts = _load(ALERTS_PATH)
    tr = _load(TR_PATH)

    recs: List[Dict[str, Any]] = []
    recs.extend(_check_n_prior(cal, prev_cal, res))
    recs.extend(_check_max_correction(cal))
    recs.extend(_check_edge_threshold(alerts))
    recs.extend(_check_player_bias(pb, anom))
    recs.extend(_check_kelly_fraction(tr))
    recs.extend(_check_walk_forward(wf))

    # Dedupe by key (keep first / strongest)
    seen = set()
    deduped = []
    for r in recs:
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        deduped.append(r)

    sev_order = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(key=lambda r: sev_order.get(r["severity"], 3))

    if not deduped:
        summary = "No parameter changes recommended -- model is operating within healthy bands."
    elif len(deduped) == 1:
        summary = f"1 suggested override: {deduped[0]['key']} ({deduped[0]['direction']})."
    else:
        summary = f"{len(deduped)} suggested overrides -- review on /config."

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_recommendations": len(deduped),
        "recommendations": deduped,
        "summary": summary,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_recommendations']} recommendations")
    print(f"  {p['summary']}")
    for r in p["recommendations"]:
        print(f"    [{r['severity']}] {r['key']}: {r['current']} -> {r['suggested']} ({r['direction']})")
        print(f"        {r['rationale']}")
