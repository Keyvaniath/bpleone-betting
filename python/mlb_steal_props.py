"""
EdgeStat -- MLB Stolen Base prop projections.

Niche but high-edge market. SB success rate depends almost entirely on:
  - Pitcher delivery time to the plate (slow = vulnerable)
  - Catcher pop time (the throw to second)
  - Runner sprint speed
  - Runner SB rate vs lefty/righty starter

For each game, identifies the top SB candidates and projects:
  - P(SB attempt in game) given lineup spot + starter handedness
  - P(SB success | attempt) given pitcher delivery + catcher pop
  - P(SB >= 1) per runner

Source: pre-computed splits from Statcast / Baseball Savant baked in as
constants. Updates yearly. Fast-fallback if no specific data found.

Output: data/mlb_steal_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_steal_props.json")

# 2025 SB-relevant runner pool (sprint speed >= 28.5 ft/s + SB rate > 70%)
# Format: lower name -> { sprint_ft_s, sb_rate_pct, projected_attempts_per_game }
SB_RUNNERS = {
    "elly de la cruz":   {"sprint": 30.7, "sb_rate": 0.84, "att_per_game": 0.42, "sb_per_g": 0.35},
    "trea turner":       {"sprint": 30.3, "sb_rate": 0.88, "att_per_game": 0.30, "sb_per_g": 0.26},
    "esteury ruiz":      {"sprint": 30.5, "sb_rate": 0.79, "att_per_game": 0.55, "sb_per_g": 0.43},
    "corbin carroll":    {"sprint": 30.1, "sb_rate": 0.86, "att_per_game": 0.30, "sb_per_g": 0.26},
    "bobby witt jr":     {"sprint": 30.4, "sb_rate": 0.82, "att_per_game": 0.30, "sb_per_g": 0.25},
    "ronald acuna jr":   {"sprint": 29.8, "sb_rate": 0.85, "att_per_game": 0.32, "sb_per_g": 0.27},
    "jose ramirez":      {"sprint": 28.9, "sb_rate": 0.83, "att_per_game": 0.24, "sb_per_g": 0.20},
    "francisco lindor":  {"sprint": 28.7, "sb_rate": 0.85, "att_per_game": 0.20, "sb_per_g": 0.17},
    "wyatt langford":    {"sprint": 29.1, "sb_rate": 0.81, "att_per_game": 0.20, "sb_per_g": 0.16},
    "byron buxton":      {"sprint": 30.0, "sb_rate": 0.88, "att_per_game": 0.18, "sb_per_g": 0.16},
    "jorge polanco":     {"sprint": 28.5, "sb_rate": 0.72, "att_per_game": 0.15, "sb_per_g": 0.11},
    "jose altuve":       {"sprint": 28.4, "sb_rate": 0.78, "att_per_game": 0.18, "sb_per_g": 0.14},
    "shohei ohtani":     {"sprint": 30.0, "sb_rate": 0.84, "att_per_game": 0.25, "sb_per_g": 0.21},
    "fernando tatis jr": {"sprint": 29.5, "sb_rate": 0.83, "att_per_game": 0.22, "sb_per_g": 0.18},
    "julio rodriguez":   {"sprint": 29.7, "sb_rate": 0.77, "att_per_game": 0.20, "sb_per_g": 0.15},
    "kyle tucker":       {"sprint": 28.8, "sb_rate": 0.82, "att_per_game": 0.18, "sb_per_g": 0.15},
    "luis robert":       {"sprint": 30.2, "sb_rate": 0.85, "att_per_game": 0.22, "sb_per_g": 0.19},
    "ozzie albies":      {"sprint": 28.6, "sb_rate": 0.79, "att_per_game": 0.15, "sb_per_g": 0.12},
    "jose siri":         {"sprint": 29.4, "sb_rate": 0.80, "att_per_game": 0.18, "sb_per_g": 0.14},
    "anthony volpe":     {"sprint": 29.0, "sb_rate": 0.78, "att_per_game": 0.20, "sb_per_g": 0.16},
}

# Pitcher delivery times (median seconds plate to 2nd). Slower = SB-vulnerable.
# Right-handed start ~1.30s from set; left-handed ~1.40s.
# Only flag exceptionally slow ones; the rest get the default modifier.
SLOW_PITCHERS = {
    "merrill kelly":    {"time": 1.55, "tag": "slow"},
    "patrick corbin":   {"time": 1.45, "tag": "moderate"},
    "lance lynn":       {"time": 1.50, "tag": "slow"},
    "shota imanaga":    {"time": 1.42, "tag": "moderate"},
    "kyle hendricks":   {"time": 1.40, "tag": "moderate"},
    "kyle gibson":      {"time": 1.48, "tag": "slow"},
}

# Catcher pop times (median seconds, glove to 2nd base bag). League avg = 1.99s
# Below 1.92 = elite arm (caught stealing edge), above 2.05 = weak.
WEAK_ARM_CATCHERS = {
    "salvador perez":   2.07,
    "willson contreras": 2.06,
    "yainer diaz":      2.04,
    "j.t. realmuto":    1.90,  # elite -- runners avoid
    "patrick bailey":   1.92,  # above avg
    "shea langeliers":  1.94,
    "francisco alvarez": 2.03,
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


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    games = matchups.get("games") or today.get("games") or []
    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        lineups = g.get("lineups") or {}
        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            opp_side = "away" if side == "home" else "home"
            opp_pitcher_raw = g.get(f"{opp_side}_pitcher")
            opp_pitcher_name = opp_pitcher_raw if isinstance(opp_pitcher_raw, str) else (opp_pitcher_raw or {}).get("name")
            # Find catcher of opposite side (catches our pitcher? No, opposite — catcher catches own pitcher)
            opp_lineup = lineups.get(opp_side) or []
            opp_catcher = None
            for b in opp_lineup:
                if isinstance(b, dict) and (b.get("pos") or "").upper() in ("C", "CATCHER"):
                    opp_catcher = (b.get("name") or "").lower()
                    break

            # Pitcher delivery modifier
            slow_data = SLOW_PITCHERS.get((opp_pitcher_name or "").lower(), {})
            pitcher_mult = 1.15 if slow_data.get("tag") == "slow" else (1.05 if slow_data.get("tag") == "moderate" else 1.0)

            # Catcher arm modifier
            opp_catcher_pop = WEAK_ARM_CATCHERS.get(opp_catcher, 1.99)
            if opp_catcher_pop >= 2.05: catcher_mult = 1.15
            elif opp_catcher_pop >= 2.00: catcher_mult = 1.05
            elif opp_catcher_pop <= 1.92: catcher_mult = 0.85  # elite arm, runners stay
            else: catcher_mult = 1.0

            # SB success rate adjustment
            success_mult = 1.0 + 0.5 * (opp_catcher_pop - 1.99)  # 1 std slower = +50% success
            success_mult = max(0.7, min(1.3, success_mult))

            for batter in lineup:
                if not isinstance(batter, dict): continue
                name = batter.get("name") or batter.get("fullName")
                runner = SB_RUNNERS.get((name or "").lower())
                if not runner: continue

                base_att = runner["att_per_game"]
                base_rate = runner["sb_rate"]
                exp_attempts = base_att * pitcher_mult * catcher_mult
                exp_success_rate = min(0.95, base_rate * success_mult)
                p_sb_1_plus = 1 - math.exp(-exp_attempts * exp_success_rate)  # Poisson approx
                p_sb_2_plus = max(0, 1 - math.exp(-exp_attempts * exp_success_rate) -
                                  exp_attempts * exp_success_rate * math.exp(-exp_attempts * exp_success_rate))

                # Edge classification (vs typical -150 book line for SB Y/N)
                edge_class = "NONE"
                if p_sb_1_plus >= 0.45:
                    edge_class = "STRONG_1PLUS_YES"
                elif p_sb_1_plus <= 0.18 and runner["att_per_game"] >= 0.20:
                    edge_class = "STRONG_1PLUS_NO"  # this runner is usually stealing, but elite C arm blocks it
                elif p_sb_1_plus >= 0.35:
                    edge_class = "STANDARD"

                rows.append({
                    "matchup": matchup_str,
                    "runner": name,
                    "team": batter.get("team_abbr") or batter.get("team"),
                    "order": batter.get("order"),
                    "sprint_ft_s": runner["sprint"],
                    "career_sb_rate": runner["sb_rate"],
                    "vs_pitcher": opp_pitcher_name,
                    "pitcher_delivery_tag": slow_data.get("tag", "average"),
                    "vs_catcher": opp_catcher,
                    "catcher_pop_time": opp_catcher_pop,
                    "exp_attempts": round(exp_attempts, 3),
                    "exp_success_rate": round(exp_success_rate, 3),
                    "p_sb_1_plus": round(p_sb_1_plus, 3),
                    "p_sb_2_plus": round(p_sb_2_plus, 3),
                    "fair_odds_1_plus_yes": _american(p_sb_1_plus),
                    "edge_class": edge_class,
                })

    rows.sort(key=lambda r: -r["p_sb_1_plus"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_runners": len(rows),
        "n_strong": len(strong),
        "n_runners_in_db": len(SB_RUNNERS),
        "method_note": "SB attempts modeled from runner base rate × pitcher delivery × catcher arm. "
                       "Sprint speed + career SB% are runner inputs; delivery time + pop time are matchup.",
        "rows": rows[:60],
        "strong_edges": strong[:20],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[steal-props] {o['n_runners']} runners, {o['n_strong']} strong edges -> {OUT}")
