"""
EdgeStat -- Soccer goals & BTTS board.

Pure-model (no book line). Reads the soccer match confluence feed and
surfaces per-match goals/BTTS leans from the model's own probabilities:

  BTTS lean   p_btts_yes >= 0.58 -> BTTS YES; <= 0.42 -> BTTS NO
  total lean  goals_edge == STRONG_TOTAL -> OVER team goals
  conviction  blend of composite + distance of p_btts from 0.50

Skips matches with no signal (no BTTS prob AND no goals edge) so the
board stays clean. Fills the (currently empty) BTTS props slot.

Output: data/soccer_goals_btts_board.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_goals_btts_board.json")


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


def run() -> Dict[str, Any]:
    conf = _load(os.path.join(DATA_DIR, "soccer_match_confluence_score.json"))

    rows: List[Dict[str, Any]] = []
    for m in (conf.get("rows") or []):
        if not isinstance(m, dict): continue
        match = m.get("match")
        if not match: continue

        p_btts = _safe(m.get("p_btts_yes"))
        goals_edge = (m.get("goals_edge") or "NONE").upper()
        composite = _safe(m.get("composite_score"))
        has_btts = p_btts > 0.0
        has_total = goals_edge not in ("NONE", "")

        # No usable signal -> skip
        if not has_btts and not has_total:
            continue

        # BTTS lean
        if has_btts and p_btts >= 0.58:
            btts_lean = "BTTS YES"
        elif has_btts and p_btts <= 0.42:
            btts_lean = "BTTS NO"
        else:
            btts_lean = "BTTS neutral" if has_btts else None

        total_lean = "OVER total goals" if goals_edge == "STRONG_TOTAL" else None

        # Conviction: composite + how far BTTS prob sits from a coin flip
        btts_conf = abs(p_btts - 0.50) * 100 if has_btts else 0.0
        conviction = round(min(100.0, composite + btts_conf
                               + (12 if total_lean else 0)), 1)

        markets: List[str] = []
        if btts_lean and btts_lean != "BTTS neutral":
            markets.append(btts_lean)
        if total_lean:
            markets.append(total_lean)
            markets.append("OVER 2.5 goals")
        if not markets:
            markets.append("no strong goals/BTTS lean")

        if conviction >= 50:
            tier = "STRONG_LEAN"
        elif conviction >= 35:
            tier = "LEAN"
        else:
            tier = "WEAK"

        rows.append({
            "match": match,
            "league": m.get("league"),
            "p_btts_yes": round(p_btts, 3) if has_btts else None,
            "goals_edge": goals_edge,
            "composite_score": round(composite, 1),
            "btts_lean": btts_lean,
            "total_lean": total_lean,
            "conviction": conviction,
            "tier": tier,
            "recommended_markets": markets,
        })

    rows.sort(key=lambda r: -r["conviction"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_btts_yes": sum(1 for r in rows if r["btts_lean"] == "BTTS YES"),
        "n_total_over": sum(1 for r in rows if r["total_lean"]),
        "method_note": "Soccer goals/BTTS board from match confluence. BTTS "
                       "YES if p_btts_yes>=.58, NO if <=.42. OVER total goals "
                       "if goals_edge==STRONG_TOTAL. conviction = composite + "
                       "|p_btts-0.50|*100 + total bonus. Skips no-signal "
                       "matches. Tiers STRONG_LEAN>=50, LEAN>=35, WEAK<35.",
        "rows": rows,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-goals-btts] {o['n_matches']} matches with signal "
          f"({o['n_btts_yes']} BTTS YES, {o['n_total_over']} OVER total) -> {OUT}")
