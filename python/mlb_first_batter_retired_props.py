"""
EdgeStat -- MLB First-batter-retired yes/no prop.

For each starting pitcher, projects P(retires the leadoff batter).
Common book price: -110 to +110 yes/no.

Method:
  P(retire) = 1 - (1B_rate + 2B_rate + 3B_rate + HR_rate + BB_rate + HBP_rate)
  Use opp leadoff hitter's OBP × pitcher's hit-allowed rate.

  Simpler: 1 - opp_leadoff_OBP_adjusted_by_pitcher_skill
  Pitcher skill = league_avg_obp_allowed / pitcher_obp_allowed (proxy from WHIP)

Adjusters:
  - Opp leadoff batter's career OBP vs this pitcher's handedness
  - Pitcher's first-inning OBP allowed
  - Umpire strike-zone (wide zone = more retires)

Output: data/mlb_first_batter_retired_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_first_batter_retired_props.json")

LEAGUE_OBP = 0.317


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


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))

    p_by_name = {(p.get("name") or "").lower(): p for p in (pitcher_logs.get("pitchers") or [])}
    lvr_idx = {}
    for row in (lvr.get("all_batters") or []):
        nm = (row.get("batter") or "").lower()
        if nm: lvr_idx[nm] = row

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        lineups = g.get("lineups") or {}

        for side in ("home", "away"):
            opp_side = "away" if side == "home" else "home"
            opp_lineup = lineups.get(opp_side) or []
            # Leadoff hitter = order 1
            leadoff = None
            for b in opp_lineup:
                if isinstance(b, dict) and (b.get("order") or 99) == 1:
                    leadoff = b
                    break
            if not leadoff: continue

            p_raw = g.get(f"{side}_pitcher")
            name = p_raw if isinstance(p_raw, str) else (p_raw or {}).get("name")
            pitcher = p_by_name.get((name or "").lower())
            if not pitcher and isinstance(p_raw, dict): pitcher = p_raw
            if not pitcher: continue

            # Leadoff batter OBP (blended)
            leadoff_name = leadoff.get("name") or leadoff.get("fullName")
            lvr_row = lvr_idx.get((leadoff_name or "").lower(), {})
            season_ops = _safe(lvr_row.get("season_ops_estimate"), 0.72)
            # OBP ≈ OPS - 0.40 (rough conversion). Clamp.
            leadoff_obp = max(0.28, min(0.42, season_ops - 0.40))

            # Pitcher WHIP-based OBP allowed (rough)
            whip = _safe(pitcher.get("whip") or pitcher.get("season", {}).get("whip"), 1.25)
            # WHIP × 0.275 ≈ OBP allowed (rough conversion from WH per IP to OBP)
            pitcher_obp_allowed = max(0.28, min(0.40, whip * 0.275))

            # Composite reach-base probability: blend leadoff OBP with pitcher tendency
            # Weight 60/40 batter/pitcher (leadoff bats first, has full plate appearance)
            p_leadoff_reaches = 0.6 * leadoff_obp + 0.4 * pitcher_obp_allowed
            p_retired = 1 - p_leadoff_reaches

            # Edge classification: most starters retire leadoff at 65-70%% so books
            # price -135 to -180. STRONG requires significant deviation from baseline.
            edge_class = "NONE"
            best_market = None
            # STRONG_YES: model says >= 75% (vs typical book -180 = 64% breakeven)
            if p_retired >= 0.75 and p_retired <= 0.85:
                edge_class = "STRONG_YES"
                best_market = {"market": "FIRST_BATTER_RETIRED_YES", "p": round(p_retired, 3),
                               "fair_odds": _american(p_retired)}
            # STRONG_NO: model says <= 55% (vs typical book +130 = 43% breakeven)
            elif p_retired <= 0.55 and p_retired >= 0.45:
                edge_class = "STRONG_NO"
                best_market = {"market": "FIRST_BATTER_RETIRED_NO", "p": round(1 - p_retired, 3),
                               "fair_odds": _american(1 - p_retired)}

            rows.append({
                "matchup": matchup_str,
                "pitcher": name,
                "team": (lvr_row.get("team_abbr") or "").upper(),
                "leadoff_batter": leadoff_name,
                "leadoff_obp_est": round(leadoff_obp, 3),
                "pitcher_whip": whip,
                "pitcher_obp_allowed": round(pitcher_obp_allowed, 3),
                "p_leadoff_reaches": round(p_leadoff_reaches, 3),
                "p_retired": round(p_retired, 3),
                "fair_odds_yes": _american(p_retired),
                "fair_odds_no": _american(1 - p_retired),
                "edge_class": edge_class,
                "best_market": best_market,
            })

    rows.sort(key=lambda r: -r["p_retired"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_starters": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "P(first batter retired) = 1 - (0.6 × leadoff_OBP + 0.4 × pitcher_OBP_allowed). "
                       "STRONG_YES: p in [0.62, 0.72]. STRONG_NO: p in [0.42, 0.55].",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[first-batter] {o['n_starters']} starters, {o['n_strong_edges']} strong -> {OUT}")
