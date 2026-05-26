"""
EdgeStat -- MLB pitcher 'blowup' alert (4+ ER allowed yes/no).

DK alt: 'Pitcher to allow 4+ ER yes/no'. Common pricing:
  - Vulnerable starter in tough matchup: +130 to +200 YES
  - Avg starter: +250 to +350 YES
  - Ace: +400+

Method:
  Pull expected_er from mlb_pitcher_er_props or derive from
  ERA * expected_IP / 9. P(>= 4 ER) via Poisson.

  STRONG_YES at p in [0.28, 0.45] (vs +200 book = 33.3%)

Output: data/mlb_pitcher_blowup_alert.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_blowup_alert.json")


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    er_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_er_props.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    outs_props = _load(os.path.join(DATA_DIR, "mlb_pitcher_outs_props.json"))

    er_idx = {(r.get("pitcher") or "").lower(): r
              for r in (er_props.get("rows") or []) if isinstance(r, dict)}
    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    outs_idx = {(r.get("pitcher") or "").lower(): r
                for r in (outs_props.get("rows") or []) if isinstance(r, dict)}

    matchups_data = _load(os.path.join(DATA_DIR, "matchups.json"))
    games = matchups_data.get("games") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        matchup = g.get("matchup") or ""
        for side, sp_field in (("HOME", "home_pitcher"), ("AWAY", "away_pitcher")):
            sp_raw = g.get(sp_field)
            sp_name = sp_raw if isinstance(sp_raw, str) else (sp_raw or {}).get("name")
            if not sp_name: continue
            sp_l = sp_name.lower()
            er_row = er_idx.get(sp_l, {})
            expected_er = _safe(er_row.get("expected_er") or er_row.get("xER"))
            if expected_er <= 0:
                # Fallback from ERA + IP
                sp_row = p_by_name.get(sp_l, {})
                stats = sp_row.get("stats") or {}
                era = _safe(stats.get("era"), 4.20)
                x_outs = _safe(outs_idx.get(sp_l, {}).get("expected_outs"), 16.0)
                expected_er = (era / 9.0) * (x_outs / 3.0)

            p_4plus = _poisson_at_least(4, expected_er)
            p_5plus = _poisson_at_least(5, expected_er)
            p_no_4plus = 1 - p_4plus

            edge_class = "NONE"
            best_market = None
            if 0.28 <= p_4plus <= 0.45:
                edge_class = "STRONG_BLOWUP_YES"
                best_market = {"market": "PITCHER_4PLUS_ER_YES",
                               "p": round(p_4plus, 3),
                               "fair_odds": _american(p_4plus)}

            rows.append({
                "matchup": matchup,
                "side": side,
                "pitcher": sp_name,
                "team": (p_by_name.get(sp_l, {})).get("team_abbr"),
                "expected_er": round(expected_er, 2),
                "p_4plus_ER": round(p_4plus, 3),
                "p_5plus_ER": round(p_5plus, 3),
                "p_no_4plus_ER": round(p_no_4plus, 3),
                "fair_yes_4plus": _american(p_4plus),
                "fair_no_4plus": _american(p_no_4plus),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_4plus_ER"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_pitchers": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(>=4 ER allowed) via Poisson(expected_er). Inherits "
                       "expected_er from mlb_pitcher_er_props, falls back to "
                       "ERA*IP/9. STRONG_BLOWUP_YES p in [0.28, 0.45] vs +200 book.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[blowup] {o['n_pitchers']} pitchers, {o['n_strong_edges']} strong -> {OUT}")
