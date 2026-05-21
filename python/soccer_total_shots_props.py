"""
EdgeStat -- Soccer total shots (combined) prop projections.

Common DK lines: O/U 22.5, 24.5, 26.5 total shots in match.
Different from shots-on-target. This is all attempts including off-target.

Method:
  expected_total_shots = (home_shots_per_game + away_shots_per_game) / 2 * 2
                       * pace_factor (league avg pace correction)
  Normal CDF at nearest 1.0 line within 4.0 of projection.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/soccer_total_shots_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_total_shots_props.json")

# League average shots per team per match
LEAGUE_AVG_SHOTS_PER_TEAM = 12.5  # ~25 combined shots per match

# Team shot generation rates per match (shots taken per game)
# 2024-25 select EPL + MLS + UCL teams
TEAM_SHOTS = {
    # EPL
    "manchester city":      14.5, "liverpool":           15.0, "arsenal":             13.5,
    "tottenham":            14.0, "chelsea":             13.8, "manchester united":   12.5,
    "newcastle":            13.0, "aston villa":         12.5, "brighton":            13.0,
    "brentford":            12.0, "fulham":              11.5, "west ham":            11.0,
    "everton":              10.5, "crystal palace":      10.5, "bournemouth":         11.0,
    "wolves":               10.5, "nottingham forest":   10.0, "leicester":           11.0,
    "ipswich":               9.5, "southampton":          9.5,
    # MLS
    "inter miami":          14.0, "los angeles fc":      13.0, "seattle sounders":    12.5,
    "atlanta united":       12.0, "lafc":                13.0, "fc cincinnati":       12.5,
    "ny red bulls":         11.5, "philadelphia union":  11.0, "columbus crew":       12.5,
    # UCL/La Liga big clubs
    "real madrid":          15.5, "barcelona":           16.0, "bayern munich":       15.5,
    "psg":                  16.0, "atletico madrid":     12.5, "inter milan":         14.0,
    "ac milan":             13.5, "juventus":            13.0, "bayer leverkusen":    14.5,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _team_shots(name: str) -> float:
    if not name: return LEAGUE_AVG_SHOTS_PER_TEAM
    key = name.lower().strip()
    return TEAM_SHOTS.get(key, LEAGUE_AVG_SHOTS_PER_TEAM)


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "soccer_state.json"))
    events = state.get("events") or state.get("games") or []

    rows: List[Dict[str, Any]] = []

    for ev in events:
        status = (ev.get("status") or ev.get("state") or "").lower()
        if "final" in status or "ft" == status or "post" in status: continue
        home = ev.get("home_team") or ev.get("home") or ""
        away = ev.get("away_team") or ev.get("away") or ""
        if not home or not away: continue

        home_shots = _team_shots(home)
        away_shots = _team_shots(away)
        expected_total = home_shots + away_shots

        # Sigma: total shots variance per game ~6-7 (each team ~4, sqrt(2 * 4^2))
        sigma = max(5.5, 0.22 * expected_total)

        # Evaluate at nearest 1.0 line within 4.0 of projection
        edge_class = "NONE"
        best_market = None
        base_line = round(expected_total) + 0.5
        for line_int in (base_line - 3, base_line - 2, base_line - 1, base_line, base_line + 1, base_line + 2, base_line + 3):
            line = line_int
            if line < 12.5 or line > 40.5: continue
            if abs(expected_total - line) > 4.0: continue
            p_over = _p_over(expected_total, sigma, line)
            p_under = 1 - p_over
            if 0.62 <= p_over <= 0.72:
                if not best_market or p_over > best_market["p"]:
                    edge_class = "STRONG_OVER"
                    best_market = {"market": f"TOTAL_SHOTS_OVER_{line}", "p": round(p_over, 3),
                                   "fair_odds": _american(p_over), "line": line}
            elif 0.62 <= p_under <= 0.72:
                if not best_market or p_under > best_market["p"]:
                    edge_class = "STRONG_UNDER"
                    best_market = {"market": f"TOTAL_SHOTS_UNDER_{line}", "p": round(p_under, 3),
                                   "fair_odds": _american(p_under), "line": line}

        rows.append({
            "matchup": f"{away} @ {home}",
            "home": home,
            "away": away,
            "home_shots_avg": home_shots,
            "away_shots_avg": away_shots,
            "expected_total_shots": round(expected_total, 1),
            "sigma": round(sigma, 1),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -r["expected_total_shots"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "Soccer total shots = home_shots_avg + away_shots_avg. Normal CDF at "
                       "nearest 1.0 line within 4.0 of projection. STRONG = 10%+ edge vs -120.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soccer-shots] {o['n_matches']} matches, {o['n_strong_edges']} strong edges -> {OUT}")
