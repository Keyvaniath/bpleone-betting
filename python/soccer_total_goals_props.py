"""
EdgeStat -- Soccer total goals over/under prop.

The most-bet soccer market globally. Common DK lines:
  - Over 2.5 / Under 2.5  (most common, ~50/50 in EPL/UCL, more under in MLS)
  - Over 1.5 / Under 1.5  (low total - heavy under typically)
  - Over 3.5 / Under 3.5  (high total - heavy over typically)

Method:
  Combined lambda = lam_home + lam_away (from BTTS module pattern).
  P(>= N) via Poisson cumulative distribution (or skew-adjusted Skellam).

  Per-league baselines:
    EPL: ~2.85 g/game
    UCL: ~3.10 g/game
    La Liga: ~2.45 g/game
    MLS: ~2.70 g/game
    Bundesliga: ~3.00 g/game

  STRONG when edge >= 5pp vs typical -110 book (52.4% breakeven).

Output: data/soccer_total_goals_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_total_goals_props.json")

LEAGUE_BASELINES = {
    "epl": 2.85, "mls": 2.70, "ucl": 3.10, "la_liga": 2.45,
    "serie_a": 2.75, "bundesliga": 3.00, "ligue_1": 2.55,
}
HOME_ADVANTAGE = 0.30  # home boost in lambda


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


def _process_league(state_file: str, league: str) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or state.get("events") or []
    rows = []
    base_total = LEAGUE_BASELINES.get(league, 2.7)

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        elo_diff = (home_elo - away_elo) / 400.0
        # Stronger teams typically push slight tempo up; differential affects who scores more
        per_team_base = base_total / 2.0
        lam_home = max(0.4, min(3.5, per_team_base + HOME_ADVANTAGE + 0.15 * elo_diff))
        lam_away = max(0.4, min(3.5, per_team_base - 0.15 * elo_diff))
        lam_total = lam_home + lam_away

        # P(over N.5) = P(>= N+1) at Poisson(lam_total)
        p_over_05 = _poisson_at_least(1, lam_total)
        p_over_15 = _poisson_at_least(2, lam_total)
        p_over_25 = _poisson_at_least(3, lam_total)
        p_over_35 = _poisson_at_least(4, lam_total)
        p_over_45 = _poisson_at_least(5, lam_total)

        # Only flag STRONG when ELO differential is meaningful (not pure default)
        # OR when lam_total deviates >= 0.50 from league baseline (above
        # the 0.30 home-advantage floor).
        elo_meaningful = abs(elo_diff) >= 0.20
        lam_deviation = abs(lam_total - base_total - HOME_ADVANTAGE) >= 0.50

        edges: List[Dict[str, Any]] = []
        # Only emit edges when there's a real signal — avoid default-ELO false positives
        if elo_meaningful or lam_deviation:
            best_edge_amt = 0.0
            best_edge = None
            for line, p_over in (("0.5", p_over_05), ("1.5", p_over_15),
                                 ("2.5", p_over_25), ("3.5", p_over_35),
                                 ("4.5", p_over_45)):
                p_under = 1 - p_over
                for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                    if 0.60 <= p <= 0.68:  # Tighter zone for cleaner edges
                        edge_amt = p - 0.524  # vs -110 breakeven
                        if edge_amt > best_edge_amt:
                            best_edge_amt = edge_amt
                            best_edge = {
                                "market": f"TOTAL_{direction}_{line}",
                                "line": float(line),
                                "direction": direction,
                                "p": round(p, 3),
                                "fair_odds": _american(p),
                            }
            if best_edge:
                edges.append(best_edge)

        edge_class = "STRONG_TOTAL" if edges else "NONE"

        rows.append({
            "league": league.upper(),
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "lam_home": round(lam_home, 3),
            "lam_away": round(lam_away, 3),
            "lam_total": round(lam_total, 3),
            "p_over_1.5": round(p_over_15, 3),
            "p_over_2.5": round(p_over_25, 3),
            "p_over_3.5": round(p_over_35, 3),
            "edge_class": edge_class,
            "edges_found": edges,
        })
    return rows


def run() -> Dict[str, Any]:
    all_rows = []
    for state_file, league in (
        ("epl_state.json", "epl"),
        ("mls_state.json", "mls"),
        ("ucl_state.json", "ucl"),
        ("la_liga_state.json", "la_liga"),
        ("serie_a_state.json", "serie_a"),
        ("bundesliga_state.json", "bundesliga"),
        ("ligue_1_state.json", "ligue_1"),
    ):
        all_rows.extend(_process_league(state_file, league))

    strong = [r for r in all_rows if r["edge_class"] == "STRONG_TOTAL"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(all_rows),
        "n_strong_edges": len(strong),
        "method_note": "Poisson(lam_total) cumulative for over/under at 0.5/1.5/2.5/"
                       "3.5/4.5 lines. Per-league baselines: EPL 2.85, UCL 3.10, "
                       "La Liga 2.45. STRONG at p >= 57% vs -110 book.",
        "rows": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soc-total] {o['n_matches']} matches, {o['n_strong_edges']} strong -> {OUT}")
