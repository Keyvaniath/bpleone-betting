"""
EdgeStat -- REAL factor decomposition for the Play of the Day.

For tonight's POD game, computes the marginal contribution of each
factor to the model's projected fair_total / p_home_win. Replaces the
old seed mock data that hardcoded "Yamamoto vs Darvish".

Output: data/pod_factor_decomp.json
   {
     "matchup": "LAD @ SDP",
     "label": "UNDER_7.5",
     "factors": [
       {"name": "Starting Pitcher (Ohtani vs Vasquez)",
        "contribution": -0.42, "unit": "runs",
        "detail": "Ohtani ERA 0.82 vs Vasquez 2.68; -0.42 runs to total"},
       ...
     ]
   }

Each factor's contribution is in "expected runs added/subtracted from
the model's fair_total" -- positive = pushes total UP, negative = pushes
total DOWN. UNDER bets want negative-sum factors.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "pod_factor_decomp.json")

LEAGUE_ERA = 4.20
LEAGUE_OPS = 0.720
LEAGUE_CARRY = 0.50
LEAGUE_TEMP = 72


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _find_pod_game(today: Dict[str, Any], matchups: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find the game matching today's POD."""
    pod = today.get("play_of_day") or {}
    pod_mu = pod.get("matchup")
    if not pod_mu: return None
    for g in (matchups.get("games") or []):
        if g.get("matchup") == pod_mu:
            return g
    return None


def _factor_starting_pitchers(g: Dict[str, Any]) -> Dict[str, Any]:
    """Better starting pitchers -> lower total runs (negative contribution)."""
    home_p = g.get("home_pitcher") or {}
    away_p = g.get("away_pitcher") or {}
    home_era = (home_p.get("season") or {}).get("era") or LEAGUE_ERA
    away_era = (away_p.get("season") or {}).get("era") or LEAGUE_ERA
    avg_era = (home_era + away_era) / 2
    # Each 1.0 ERA below league average -> ~ -0.55 runs to total
    contribution = -((LEAGUE_ERA - avg_era) * 0.55)
    home_name = (home_p.get("name") or "?").split()[-1]
    away_name = (away_p.get("name") or "?").split()[-1]
    return {
        "name": f"Starting Pitcher ({away_name} vs {home_name})",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"{away_name} ERA {away_era:.2f} vs {home_name} ERA {home_era:.2f} (avg {avg_era:.2f} vs league {LEAGUE_ERA:.2f})",
    }


def _factor_lineup(g: Dict[str, Any]) -> Dict[str, Any]:
    """Strong lineups -> higher total runs (positive contribution)."""
    home = g.get("home") or {}
    away = g.get("away") or {}
    home_ops = home.get("ops") or LEAGUE_OPS
    away_ops = away.get("ops") or LEAGUE_OPS
    avg_ops = (home_ops + away_ops) / 2
    contribution = (avg_ops - LEAGUE_OPS) * 4.5   # +.080 OPS -> +0.36 runs
    return {
        "name": "Lineup Strength (OPS)",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"avg team OPS {avg_ops:.3f} vs league {LEAGUE_OPS:.3f}",
    }


def _factor_bullpen(g: Dict[str, Any]) -> Dict[str, Any]:
    """Tired bullpens -> higher late-inning runs (positive contribution)."""
    bullpens = g.get("bullpens") or {}
    home_ip2d = (bullpens.get("home") or {}).get("ip_2d") or 0
    away_ip2d = (bullpens.get("away") or {}).get("ip_2d") or 0
    avg_ip = (home_ip2d + away_ip2d) / 2
    # Each IP above 4.0 baseline -> +0.05 runs
    contribution = (avg_ip - 4.0) * 0.05
    return {
        "name": "Bullpen Freshness (IP last 2d)",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"avg pen IP last 2d: {avg_ip:.1f} (>4 = tired)",
    }


def _factor_park(g: Dict[str, Any]) -> Dict[str, Any]:
    """Pitcher's parks suppress runs; hitter's parks inflate. Use carry_index proxy."""
    wx = g.get("weather") or {}
    carry = wx.get("carry_index") or LEAGUE_CARRY
    contribution = (carry - LEAGUE_CARRY) * 1.2
    park = g.get("park") or "?"
    return {
        "name": f"Park Factor ({park})",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"carry index {carry:.2f} vs neutral {LEAGUE_CARRY:.2f}",
    }


