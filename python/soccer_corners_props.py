"""
EdgeStat -- Soccer total corners prop projections.

For each upcoming soccer match (MLS/EPL/UCL), projects:
  - Expected total corners (sum of home + away)
  - P(total > 8.5), P(total > 9.5), P(total > 10.5), P(total > 11.5)
  - Best edge classification per match

Method:
  Per-team corners-per-game from league averages (refined by team if we have
  shots-on-goal data). Convert via Poisson convolution.

League-average corners per game (per team):
  - EPL:   ~5.4 per team (10.8 total per match)
  - MLS:   ~4.8 per team (9.6 total)
  - UCL:   ~5.6 per team (11.2 total -- attacking-heavy)
  - La Liga: ~5.1 per team
  - Serie A: ~4.9 per team

Approach:
  total_corners ~ Poisson(lambda = home_attacking_intensity + away_attacking_intensity)
  where intensity is league_avg adjusted by team-attack-rating from shots data.

Output: data/soccer_corners_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_corners_props.json")

# League corners-per-team baselines (2024 season)
LEAGUE_BASELINES = {
    "epl": 5.4, "mls": 4.8, "ucl": 5.6, "la_liga": 5.1, "serie_a": 4.9,
}

# Sigma proxy for normal approximation (corners std dev ~ 2.5 per team)
CORNERS_STDDEV = 3.5  # per match total


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


def _poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _poisson_at_least(k: int, lam: float) -> float:
    if lam <= 0: return 0.0 if k > 0 else 1.0
    p_less = sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))
    return max(0.0, min(1.0, 1.0 - p_less))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _league_baseline(league: str) -> float:
    """Per-team corners baseline for a league. Returns total expected per match."""
    key = (league or "").lower()
    base = LEAGUE_BASELINES.get(key, 5.0)  # default ~10/match total
    return base * 2  # home + away combined


def _process_league(state_file: str, league: str) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or state.get("events") or []
    rows = []
    base_total = _league_baseline(league)

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        # Use ELO-based attacking strength if available (proxy for shot creation)
        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        # Higher ELO teams create more chances -> more corners
        elo_mult = 1.0 + (home_elo + away_elo - 3000) / 30000  # +0.033 per 1000 combined ELO above 3000
        elo_mult = max(0.85, min(1.20, elo_mult))

        expected_total = base_total * elo_mult

        lines = {}
        for line in [8.5, 9.5, 10.5, 11.5, 12.5]:
            p_over = _poisson_at_least(int(line) + 1, expected_total)
            lines[f"line_{line}"] = {
                "p_over": round(p_over, 3),
                "p_under": round(1 - p_over, 3),
                "fair_odds_over": _american(p_over),
                "fair_odds_under": _american(1 - p_over),
            }

        # Edge classification: STRONG requires BOTH (a) the model materially differs
        # from the league baseline (otherwise the book has same info), AND (b) the
        # nearest 0.5 line gives 15%+ edge vs -120 book (p in [0.66, 0.74]).
        edge_class = "NONE"
        best_market = None
        differentiation = abs(expected_total - base_total)
        if differentiation >= 0.6:  # team-specific signal is meaningful
            nearest_line = round(expected_total - 0.5) + 0.5
            for line in [nearest_line, nearest_line + 0.5]:
                if line < 6.5 or line > 14.5: continue
                if abs(expected_total - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, expected_total)
                p_under = 1 - p_over
                if 0.66 <= p_over <= 0.74:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"CORNERS_OVER_{line}",
                                       "p": round(p_over, 3), "fair_odds": _american(p_over), "line": line}
                elif 0.66 <= p_under <= 0.74:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"CORNERS_UNDER_{line}",
                                       "p": round(p_under, 3), "fair_odds": _american(p_under), "line": line}

        rows.append({
            "league": league.upper(),
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "league_baseline_total": base_total,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_mult": round(elo_mult, 3),
            "expected_total_corners": round(expected_total, 2),
            "lines": lines,
            "edge_class": edge_class,
            "best_market": best_market,
        })
    return rows


def run() -> Dict[str, Any]:
    all_rows = []
    for state_file, league in [
        ("mls_state.json", "mls"),
        ("epl_state.json", "epl"),
        ("ucl_state.json", "ucl"),
        ("worldcup_state.json", "worldcup"),
    ]:
        rows = _process_league(state_file, league)
        all_rows.extend(rows)

    all_rows.sort(key=lambda r: -r["expected_total_corners"])
    strong = [r for r in all_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(all_rows),
        "n_strong_edges": len(strong),
        "league_baselines_per_team": LEAGUE_BASELINES,
        "method_note": "Total corners ~ Poisson(home_intensity + away_intensity). "
                       "Intensity = league_baseline * ELO-derived attacking adjustment.",
        "matches": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[corners] {o['n_matches']} matches, {o['n_strong_edges']} strong edges -> {OUT}")
