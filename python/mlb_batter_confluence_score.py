"""
EdgeStat -- MLB batter confluence score.

Counterpart to mlb_pitcher_confluence_score. Composite per-batter score
combining:
  - mlb_batter_explosion_alerts (n_aligned_overs)
  - mlb_batter_heat (HOT/COLD)
  - mlb_to_hit_hr_yn (p_hr)
  - mlb_total_bases_props (xTB edge)
  - mlb_batter_strikeout_props (K UNDER -- positive bat)

Score formula:
  positive = ceiling_overs * 2 + max(form_score, 0) + p_hr * 30 + tb_edge
  negative = max(-form_score, 0) + k_under_signal * (-1) (K_OVER is bad)
  score = positive - negative

BATTER_LOCK = score >= 14 with ceiling >= 4; STRONG = 10-13; FADE = score
<= 2 or 4+ K_OVER signals.

Output: data/mlb_batter_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_confluence_score.json")


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
    explosion = _load(os.path.join(DATA_DIR, "mlb_batter_explosion_alerts.json"))
    heat = _load(os.path.join(DATA_DIR, "mlb_batter_heat.json"))
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    tb = _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json"))
    k_props = _load(os.path.join(DATA_DIR, "mlb_batter_strikeout_props.json"))

    expl_idx = {_norm(a.get("batter")): a for a in (explosion.get("alerts") or []) if isinstance(a, dict)}

    heat_idx: Dict[str, str] = {}
    for k in ("hot", "cold", "heating_up", "cooling_down", "rows"):
        for r in (heat.get(k) or []):
            if isinstance(r, dict):
                heat_idx[_norm(r.get("batter") or r.get("player") or "")] = (
                    r.get("trend") or k).upper()

    hr_idx: Dict[str, float] = {}
    for k in ("rows", "top_25_by_p_hr", "strong_edges"):
        for r in (hr.get(k) or []):
            if isinstance(r, dict):
                key = _norm(r.get("batter") or r.get("player") or "")
                if key and key not in hr_idx:
                    hr_idx[key] = _safe(r.get("p_hr") or r.get("p"))

    tb_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tb.get("rows") or []):
        if not isinstance(r, dict): continue
        tb_idx[_norm(r.get("batter") or r.get("player") or "")] = r

    k_idx: Dict[str, Dict[str, Any]] = {}
    for r in (k_props.get("rows") or []):
        if not isinstance(r, dict): continue
        k_idx[_norm(r.get("batter") or r.get("player") or "")] = r

    all_batters = (set(expl_idx) | set(heat_idx) | set(hr_idx)
                   | set(tb_idx) | set(k_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_batters:
        e = expl_idx.get(name, {})
        h_trend = heat_idx.get(name, "")
        p_hr = hr_idx.get(name, 0)
        tbr = tb_idx.get(name, {})
        kr = k_idx.get(name, {})

        ceiling_overs = int(e.get("n_aligned_overs", 0) or 0)
        tb_edge = _safe(tbr.get("edge_pp") or tbr.get("edge")) * 100
        k_edge_class = (kr.get("edge_class") or "").upper()
        k_over_neg = 1 if "OVER" in k_edge_class else 0  # K_OVER is negative for batter

        form_score = 0
        if "HOT" in h_trend or "HEATING" in h_trend:
            form_score = 1
        elif "COLD" in h_trend or "COOLING" in h_trend:
            form_score = -1

        positive = ceiling_overs * 2 + max(form_score, 0) + p_hr * 30 + max(tb_edge, 0)
        negative = max(-form_score, 0) + k_over_neg * 1.5 + max(-tb_edge, 0)
        score = positive - negative

        # Require at least one piece of real data to classify FADE/STRONG/LOCK.
        # Otherwise it's NO_DATA -- batter wasn't projected in any synthesizer.
        has_data = (ceiling_overs > 0 or p_hr > 0 or abs(tb_edge) > 0
                    or k_edge_class not in ("", "NONE") or h_trend)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 14 and ceiling_overs >= 4:
            tier = "BATTER_LOCK"
        elif score >= 10:
            tier = "BATTER_STRONG"
        elif k_over_neg >= 1 and form_score < 0:
            tier = "BATTER_FADE"
        elif form_score < 0 and ceiling_overs == 0 and score <= 0:
            tier = "BATTER_FADE"
        else:
            tier = "BATTER_NEUTRAL"

        rows.append({
            "batter": (e.get("batter") or tbr.get("batter") or tbr.get("player")
                       or kr.get("batter") or kr.get("player") or name.title()),
            "team": e.get("team") or tbr.get("team") or kr.get("team"),
            "matchup": (e.get("matchup") or tbr.get("matchup") or kr.get("matchup")
                        or ""),
            "ceiling_overs": ceiling_overs,
            "p_hr": round(p_hr, 3),
            "tb_edge_pp": round(tb_edge, 2),
            "k_edge_class": k_edge_class or None,
            "form": h_trend or None,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    rows_with_data = [r for r in rows if r["tier"] != "NO_DATA"]
    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_batters": len(rows),
        "n_with_data": len(rows_with_data),
        "n_lock": sum(1 for r in rows if r["tier"] == "BATTER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "BATTER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "BATTER_FADE"),
        "method_note": "Composite MLB batter score. ceiling_overs*2 + p_hr*30 + "
                       "tb_edge_pp + max(form_score,0) - k_over_penalty(1.5). "
                       "LOCK >= 14 with ceiling >= 4; STRONG 10-13; "
                       "FADE = score <=2 or K_OVER with score <6.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "BATTER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "BATTER_FADE"],
        "top_25": rows[:25],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[batter-confluence] {o['n_batters']} batters "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