def _factor_weather(g: Dict[str, Any]) -> Dict[str, Any]:
    """Warm weather + wind out -> higher runs. Cold or indoor -> lower."""
    wx = g.get("weather") or {}
    if wx.get("is_indoor"):
        return {"name": "Weather (Indoor)", "contribution": -0.1, "unit": "runs",
                 "detail": "Indoor game - no wind/temp variance"}
    temp = wx.get("temp_f") or LEAGUE_TEMP
    contribution = (temp - LEAGUE_TEMP) * 0.012
    wind = wx.get("wind_mph") or 0
    return {
        "name": f"Weather ({temp}F)",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"{temp}F (warmer = more carry), wind {wind} mph",
    }


def _factor_umpire(g: Dict[str, Any]) -> Dict[str, Any]:
    """Tight ump -> more Ks -> fewer runs (negative). Wide ump -> opposite."""
    ump = g.get("umpire") or {}
    k_mult = ump.get("ump_k_mult") or 1.0
    contribution = -(k_mult - 1.0) * 4.0   # K mult > 1 means more Ks -> fewer runs
    name = ump.get("ump_name") or "?"
    return {
        "name": f"Umpire ({name})",
        "contribution": round(contribution, 3),
        "unit": "runs",
        "detail": f"K mult {k_mult:.2f} (>1.0 = tight zone, fewer runs)",
    }


def _factor_pitcher_form(g: Dict[str, Any]) -> Dict[str, Any]:
    """Recent pitcher form (last 3 starts vs season)."""
    home_p = g.get("home_pitcher") or {}
    away_p = g.get("away_pitcher") or {}
    contributions = []
    for sp in (home_p, away_p):
        s = sp.get("season") or {}
        r = sp.get("recent") or {}
        s_era = s.get("era")
        r_era = r.get("era")
        if s_era is not None and r_era is not None:
            # Recent ERA significantly different from season - regression risk
            delta = r_era - s_era
            contributions.append(delta * 0.3)
    if not contributions:
        return {"name": "Pitcher Recent Form", "contribution": 0.0, "unit": "runs",
                 "detail": "no recent-form data"}
    return {
        "name": "Pitcher Recent Form (3 starts vs season)",
        "contribution": round(sum(contributions) / len(contributions), 3),
        "unit": "runs",
        "detail": "mean recent-vs-season ERA delta",
    }


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pod = today.get("play_of_day") or {}
    if not pod:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "error": "No POD set in today.json", "factors": []}
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    game = _find_pod_game(today, matchups)
    if not game:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "matchup": pod.get("matchup"), "label": pod.get("label"),
                    "error": "No matching game in matchups.json", "factors": []}
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    factors = [
        _factor_starting_pitchers(game),
        _factor_lineup(game),
        _factor_bullpen(game),
        _factor_park(game),
        _factor_weather(game),
        _factor_umpire(game),
        _factor_pitcher_form(game),
    ]
    total_contribution = round(sum(f["contribution"] for f in factors), 3)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "matchup": pod.get("matchup"),
        "label": pod.get("label"),
        "model_fair_total": (game.get("model") or {}).get("fair_total"),
        "market_total": (game.get("market") or {}).get("total"),
        "factors": factors,
        "total_contribution_runs": total_contribution,
        "note": ("Each factor is the marginal expected-runs contribution to "
                  "the game total. Positive = pushes total UP (favors OVER). "
                  "Negative = favors UNDER. Sum across factors approximates "
                  "the model's edge vs league baseline."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"POD factor decomp: {p.get('matchup')} {p.get('label')}")
    if p.get("error"):
        print(f"  Error: {p['error']}")
    else:
        print(f"  Model fair_total: {p.get('model_fair_total')} | Market: {p.get('market_total')}")
        for f in p.get("factors", []):
            sign = "+" if f["contribution"] >= 0 else ""
            print(f"  {f['name']:50s} {sign}{f['contribution']:+.3f} runs -- {f['detail']}")
        print(f"  TOTAL: {p['total_contribution_runs']:+.3f} runs vs baseline")
