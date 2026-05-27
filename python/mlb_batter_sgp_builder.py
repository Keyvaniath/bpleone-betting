"""
EdgeStat -- MLB batter same-game parlay (SGP) builder.

For each MLB batter with confluence_score >= 10 (STRONG+), builds the
recommended SGP from their OVER signals:
  - HR YES (if p_hr >= 18%)
  - 2+ Hits YES (if p_2plus >= 40%)
  - 1+ RBI YES (if p_rbi >= 50%)
  - 1+ Hit YES (if p_hit >= 75%)
  - 3+ TB YES (if p_tb3 >= 22%)
  - Total Bases OVER (if signaled)

Apply 1.20x correlation boost since MLB batter props are very tightly
correlated (HR = TB OVER = 3+ TB likely all hit together).

Output: data/mlb_batter_sgp_builder.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_sgp_builder.json")


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


def _is_over(ec: str) -> bool:
    return "OVER" in (ec or "").upper()


def run() -> Dict[str, Any]:
    confluence = _load(os.path.join(DATA_DIR, "mlb_batter_confluence_score.json"))
    hr = _load(os.path.join(DATA_DIR, "mlb_to_hit_hr_yn.json"))
    hits_2 = _load(os.path.join(DATA_DIR, "mlb_batter_2plus_hits_props.json"))
    rbi = _load(os.path.join(DATA_DIR, "mlb_batter_rbi_props.json"))
    hit_yn = _load(os.path.join(DATA_DIR, "mlb_to_record_hit_yn.json"))
    tb_3 = _load(os.path.join(DATA_DIR, "mlb_batter_3plus_tb_props.json"))
    tb = _load(os.path.join(DATA_DIR, "mlb_total_bases_props.json"))

    def _prob_idx(src, p_field):
        idx: Dict[str, float] = {}
        for k in ("rows", "top_25_by_p_hr", "top_25_by_p_2plus",
                  "top_25_by_p_rbi", "top_25_by_p_hit",
                  "top_25_by_p_tb3", "strong_edges"):
            for r in (src.get(k) or []):
                if isinstance(r, dict):
                    key = _norm(r.get("batter") or r.get("player") or "")
                    if key and key not in idx:
                        idx[key] = _safe(r.get(p_field) or r.get("p"))
        return idx

    hr_idx = _prob_idx(hr, "p_hr")
    hits2_idx = _prob_idx(hits_2, "p_2plus")
    rbi_idx = _prob_idx(rbi, "p_rbi")
    hit_idx = _prob_idx(hit_yn, "p_hit")
    tb3_idx = _prob_idx(tb_3, "p_tb3")

    tb_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tb.get("rows") or []):
        if isinstance(r, dict):
            key = _norm(r.get("batter") or r.get("player") or "")
            if key:
                tb_idx[key] = r

    parlays: List[Dict[str, Any]] = []
    for r in (confluence.get("rows") or []):
        if not isinstance(r, dict): continue
        score = _safe(r.get("composite_score"))
        if score < 10: continue

        name = _norm(r.get("batter") or "")
        legs: List[Dict[str, Any]] = []

        p_hr = hr_idx.get(name, 0)
        if p_hr >= 0.18:
            legs.append({"market": "HR YES", "p": round(p_hr, 3)})

        p_2plus = hits2_idx.get(name, 0)
        if p_2plus >= 0.40:
            legs.append({"market": "2+ Hits YES", "p": round(p_2plus, 3)})

        p_rbi = rbi_idx.get(name, 0)
        if p_rbi >= 0.50:
            legs.append({"market": "1+ RBI YES", "p": round(p_rbi, 3)})

        p_hit = hit_idx.get(name, 0)
        if p_hit >= 0.75:
            legs.append({"market": "1+ Hit YES", "p": round(p_hit, 3)})

        p_tb3 = tb3_idx.get(name, 0)
        if p_tb3 >= 0.22:
            legs.append({"market": "3+ TB YES", "p": round(p_tb3, 3)})

        if _is_over(tb_idx.get(name, {}).get("edge_class") or ""):
            legs.append({"market": "Total Bases OVER", "p": 0.55})

        if len(legs) < 2: continue

        parlay_p_naive = 1.0
        for leg in legs:
            parlay_p_naive *= leg["p"]

        parlay_p_corr = min(parlay_p_naive * 1.20, 0.99)

        parlays.append({
            "batter": r.get("batter"),
            "team": r.get("team"),
            "matchup": r.get("matchup"),
            "confluence_score": round(score, 2),
            "n_legs": len(legs),
            "legs": legs,
            "parlay_p_naive": round(parlay_p_naive, 4),
            "parlay_p_correlated": round(parlay_p_corr, 4),
            "advisory": "Same-batter SGP. HR / TB / RBI / hits are highly "
                        "correlated -> apply 1.20x boost to naive parlay p.",
        })

    parlays.sort(key=lambda p: -p["parlay_p_correlated"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_parlays": len(parlays),
        "method_note": "MLB batter SGP builder. Confluence >= 10 + OVER + "
                       "threshold signals across HR/2+ hits/1+ RBI/1+ hit/3+ "
                       "TB/TB OVER. 1.20x correlation boost (high correlation).",
        "parlays": parlays,
        "top_15": parlays[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-batter-sgp] {o['n_parlays']} SGP builds -> {OUT}")
