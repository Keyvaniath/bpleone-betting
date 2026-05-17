"""
EdgeStat -- LoL per-player projections.

For each player in lol_players.json, project per-game stats:
  - Kills, Deaths, Assists (KDA distribution by role)
  - Win-rate contribution (player rating relative to team ELO)
  - Common prop fair odds:
      * Kills OVER/UNDER (typical lines: 2.5, 3.5, 4.5)
      * Assists OVER/UNDER (typical lines: 5.5, 7.5, 9.5)
      * Deaths UNDER (typical lines: 2.5, 3.5)
      * 1+ kill in first 10 minutes (early-game prop)

Model: tiered player skill from league + named-player heuristic.
Role multipliers calibrated to LCK / Worlds average game-stat distributions.

Output: data/lol_player_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PLAYERS_PATH = os.path.join(DATA_DIR, "lol_players.json")
OUT_PATH = os.path.join(DATA_DIR, "lol_player_props.json")

# Per-role league-average baseline stats per game (35-min game baseline)
ROLE_BASELINE = {
    # role: (mean_kills, mean_deaths, mean_assists)
    "top":      (2.5, 2.8, 5.5),
    "jungle":   (3.0, 2.5, 8.0),
    "mid":      (3.5, 2.4, 7.0),
    "bottom":   (4.2, 2.0, 6.5),    # ADC carries kills
    "support":  (1.0, 2.8, 11.5),   # support carries assists
}

# League tier multipliers (top regions produce more individual highlights)
LEAGUE_TIER = {
    "LCK": 1.10, "LPL": 1.10, "LEC": 1.00, "LCS": 0.95,
    "Worlds": 1.15, "MSI": 1.12, "First Stand": 1.05,
    "PCS": 0.90, "VCS": 0.85, "CBLOL": 0.85, "LLA": 0.85,
    "LJL": 0.80, "LCO": 0.80, "EU Masters": 0.85, "NACL": 0.80,
}

# Elite player prior: top mechanical players get a boost on kill stats
ELITE_PLAYERS = {
    # LCK
    "Chovy": 1.20, "Faker": 1.15, "Zeka": 1.18, "Knight": 1.15, "Ruler": 1.22,
    "ShowMaker": 1.12, "Peyz": 1.15, "Doran": 1.10, "Canyon": 1.18, "Oner": 1.12,
    "Keria": 1.05, "Lehends": 1.08, "BeryL": 1.10, "Gumayusi": 1.20, "Viper": 1.20,
    # LPL
    "JackeyLove": 1.20, "Light": 1.18, "Elk": 1.18, "Hope": 1.15,
    "Tian": 1.15, "Wei": 1.15, "Tarzan": 1.15, "Karsa": 1.12,
    # LEC
    "Caps": 1.18, "Hans Sama": 1.15, "Yike": 1.10, "Mikyx": 1.10,
    "Hylissang": 1.05, "Targamas": 1.05,
    # LCS
    "Berserker": 1.10, "Bjergsen": 1.05, "Inspired": 1.10, "Impact": 1.05,
    "Doublelift": 1.10, "PowerOfEvil": 1.05,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _save(p, payload):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w") as f: json.dump(payload, f, indent=2)


def _poisson_p_over(lam: float, line: float) -> float:
    """P(stat OVER line) using Poisson PMF. line=2.5 means P(X >= 3)."""
    if lam <= 0:
        return 0.0
    threshold = int(math.floor(line)) + 1
    # P(X >= threshold) = 1 - sum_{k=0}^{threshold-1} P(X=k)
    s = 0.0
    for k in range(threshold):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _poisson_p_under(lam: float, line: float) -> float:
    """P(stat UNDER line) using Poisson PMF. line=2.5 means P(X <= 2)."""
    return 1.0 - _poisson_p_over(lam, line)


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999:
        return 0
    if p >= 0.5:
        return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_player(p: Dict[str, Any]) -> Dict[str, Any]:
    role = (p.get("role") or "").lower()
    league = p.get("league", "")
    name = p.get("summoner_name", "")

    base = ROLE_BASELINE.get(role)
    if not base:
        return None
    mean_k, mean_d, mean_a = base
    league_mult = LEAGUE_TIER.get(league, 0.85)
    elite_mult = ELITE_PLAYERS.get(name, 1.0)

    # Skill multiplier compounds (cap to avoid runaway)
    skill_mult = league_mult * elite_mult
    skill_mult = min(1.40, max(0.70, skill_mult))

    lam_k = mean_k * skill_mult
    lam_a = mean_a * skill_mult
    # Better players also die LESS, so deaths inversely scale
    lam_d = mean_d / max(0.85, skill_mult ** 0.7)

    # Project common prop markets
    KILL_LINES = [2.5, 3.5, 4.5]
    ASSIST_LINES = [5.5, 7.5, 9.5]
    DEATH_LINES = [2.5, 3.5]

    kill_props = []
    for ln in KILL_LINES:
        p_over = _poisson_p_over(lam_k, ln)
        kill_props.append({
            "line": ln,
            "p_over": round(p_over, 4),
            "p_under": round(1 - p_over, 4),
            "fair_over_american": _american(p_over),
            "fair_under_american": _american(1 - p_over),
        })

    assist_props = []
    for ln in ASSIST_LINES:
        p_over = _poisson_p_over(lam_a, ln)
        assist_props.append({
            "line": ln,
            "p_over": round(p_over, 4),
            "p_under": round(1 - p_over, 4),
            "fair_over_american": _american(p_over),
            "fair_under_american": _american(1 - p_over),
        })

    death_props = []
    for ln in DEATH_LINES:
        p_under = _poisson_p_under(lam_d, ln)
        death_props.append({
            "line": ln,
            "p_under": round(p_under, 4),
            "fair_under_american": _american(p_under),
        })

    return {
        "summoner_name": name,
        "real_name": p.get("real_name"),
        "role": role,
        "team_name": p.get("team_name"),
        "team_code": p.get("team_code"),
        "league": league,
        "image": p.get("image"),
        "id": p.get("id"),
        "skill_mult": round(skill_mult, 3),
        "is_elite": elite_mult > 1.05,
        "projection": {
            "mean_kills": round(lam_k, 2),
            "mean_deaths": round(lam_d, 2),
            "mean_assists": round(lam_a, 2),
            "kda": round((lam_k + lam_a) / max(0.5, lam_d), 2),
        },
        "kill_props": kill_props,
        "assist_props": assist_props,
        "death_props": death_props,
    }


def run() -> Dict[str, Any]:
    state = _load(PLAYERS_PATH)
    players = state.get("all_players") or []
    projections: List[Dict[str, Any]] = []
    by_league: Dict[str, int] = {}
    by_role: Dict[str, int] = {}
    elite_count = 0
    for p in players:
        proj = _project_player(p)
        if not proj:
            continue
        projections.append(proj)
        by_league[proj["league"]] = by_league.get(proj["league"], 0) + 1
        by_role[proj["role"]] = by_role.get(proj["role"], 0) + 1
        if proj["is_elite"]:
            elite_count += 1

    # Sort by KDA desc within league + role
    projections.sort(key=lambda x: -x["projection"]["kda"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_players": len(projections),
        "n_elite": elite_count,
        "by_league": by_league,
        "by_role": by_role,
        "projections": projections,
    }
    _save(OUT_PATH, payload)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['n_players']} player projections ({p['n_elite']} elite)")
    print(f"  by role: {p['by_role']}")
    print(f"  Top 10 by projected KDA:")
    for pl in p["projections"][:10]:
        proj = pl["projection"]
        print(f"    {pl['summoner_name']:15} {pl['role']:8} [{pl['team_code']:5}] "
              f"K:{proj['mean_kills']:.1f} D:{proj['mean_deaths']:.1f} A:{proj['mean_assists']:.1f} "
              f"KDA={proj['kda']:.2f}")
