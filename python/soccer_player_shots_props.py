"""
EdgeStat -- Soccer player shots on target O/U prop.

DK common per-player line for stars: Haaland 2.5 SOT, Mbappe 2.5,
Salah 1.5, Bellingham 1.5, etc.

Method:
  PLAYER_DB hardcoded for top scorers in major leagues. Per-player baseline
  SOT/match adjusted for:
    - Surface bonus (no concept in soccer, leave as 1.0)
    - Match competitiveness factor (UCL +20% SOT volume vs domestic league)
    - Home factor (+10% SOT volume at home)

  Normal CDF around projection with sigma scaled to 35% of mean.
  STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).

Output: data/soccer_player_shots_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_player_shots_props.json")

# Per-player avg SOT (shots on target) per match
PLAYER_DB = {
    # EPL stars
    "erling haaland":        {"team": "Manchester City", "sot_match": 2.3, "league": "epl"},
    "mohamed salah":         {"team": "Liverpool", "sot_match": 2.0, "league": "epl"},
    "cole palmer":           {"team": "Chelsea", "sot_match": 1.9, "league": "epl"},
    "harry kane":            {"team": "Bayern Munich", "sot_match": 2.2, "league": "bundesliga"},
    "bukayo saka":           {"team": "Arsenal", "sot_match": 1.6, "league": "epl"},
    "son heung-min":         {"team": "Tottenham", "sot_match": 1.8, "league": "epl"},
    "alexander isak":        {"team": "Newcastle", "sot_match": 2.0, "league": "epl"},
    # La Liga
    "robert lewandowski":    {"team": "Barcelona", "sot_match": 2.4, "league": "la_liga"},
    "vinicius junior":       {"team": "Real Madrid", "sot_match": 2.0, "league": "la_liga"},
    "jude bellingham":       {"team": "Real Madrid", "sot_match": 1.5, "league": "la_liga"},
    "kylian mbappe":         {"team": "Real Madrid", "sot_match": 2.3, "league": "la_liga"},
    "lamine yamal":          {"team": "Barcelona", "sot_match": 1.4, "league": "la_liga"},
    # Bundesliga
    "florian wirtz":         {"team": "Bayer Leverkusen", "sot_match": 1.5, "league": "bundesliga"},
    "serhou guirassy":       {"team": "Borussia Dortmund", "sot_match": 1.9, "league": "bundesliga"},
    # Serie A
    "lautaro martinez":      {"team": "Inter Milan", "sot_match": 1.8, "league": "serie_a"},
    "victor osimhen":        {"team": "Napoli", "sot_match": 2.0, "league": "serie_a"},
    # MLS
    "lionel messi":          {"team": "Inter Miami", "sot_match": 2.5, "league": "mls"},
    "luis suarez":           {"team": "Inter Miami", "sot_match": 2.0, "league": "mls"},
    # Other big names
    "rasmus hojlund":        {"team": "Manchester United", "sot_match": 1.4, "league": "epl"},
    "ollie watkins":         {"team": "Aston Villa", "sot_match": 1.7, "league": "epl"},
    "darwin nunez":          {"team": "Liverpool", "sot_match": 1.8, "league": "epl"},
    "marcus rashford":       {"team": "Aston Villa", "sot_match": 1.5, "league": "epl"},
    "phil foden":            {"team": "Manchester City", "sot_match": 1.5, "league": "epl"},
}

LEAGUE_MULT = {"epl": 1.0, "la_liga": 0.95, "serie_a": 0.95,
               "bundesliga": 1.05, "mls": 1.0, "ucl": 1.20}
HOME_BONUS = 1.10


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


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _p_over(mean: float, sigma: float, line: float) -> float:
    if sigma <= 0: return 1.0 if mean > line else 0.0
    z = (line + 0.5 - mean) / sigma
    return 1 - _norm_cdf(z)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _process_league(state_file: str, league: str) -> List[Dict[str, Any]]:
    state = _load(os.path.join(DATA_DIR, state_file))
    games = state.get("games") or state.get("events") or []
    league_mult = LEAGUE_MULT.get(league, 1.0)

    rows = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        for name, info in PLAYER_DB.items():
            if info.get("league") != league: continue
            if info.get("team") not in (home, away): continue
            is_home = info["team"] == home
            home_mult = HOME_BONUS if is_home else 1.0

            proj = info["sot_match"] * league_mult * home_mult
            sigma = max(0.8, 0.35 * proj)

            base_line = round(proj * 2) / 2
            best_edge = 0.0
            best_market = None
            edge_class = "NONE"
            for offset in (-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5):
                line = base_line + offset
                if line < 0.5 or line > 8.5: continue
                p_over = _p_over(proj, sigma, line)
                p_under = 1 - p_over
                for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                    if 0.62 <= p <= 0.72:
                        edge_amt = p - 0.545
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {"market": f"SOT_{direction}_{line}",
                                           "line": line, "direction": direction,
                                           "p": round(p, 3),
                                           "fair_odds": _american(p)}
                            edge_class = "STRONG"

            rows.append({
                "league": league.upper(),
                "matchup": f"{away} @ {home}",
                "player": name,
                "team": info["team"],
                "is_home": is_home,
                "base_sot_per_match": info["sot_match"],
                "projected_sot": round(proj, 2),
                "sigma": round(sigma, 2),
                "best_market": best_market,
                "edge_class": edge_class,
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
    ):
        all_rows.extend(_process_league(state_file, league))

    strong = [r for r in all_rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_player_matches": len(all_rows),
        "n_strong_edges": len(strong),
        "method_note": "Per-player SOT projection = base_sot_match * league_mult * "
                       "home_bonus (1.10). Normal CDF, sigma 35% of projection. "
                       "STRONG when 10%+ edge vs -120 book (p in [0.62, 0.72]).",
        "rows": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[soc-sot] {o['n_player_matches']} player-matches, "
          f"{o['n_strong_edges']} strong -> {OUT}")
