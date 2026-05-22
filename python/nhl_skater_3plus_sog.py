"""
EdgeStat -- NHL skater 3+ shots on goal alternate.

Distinct from nhl_skater_sog_props (which targets the nearest 0.5 line, often
2.5 or 3.5). This module specifically prices the popular 3+ SOG alternate
which is common on DK at -180 to +200 for typical forwards.

Common pricing:
  - Elite shooters (Kucherov, Pastrnak, McDavid): -180 to -150 (60-64%)
  - Standard top-6 forward: -110 to +130 (45-52%)
  - Bottom-6 / defensive forward: +250 to +500 (16-29%)

Method:
  Inherit expected_sog from nhl_skater_sog_props.json. Compute P(>=3) at
  Poisson(expected_sog).

  STRONG_YES at p_3plus in [0.55, 0.75] (vs -120 book = 54.5%)
  STRONG_NO at p_no in [0.78, 0.88] (vs +180 book on NO = 35.7%, so NO is
    +180 implies p ~37%, meaning -250 on YES so p_no >= 70% = strong)

Output: data/nhl_skater_3plus_sog.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_skater_3plus_sog.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    s = sum((lam ** i) * math.exp(-lam) / math.factorial(i) for i in range(k))
    return max(0.0, min(1.0, 1.0 - s))


def run() -> Dict[str, Any]:
    src = _load(os.path.join(DATA_DIR, "nhl_skater_sog_props.json"))
    rows_in = src.get("rows") or []
    if not rows_in:
        for k in ("top_25_by_xSOG", "all_rows", "strong_edges"):
            if k in src and isinstance(src[k], list):
                rows_in = src[k]; break

    out_rows: List[Dict[str, Any]] = []
    for r in rows_in:
        if not isinstance(r, dict): continue
        # Try multiple key names for expected SOG
        xsog = r.get("expected_sog") or r.get("xSOG") or r.get("projected_sog") or r.get("lam")
        if xsog is None: continue
        try:
            xsog = float(xsog)
        except Exception:
            continue

        p_3plus = _poisson_at_least(3, xsog)
        p_4plus = _poisson_at_least(4, xsog)
        p_no = 1 - p_3plus

        edge_class = "NONE"
        best_market = None
        if 0.55 <= p_3plus <= 0.75:
            edge_class = "STRONG_YES"
            best_market = {"market": "SOG_3PLUS_YES",
                           "p": round(p_3plus, 3),
                           "fair_odds": _american(p_3plus)}
        elif 0.78 <= p_no <= 0.88:
            edge_class = "STRONG_NO"
            best_market = {"market": "SOG_3PLUS_NO",
                           "p": round(p_no, 3),
                           "fair_odds": _american(p_no)}

        out_rows.append({
            "skater": r.get("skater") or r.get("player") or r.get("name"),
            "team": r.get("team"),
            "matchup": r.get("matchup") or r.get("game") or "",
            "expected_sog": round(xsog, 2),
            "p_3plus_sog": round(p_3plus, 3),
            "p_4plus_sog": round(p_4plus, 3),
            "p_no_3plus": round(p_no, 3),
            "fair_yes_3plus": _american(p_3plus),
            "fair_no_3plus": _american(p_no),
            "fair_yes_4plus": _american(p_4plus) if p_4plus > 0.005 else None,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    out_rows.sort(key=lambda r: -r["p_3plus_sog"])
    strong = [r for r in out_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_skaters": len(out_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(expected_sog) >= 3; expected_sog inherited from "
                       "nhl_skater_sog_props. STRONG_YES p in [0.55, 0.75] vs -120 book; "
                       "STRONG_NO p_no in [0.78, 0.88]. Also exposes p_4plus alt.",
        "top_25_by_p_3plus": out_rows[:25],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nhl-sog3+] {o['n_skaters']} skaters, {o['n_strong_edges']} strong -> {OUT}")
