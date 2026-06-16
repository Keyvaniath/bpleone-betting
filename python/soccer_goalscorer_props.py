"""
EdgeStat -- Soccer player anytime-goalscorer prop projections.

For top forwards/attacking midfielders, project P(scores >= 1 goal).
Common book prices: -120 to +500 depending on player + matchup.

Approach:
  Per-player season goals/match (G/M) * 0.92 = expected goals this match.
  P(scores 1+) = 1 - exp(-lambda_goals).
  Matchup adjustment: opponent defensive ELO + home_field_boost.

Player DB: top 30 attacking talents in EPL/MLS/UCL competitions 2024-25.

Output: data/soccer_goalscorer_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "soccer_goalscorer_props.json")

# 2024-25 season goals-per-match for top attackers (compiled May 2026)
PLAYER_DB = {
    # 2026 WORLD CUP -- national-team scorers. gpm = recent international rate,
    # deliberately conservative (international scoring runs below club rates).
    # Team strings must match ESPN displayName in worldcup_state.json.
    "kylian mbappe wc":      {"team": "France",        "gpm": 0.75, "league": "WORLDCUP", "name": "kylian mbappe"},
    "lionel messi wc":       {"team": "Argentina",     "gpm": 0.55, "league": "WORLDCUP", "name": "lionel messi"},
    "lautaro martinez wc":   {"team": "Argentina",     "gpm": 0.50, "league": "WORLDCUP", "name": "lautaro martinez"},
    "harry kane wc":         {"team": "England",       "gpm": 0.65, "league": "WORLDCUP", "name": "harry kane"},
    "erling haaland wc":  {"team": "Norway",        "gpm": 0.80, "league": "WORLDCUP", "name": "erling haaland"},
    "cristiano ronaldo":  {"team": "Portugal",      "gpm": 0.50, "league": "WORLDCUP"},
    "vinicius junior wc":    {"team": "Brazil",        "gpm": 0.45, "league": "WORLDCUP", "name": "vinicius junior"},
    "raphinha wc":           {"team": "Brazil",        "gpm": 0.45, "league": "WORLDCUP", "name": "raphinha"},
    "lamine yamal wc":       {"team": "Spain",         "gpm": 0.40, "league": "WORLDCUP", "name": "lamine yamal"},
    "alvaro morata":      {"team": "Spain",         "gpm": 0.40, "league": "WORLDCUP"},
    "jamal musiala wc":      {"team": "Germany",       "gpm": 0.40, "league": "WORLDCUP", "name": "jamal musiala"},
    "memphis depay":      {"team": "Netherlands",   "gpm": 0.45, "league": "WORLDCUP"},
    "romelu lukaku":      {"team": "Belgium",       "gpm": 0.55, "league": "WORLDCUP"},
    "son heung-min wc":   {"team": "South Korea",   "gpm": 0.45, "league": "WORLDCUP", "name": "son heung-min"},
    "mohamed salah wc":   {"team": "Egypt",         "gpm": 0.55, "league": "WORLDCUP", "name": "mohamed salah"},
    "youssef en-nesyri":  {"team": "Morocco",       "gpm": 0.40, "league": "WORLDCUP"},
    "darwin nunez":       {"team": "Uruguay",       "gpm": 0.45, "league": "WORLDCUP"},
    "christian pulisic":  {"team": "United States", "gpm": 0.40, "league": "WORLDCUP"},
    "folarin balogun":    {"team": "United States", "gpm": 0.35, "league": "WORLDCUP"},
    "santiago gimenez":   {"team": "Mexico",        "gpm": 0.40, "league": "WORLDCUP"},
    "jonathan david":     {"team": "Canada",        "gpm": 0.45, "league": "WORLDCUP"},
    "takefusa kubo":      {"team": "Japan",         "gpm": 0.30, "league": "WORLDCUP"},
    "breel embolo":       {"team": "Switzerland",   "gpm": 0.35, "league": "WORLDCUP"},
    "sadio mane":         {"team": "Senegal",       "gpm": 0.40, "league": "WORLDCUP"},
    # EPL
    "erling haaland":    {"team": "Manchester City",   "gpm": 0.92, "league": "EPL"},
    "mohamed salah":     {"team": "Liverpool",         "gpm": 0.62, "league": "EPL"},
    "cole palmer":       {"team": "Chelsea",           "gpm": 0.52, "league": "EPL"},
    "alexander isak":    {"team": "Newcastle United",  "gpm": 0.55, "league": "EPL"},
    "ollie watkins":     {"team": "Aston Villa",       "gpm": 0.44, "league": "EPL"},
    "bukayo saka":       {"team": "Arsenal",           "gpm": 0.45, "league": "EPL"},
    "kai havertz":       {"team": "Arsenal",           "gpm": 0.35, "league": "EPL"},
    "bryan mbeumo":      {"team": "Brentford",         "gpm": 0.45, "league": "EPL"},
    "yoane wissa":       {"team": "Brentford",         "gpm": 0.50, "league": "EPL"},
    "dominic solanke":   {"team": "Tottenham Hotspur", "gpm": 0.40, "league": "EPL"},
    "son heung-min":     {"team": "Tottenham Hotspur", "gpm": 0.42, "league": "EPL"},
    "rasmus hojlund":    {"team": "Manchester United", "gpm": 0.35, "league": "EPL"},
    # UCL big names
    "kylian mbappe":     {"team": "Real Madrid",       "gpm": 0.85, "league": "UCL"},
    "jude bellingham":   {"team": "Real Madrid",       "gpm": 0.43, "league": "UCL"},
    "vinicius junior":   {"team": "Real Madrid",       "gpm": 0.55, "league": "UCL"},
    "robert lewandowski":{"team": "Barcelona",         "gpm": 0.80, "league": "UCL"},
    "raphinha":          {"team": "Barcelona",         "gpm": 0.45, "league": "UCL"},
    "lamine yamal":      {"team": "Barcelona",         "gpm": 0.40, "league": "UCL"},
    "harry kane":        {"team": "Bayern Munich",     "gpm": 0.95, "league": "UCL"},
    "jamal musiala":     {"team": "Bayern Munich",     "gpm": 0.50, "league": "UCL"},
    "ousmane dembele":   {"team": "Paris Saint-Germain", "gpm": 0.45, "league": "UCL"},
    "bradley barcola":   {"team": "Paris Saint-Germain", "gpm": 0.40, "league": "UCL"},
    "lautaro martinez":  {"team": "Inter Milan",       "gpm": 0.60, "league": "UCL"},
    "viktor gyokeres":   {"team": "Sporting CP",       "gpm": 1.00, "league": "UCL"},
    # MLS
    "lionel messi":      {"team": "Inter Miami CF",    "gpm": 0.85, "league": "MLS"},
    "luis suarez":       {"team": "Inter Miami CF",    "gpm": 0.55, "league": "MLS"},
    "denis bouanga":     {"team": "Los Angeles FC",    "gpm": 0.60, "league": "MLS"},
    "christian benteke": {"team": "D.C. United",       "gpm": 0.50, "league": "MLS"},
    "thiago almada":     {"team": "Atlanta United FC", "gpm": 0.40, "league": "MLS"},
    "lorenzo insigne":   {"team": "Toronto FC",        "gpm": 0.30, "league": "MLS"},
    "marco messi":       {"team": "Real Salt Lake",    "gpm": 0.42, "league": "MLS"},
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _process_league(state_file: str, league: str,
                    games_override: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    if games_override is not None:
        games = games_override
    else:
        state = _load(os.path.join(DATA_DIR, state_file))
        games = state.get("games") or state.get("events") or []
    rows = []
    for g in games:
        status = (g.get("status") or g.get("state") or "").lower()
        if "final" in status or "ft" in status: continue
        home = (g.get("home_team") or g.get("home") or "").strip()
        away = (g.get("away_team") or g.get("away") or "").strip()
        if not home or not away: continue

        home_elo = float(g.get("home_elo") or 1500)
        away_elo = float(g.get("away_elo") or 1500)

        for player_name, info in PLAYER_DB.items():
            if info["league"] != league.upper(): continue
            if info["team"] not in (home, away): continue
            is_home = info["team"] == home
            opp_elo = away_elo if is_home else home_elo

            # Adjust expected goals by opponent defensive strength
            # Default opponent ELO 1500. Each 100 ELO below average = +5%% expected goals
            opp_defense_mult = 1.0 + (1500 - opp_elo) / 2000.0
            opp_defense_mult = max(0.70, min(1.30, opp_defense_mult))
            home_boost = 1.10 if is_home else 0.95

            expected_goals = info["gpm"] * opp_defense_mult * home_boost
            p_scores_1plus = 1 - math.exp(-expected_goals)
            p_scores_2plus = 1 - math.exp(-expected_goals) - expected_goals * math.exp(-expected_goals)
            p_scores_2plus = max(0, p_scores_2plus)

            # Edge classification: STRONG when 10%+ over -120 book breakeven
            # Anytime goalscorer markets are typically priced -130 to +300
            # STRONG_YES: high-quality matchup for elite scorer
            edge_class = "NONE"
            best_market = None
            if 0.60 <= p_scores_1plus <= 0.75:
                edge_class = "STRONG_GOAL"
                best_market = {"market": "ANYTIME_GOAL", "p": round(p_scores_1plus, 3),
                               "fair_odds": _american(p_scores_1plus)}
            elif 0.30 <= p_scores_2plus <= 0.45:
                edge_class = "STRONG_2_PLUS"
                best_market = {"market": "2_PLUS_GOALS", "p": round(p_scores_2plus, 3),
                               "fair_odds": _american(p_scores_2plus)}

            rows.append({
                "league": league.upper(),
                "matchup": f"{away} @ {home}",
                "game_date": (g.get("date") or "")[:10],  # date the pick to kickoff -> dedup + clean settle
                "player": info.get("name", player_name),
                "team": info["team"],
                "opp_team": away if is_home else home,
                "is_home": is_home,
                "season_gpm": info["gpm"],
                "opp_elo": opp_elo,
                "opp_defense_mult": round(opp_defense_mult, 3),
                "expected_goals": round(expected_goals, 3),
                "p_scores_1_plus": round(p_scores_1plus, 3),
                "p_scores_2_plus": round(p_scores_2plus, 3),
                "fair_odds_1_plus": _american(p_scores_1plus),
                "fair_odds_2_plus": _american(p_scores_2plus),
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
    ]:
        all_rows.extend(_process_league(state_file, league))

    # World Cup fixtures come from the MODEL's authoritative upcoming card list
    # (worldcup_cards.json) rather than the thin state file, which lags the model's
    # 5-day scoreboard window -- so scorer props align 1:1 with the matches shown
    # on worldcup.html. opp strength flows in via the de-vigged book line on the
    # card (favourite's foe is weaker -> higher scoring chance).
    wc_cards = _load(os.path.join(DATA_DIR, "worldcup_cards.json")).get("cards") or []
    wc_games = [{
        "home_team": c.get("home"), "away_team": c.get("away"),
        "date": c.get("date"), "status": "scheduled",
        # map the de-vigged home win prob to a rough opp elo so the defense
        # adjustment still works (50% -> 1500 neutral; strong fav -> weak foe).
        "home_elo": 1500 + (float(c.get("p_home") or 0.5) - 0.5) * 600,
        "away_elo": 1500 + (float(c.get("p_away") or 0.5) - 0.5) * 600,
    } for c in wc_cards]
    all_rows.extend(_process_league("", "worldcup", games_override=wc_games))

    all_rows.sort(key=lambda r: -r["p_scores_1_plus"])
    strong = [r for r in all_rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players_projected": len(all_rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_DB),
        "method_note": "P(score 1+) = 1 - exp(-lambda) where lambda = season_gpm × opp_defense × home_boost. "
                       "STRONG_GOAL: 60-75%% (10%%+ edge vs -130 book breakeven). "
                       "STRONG_2_PLUS: 30-45%% (vs typical +300 book line).",
        "rows": all_rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[goalscorer] {o['n_players_projected']} players, {o['n_strong_edges']} strong edges -> {OUT}")
