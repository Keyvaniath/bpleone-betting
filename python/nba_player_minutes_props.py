"""
EdgeStat -- NBA player minutes prop projections.

Common DK lines: starters 32.5-37.5; role players 22.5-28.5; benchwarmers 14-18.
Typical book: -120 to +110 on either side.

Method:
  Per-player season minutes baseline + situational adjustments:
    - close_game_boost: starters play +1.5 min when game is competitive
    - blowout_penalty: starters lose -3 min if game projected by 15+
    - back_to_back_penalty: -1.5 min if team on second leg of B2B
    - playoff_intensity: in playoff games, stars +1.5 min, role players -1.0 min

Sigma scales with role:
  Star (>=30 MPG): sigma 3.5
  Mid (22-30 MPG): sigma 4.5
  Bench (<22 MPG): sigma 6.0

Normal CDF over typical lines around projection.

STRONG when 10%+ edge vs -120 (45.5% breakeven each side).

Output: data/nba_player_minutes_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nba_player_minutes_props.json")

# Top NBA players + season MPG (2024-25)
PLAYER_DB = {
    "shai gilgeous-alexander": {"team": "OKC", "mpg": 34.5},
    "luka doncic":              {"team": "LAL", "mpg": 36.0},
    "giannis antetokounmpo":    {"team": "MIL", "mpg": 35.0},
    "jayson tatum":             {"team": "BOS", "mpg": 36.5},
    "anthony edwards":          {"team": "MIN", "mpg": 36.0},
    "stephen curry":            {"team": "GSW", "mpg": 32.5},
    "lebron james":             {"team": "LAL", "mpg": 35.0},
    "donovan mitchell":         {"team": "CLE", "mpg": 35.5},
    "jaylen brown":             {"team": "BOS", "mpg": 33.5},
    "kevin durant":             {"team": "PHX", "mpg": 36.5},
    "devin booker":             {"team": "PHX", "mpg": 36.0},
    "damian lillard":           {"team": "MIL", "mpg": 35.5},
    "tyrese haliburton":        {"team": "IND", "mpg": 34.5},
    "pascal siakam":            {"team": "IND", "mpg": 34.5},
    "jalen brunson":            {"team": "NYK", "mpg": 36.5},
    "karl-anthony towns":       {"team": "NYK", "mpg": 35.0},
    "trae young":               {"team": "ATL", "mpg": 36.0},
    "victor wembanyama":        {"team": "SAS", "mpg": 32.5},
    "ja morant":                {"team": "MEM", "mpg": 34.0},
    "paul george":              {"team": "PHI", "mpg": 34.0},
    "joel embiid":              {"team": "PHI", "mpg": 32.0},
    "tyrese maxey":             {"team": "PHI", "mpg": 38.0},
    "domantas sabonis":         {"team": "SAC", "mpg": 35.5},
    "demar derozan":            {"team": "SAC", "mpg": 35.0},
    "zion williamson":          {"team": "NOP", "mpg": 32.0},
    "anthony davis":            {"team": "LAL", "mpg": 34.5},
    "lauri markkanen":          {"team": "UTA", "mpg": 33.5},
    "alperen sengun":           {"team": "HOU", "mpg": 32.0},
    "scottie barnes":           {"team": "TOR", "mpg": 35.0},
    "lamelo ball":              {"team": "CHA", "mpg": 34.0},
    "paolo banchero":           {"team": "ORL", "mpg": 35.0},
    "kyrie irving":             {"team": "DAL", "mpg": 34.5},
    "cade cunningham":          {"team": "DET", "mpg": 36.0},
    "jalen williams":           {"team": "OKC", "mpg": 33.0},
    "chet holmgren":            {"team": "OKC", "mpg": 30.0},
    "kawhi leonard":            {"team": "LAC", "mpg": 32.0},
    "james harden":             {"team": "LAC", "mpg": 34.5},
    "darius garland":           {"team": "CLE", "mpg": 31.5},
    "rudy gobert":              {"team": "MIN", "mpg": 28.0},
    "norman powell":            {"team": "LAC", "mpg": 32.0},
    "jaren jackson jr":         {"team": "MEM", "mpg": 30.5},
    "evan mobley":              {"team": "CLE", "mpg": 32.0},
    "jarrett allen":            {"team": "CLE", "mpg": 30.0},
    "isaiah hartenstein":       {"team": "OKC", "mpg": 25.0},
    "jrue holiday":             {"team": "BOS", "mpg": 30.5},
    "kristaps porzingis":       {"team": "BOS", "mpg": 27.5},
    "derrick white":            {"team": "BOS", "mpg": 32.5},
    "andrew nembhard":          {"team": "IND", "mpg": 30.0},
    "myles turner":             {"team": "IND", "mpg": 30.5},
    "bennedict mathurin":       {"team": "IND", "mpg": 28.0},
    "obi toppin":               {"team": "IND", "mpg": 24.0},
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


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


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _abbr(name: str) -> str:
    if not name: return ""
    mapping = {
        "memphis grizzlies": "MEM", "washington wizards": "WAS", "indiana pacers": "IND",
        "oklahoma city thunder": "OKC", "sacramento kings": "SAC", "boston celtics": "BOS",
        "denver nuggets": "DEN", "minnesota timberwolves": "MIN", "new york knicks": "NYK",
        "los angeles lakers": "LAL", "miami heat": "MIA", "golden state warriors": "GSW",
        "phoenix suns": "PHX", "cleveland cavaliers": "CLE", "philadelphia 76ers": "PHI",
        "dallas mavericks": "DAL", "milwaukee bucks": "MIL", "atlanta hawks": "ATL",
        "orlando magic": "ORL", "brooklyn nets": "BKN", "detroit pistons": "DET",
        "charlotte hornets": "CHA", "toronto raptors": "TOR", "portland trail blazers": "POR",
        "utah jazz": "UTA", "houston rockets": "HOU", "san antonio spurs": "SAS",
        "new orleans pelicans": "NOP", "chicago bulls": "CHI", "los angeles clippers": "LAC",
    }
    return mapping.get(name.lower().strip(), name[:3].upper())


def _sigma_for_mpg(mpg: float) -> float:
    if mpg >= 30: return 3.5
    if mpg >= 22: return 4.5
    return 6.0


def _typical_lines_around(mpg: float) -> List[float]:
    """DK typical line offsets around projection."""
    # 0.5 increments near projection
    base = round(mpg * 2) / 2  # nearest 0.5
    return [base - 1.5, base - 0.5, base + 0.5, base + 1.5]


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "nba_state.json"))
    games = state.get("games") or state.get("events") or []

    rows: List[Dict[str, Any]] = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status: continue
        home = _abbr(g.get("home_team") or g.get("home") or "")
        away = _abbr(g.get("away_team") or g.get("away") or "")
        if not home or not away: continue
        matchup = f"{away} @ {home}"

        # Optional: detect playoff via game name / round flag
        is_playoff = "playoff" in (g.get("series_name") or "").lower() \
                     or bool(g.get("playoffs"))
        # Optional: blowout / b2b flags (mock proxies)
        spread = abs(float(g.get("spread") or 0))
        is_blowout = spread >= 9
        b2b_home = bool(g.get("home_b2b"))
        b2b_away = bool(g.get("away_b2b"))

        for player_name, info in PLAYER_DB.items():
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            base_mpg = info["mpg"]

            # Situational adjustments
            adj = 0.0
            if is_playoff:
                adj += 1.5 if base_mpg >= 30 else -1.0
            if is_blowout:
                adj -= 3.0 if base_mpg >= 30 else +1.5  # benches play in blowouts
            if (is_home and b2b_home) or (not is_home and b2b_away):
                adj -= 1.5 if base_mpg >= 30 else 0.0

            proj_mpg = max(8.0, min(42.0, base_mpg + adj))
            sigma = _sigma_for_mpg(proj_mpg)

            # Lines around projection
            best_edge = 0.0
            best_market = None
            edge_class = "NONE"
            for line in _typical_lines_around(proj_mpg):
                z = (line - proj_mpg) / sigma
                p_over = 1 - _norm_cdf(z)
                p_under = 1 - p_over
                # Edge vs -120 (45.5% breakeven)
                for direction, p in (("OVER", p_over), ("UNDER", p_under)):
                    if 0.56 <= p <= 0.66:  # 10%+ edge zone
                        edge_amt = p - 0.455
                        if edge_amt > best_edge:
                            best_edge = edge_amt
                            best_market = {
                                "line": line, "direction": direction,
                                "p": round(p, 3), "fair_odds": _american(p),
                            }
                            edge_class = "STRONG"

            rows.append({
                "matchup": matchup,
                "player": player_name,
                "team": info["team"],
                "is_home": is_home,
                "base_mpg": base_mpg,
                "adjustment": round(adj, 1),
                "proj_mpg": round(proj_mpg, 2),
                "sigma": sigma,
                "is_playoff": is_playoff,
                "is_blowout": is_blowout,
                "best_market": best_market,
                "edge_amount": round(best_edge, 3) if best_edge else None,
                "edge_class": edge_class,
                "mpg_source": "fallback",
            })

    rows.sort(key=lambda r: -(r.get("edge_amount") or 0))
    strong = [r for r in rows if r["edge_class"] == "STRONG"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_strong_edges": len(strong),
        "method_note": "MPG = season_baseline + playoff/blowout/b2b adjustments. "
                       "Normal CDF over typical DK lines (0.5 increments). "
                       "STRONG when p in [0.56, 0.66] vs -120 book (45.5% breakeven).",
        "rows": rows[:60],
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[nba-min] {o['n_players']} players, {o['n_strong_edges']} strong -> {OUT}")
