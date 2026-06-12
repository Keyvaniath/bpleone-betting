"""
EdgeStat -- Soccer total cards (yellow + red) prop projections.

Popular European market. Common lines:
  - Total cards 3.5, 4.5, 5.5 over/under
  - Both teams to receive cards yes/no

Per-team cards-per-match baselines (2024 season):
  - EPL:    2.0 per team (~4.0 match total)
  - La Liga: 2.4 per team (high-tackle league)
  - Serie A: 2.5 per team
  - UCL:    2.3 per team (high-intensity knockouts)
  - MLS:    2.0 per team

ELO differential and rivalry matchups bump cards higher.

Output: data/soccer_cards_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_cards_props.json")

LEAGUE_BASELINES = {
    "epl": 2.0, "mls": 2.0, "ucl": 2.3, "la_liga": 2.4, "serie_a": 2.5,
}


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
    return max(0.0, min(1.0, 1.0 - sum(_poisson_pmf(i, lam) for i in range(min(k, 50)))))


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _process_league(state_file: str, league: str) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or state.get("events") or []
    rows = []
    base_per_team = LEAGUE_BASELINES.get(league, 2.2)
    base_total = base_per_team * 2

    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = _safe(g.get("home_elo"), 1500)
        away_elo = _safe(g.get("away_elo"), 1500)
        # Higher-ELO mismatches reduce cards (clean dominance); tight matchups raise cards
        elo_diff_abs = abs(home_elo - away_elo)
        intensity_mult = 1.0 + 0.20 * (1 - min(1.0, elo_diff_abs / 200))  # tight match = up to +20%
        intensity_mult = max(0.85, min(1.20, intensity_mult))

        expected_total = base_total * intensity_mult

        lines = {}
        for line in [2.5, 3.5, 4.5, 5.5, 6.5]:
            p_over = _poisson_at_least(int(line) + 1, expected_total)
            lines[f"line_{line}"] = {
                "p_over": round(p_over, 3),
                "p_under": round(1 - p_over, 3),
                "fair_odds_over": _american(p_over),
                "fair_odds_under": _american(1 - p_over),
            }

        # Edge classification: only nearest 0.5 line within 0.75 of expected
        edge_class = "NONE"
        best_market = None
        # Require team-specific signal (intensity_mult differentiates from league avg)
        if abs(intensity_mult - 1.0) >= 0.07:
            nearest_line = round(expected_total - 0.5) + 0.5
            for line in (nearest_line, nearest_line + 0.5):
                if line < 2.5 or line > 6.5: continue
                if abs(expected_total - line) > 0.75: continue
                p_over = _poisson_at_least(int(line) + 1, expected_total)
                p_under = 1 - p_over
                if 0.62 <= p_over <= 0.72:
                    if not best_market or p_over > best_market["p"]:
                        edge_class = "STRONG_OVER"
                        best_market = {"market": f"CARDS_OVER_{line}", "p": round(p_over, 3),
                                       "fair_odds": _american(p_over), "line": line}
                elif 0.62 <= p_under <= 0.72:
                    if not best_market or p_under > best_market["p"]:
                        edge_class = "STRONG_UNDER"
                        best_market = {"market": f"CARDS_UNDER_{line}", "p": round(p_under, 3),
                                       "fair_odds": _american(p_under), "line": line}

        rows.append({
            "league": league.upper(),
            "matchup": f"{away} @ {home}",
            "game_date": (g.get("date") or "")[:10],  # date the pick to kickoff -> dedup + clean settle
            "home_team": home,
            "away_team": away,
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_diff_abs": elo_diff_abs,
            "league_baseline_total": base_total,
            "intensity_mult": round(intensity_mult, 3),
            "expected_total_cards": round(expected_total, 2),
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

    all_rows.sort(key=lambda r: -r["expected_total_cards"])
    strong = [r for r in all_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(all_rows),
        "n_strong": len(strong),
        "league_baselines_per_team": LEAGUE_BASELINES,
        "method_note": "Total cards = league_baseline × intensity_factor (tight ELO matchup = more cards). "
                       "Poisson at nearest line. STRONG only when intensity differential is "
                       "meaningful (>=7%% from neutral).",
        "matches": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[cards] {o['n_matches']} matches, {o['n_strong']} strong -> {OUT}")
