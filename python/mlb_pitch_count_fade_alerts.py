"""
EdgeStat -- MLB pitch count fade alerts.

Surfaces pitchers approaching their pitch ceiling who may be pulled
early, killing K/outs/QS bets:
  - Recent high pitch count (>= 105 last start)
  - Manager known for early hooks
  - Multiple recent stressful starts

Pulls from starter_pitch_count_alerts (already exists) and combines
with pitcher confluence to flag genuine concern spots.

Output: data/mlb_pitch_count_fade_alerts.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitch_count_fade_alerts.json")


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
    pitch_count = _load(os.path.join(DATA_DIR, "mlb_starter_pitch_count_alerts.json"))
    confluence = _load(os.path.join(DATA_DIR, "mlb_pitcher_confluence_score.json"))
    six_plus = _load(os.path.join(DATA_DIR, "mlb_pitcher_6plus_IP_yn.json"))
    outs = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))

    pc_idx = {_norm(r.get("pitcher")): r
              for r in (pitch_count.get("rows") or pitch_count.get("alerts") or [])
              if isinstance(r, dict)}

    conf_idx = {_norm(r.get("pitcher")): r
                for r in (confluence.get("rows") or []) if isinstance(r, dict)}

    six_plus_idx = {_norm(r.get("pitcher")): r
                    for r in (six_plus.get("rows") or []) if isinstance(r, dict)}

    outs_idx = {_norm(r.get("pitcher")): r
                for r in (outs.get("rows") or []) if isinstance(r, dict)}

    alerts: List[Dict[str, Any]] = []
    for name in (set(pc_idx) | set(conf_idx)):
        pc = pc_idx.get(name, {})
        c = conf_idx.get(name, {})
        six = six_plus_idx.get(name, {})
        o = outs_idx.get(name, {})

        recent_pc = _safe(pc.get("recent_pc") or pc.get("last_start_pc"))
        avg_pc = _safe(pc.get("avg_pc") or pc.get("season_avg_pc"))
        is_flagged = pc.get("flag") or pc.get("status")

        flags: List[str] = []
        if recent_pc >= 105:
            flags.append("RECENT_HIGH_PC")
        if avg_pc >= 95:
            flags.append("ELEVATED_AVG_PC")
        if is_flagged:
            flags.append("FLAG_FROM_TRACKER")

        # Combine with low p_6plus_IP
        p_6plus = _safe(six.get("p_6plus_IP") or six.get("p"))
        if 0 < p_6plus < 0.50:
            flags.append("LOW_6PLUS_IP")

        # Outs UNDER lean
        outs_ec = (o.get("edge_class") or "").upper()
        if "UNDER" in outs_ec:
            flags.append("OUTS_UNDER_LEAN")

        # Require at least one STRONG signal beyond tracker presence
        strong_signal_set = {"RECENT_HIGH_PC", "ELEVATED_AVG_PC", "OUTS_UNDER_LEAN"}
        has_strong = any(f in strong_signal_set for f in flags)
        if not has_strong: continue
        if len(flags) < 2: continue

        alerts.append({
            "pitcher": pc.get("pitcher") or c.get("pitcher") or name.title(),
            "team": c.get("team"),
            "matchup": c.get("matchup"),
            "recent_pc": round(recent_pc, 1) if recent_pc else None,
            "avg_pc": round(avg_pc, 1) if avg_pc else None,
            "p_6plus_IP": round(p_6plus, 3),
            "outs_edge_class": outs_ec or None,
            "n_concern_flags": len(flags),
            "flags": flags,
            "advisory": "Pitcher approaching pitch ceiling -- early hook risk. "
                        "K and outs OVER bets carry tail risk. Consider K UNDER "
                        "alt + outs UNDER.",
            "recommended_markets": [
                f"FADE {pc.get('pitcher') or c.get('pitcher')} K OVER blowout",
                "Outs UNDER",
                "Pitcher 6+ IP NO",
                "Quality start NO",
            ],
        })

    alerts.sort(key=lambda a: -a["n_concern_flags"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_alerts": len(alerts),
        "method_note": "Pitch count fade alerts. 2+ flags from RECENT_HIGH_PC "
                       "(>=105), ELEVATED_AVG_PC (>=95), FLAG_FROM_TRACKER, "
                       "LOW_6PLUS_IP, OUTS_UNDER_LEAN. Recommends K/outs UNDER "
                       "alts + 6+ IP NO + QS NO.",
        "alerts": alerts,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-pc-fade] {o['n_alerts']} alerts -> {OUT}")
