"""
EdgeStat -- MLB BATTER situational-splits module.

Brandon asked for "deeper player splits." Each batter's last-14 prop
projection assumes neutral conditions. In reality:
  - Some batters hit dramatically better at home vs road (.300 home / .230 road
    is real and stable for many)
  - Some batters destroy day games (vision / circadian) vs night games
  - The TODAY game has a specific home/away assignment + day/night time

This module:
  1. Parses each batter's player_gamelogs.json (last 14 games -- has is_home,
     is_night, venue per game)
  2. Splits their hit/HR/K rates into:
        home  vs road  (sample size n_home, n_road)
        day   vs night (n_day, n_night)
  3. Determines today's situation for the batter from matchups.json:
        is the batter's team home or away?
        is the game scheduled for a day or night start?
  4. Applies a situational log-odds shift to the batter's neutral 1+hit prob
     (shrinkage prior of 10 games -- needs material data to move probabilities)

Output: data/mlb_batter_situational_splits.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_situational_splits.json")

# Shrinkage prior for split rates (need this many games before split signal
# overpowers the league baseline)
SPLIT_PRIOR_N = 10

LEAGUE_HIT_RATE = 0.260   # league-average batting average baseline


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _logit(p):
    p = _clamp(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    if z > 500: return 1.0
    if z < -500: return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _compute_splits(games: List[Dict[str, Any]]):
    """Return per-situation aggregated rates."""
    home_pa, home_h, home_hr, home_k = 0, 0, 0, 0
    road_pa, road_h, road_hr, road_k = 0, 0, 0, 0
    day_pa, day_h, day_hr, day_k = 0, 0, 0, 0
    night_pa, night_h, night_hr, night_k = 0, 0, 0, 0

    for g in games:
        ab = g.get("ab") or 0
        pa = g.get("pa") or ab
        if pa <= 0:
            continue
        h = g.get("hits") or 0
        hr = g.get("hr") or 0
        k = g.get("k") or 0
        if g.get("is_home"):
            home_pa += pa; home_h += h; home_hr += hr; home_k += k
        else:
            road_pa += pa; road_h += h; road_hr += hr; road_k += k
        if g.get("is_night"):
            night_pa += pa; night_h += h; night_hr += hr; night_k += k
        else:
            day_pa += pa; day_h += h; day_hr += hr; day_k += k

    def _rates(pa, h, hr, k):
        if pa <= 0: return {"pa": 0, "hit_rate": None, "hr_rate": None, "k_rate": None}
        return {"pa": pa, "n_games": None,
                "hit_rate": round(h / pa, 4), "hr_rate": round(hr / pa, 4),
                "k_rate": round(k / pa, 4)}

    home = _rates(home_pa, home_h, home_hr, home_k)
    road = _rates(road_pa, road_h, road_hr, road_k)
    day = _rates(day_pa, day_h, day_hr, day_k)
    night = _rates(night_pa, night_h, night_hr, night_k)
    return home, road, day, night


def _shrunk_logodds(rate, pa, baseline=LEAGUE_HIT_RATE, prior_n=SPLIT_PRIOR_N):
    """Shrink a hit-rate observation toward league baseline."""
    if rate is None or pa <= 0: return None
    # Convert PA to "effective N games" by dividing by ~3.5 PA/game
    n_games = pa / 3.5
    w = n_games / (n_games + prior_n)
    shrunk = w * rate + (1 - w) * baseline
    return _logit(shrunk) - _logit(baseline)


def _today_situation(matchups: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """For each batter today, return {batter_name: {is_home, is_night, opponent}}"""
    out = {}
    for g in (matchups.get("games") or []):
        home_team = g.get("home_team") or g.get("home")
        away_team = g.get("away_team") or g.get("away")
        time_str = (g.get("time") or "").lower()
        # Parse "20:05" or "1:35 PM" as night if hour >= 17 (5pm+)
        is_night = False
        try:
            # Try HH:MM 24h
            if ":" in time_str:
                hour = int(time_str.split(":")[0])
                is_night = hour >= 17
        except Exception:
            pass

        lineups = g.get("lineups") or {}
        for batter in (lineups.get("home") or []):
            nm = batter.get("name")
            if nm:
                out[nm.lower()] = {
                    "is_home": True, "is_night": is_night,
                    "opponent": away_team, "venue": g.get("venue"),
                }
        for batter in (lineups.get("away") or []):
            nm = batter.get("name")
            if nm:
                out[nm.lower()] = {
                    "is_home": False, "is_night": is_night,
                    "opponent": home_team, "venue": g.get("venue"),
                }
    return out


def run() -> Dict[str, Any]:
    gamelogs = _load(os.path.join(DATA_DIR, "player_gamelogs.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    today_sit = _today_situation(matchups)

    # Index batter base props by name
    by_name = {}
    for b in (batter_logs.get("batters") or []):
        by_name[(b.get("name") or "").lower()] = b

    bpid = gamelogs.get("by_player_id") or {}

    out_records = []
    for pid, prec in bpid.items():
        if not isinstance(prec, dict): continue
        if prec.get("kind") != "batter": continue
        name = prec.get("name") or ""
        if not name: continue
        nlower = name.lower()
        sit = today_sit.get(nlower)
        if not sit: continue   # batter not in today's lineup -- skip

        games = prec.get("games") or []
        if not games: continue

        home, road, day, night = _compute_splits(games)

        # Base prop probability
        blog = by_name.get(nlower)
        if not blog:
            continue
        base_hit_p = (blog.get("props", {}).get("1_plus_hit") or {}).get("p")
        base_hr_p = (blog.get("props", {}).get("1_plus_hr") or {}).get("p")
        if base_hit_p is None: continue

        # Compute log-odds shift from situational splits
        # 1) home/road effect
        if sit["is_home"]:
            split_logodds = _shrunk_logodds(home.get("hit_rate"), home.get("pa", 0))
        else:
            split_logodds = _shrunk_logodds(road.get("hit_rate"), road.get("pa", 0))
        hit_shift = (split_logodds or 0.0) * 0.6   # dampened weight

        # 2) day/night effect
        if sit["is_night"]:
            tod_logodds = _shrunk_logodds(night.get("hit_rate"), night.get("pa", 0))
        else:
            tod_logodds = _shrunk_logodds(day.get("hit_rate"), day.get("pa", 0))
        hit_shift += (tod_logodds or 0.0) * 0.5

        # HR shift: use HR rate splits (smaller absolute moves -- /2 weight)
        hr_split_logodds = None
        if sit["is_home"]:
            if home.get("hr_rate") is not None and home.get("pa", 0) > 0:
                hr_split_logodds = _shrunk_logodds(home.get("hr_rate"), home.get("pa", 0),
                                                    baseline=0.030)
        else:
            if road.get("hr_rate") is not None and road.get("pa", 0) > 0:
                hr_split_logodds = _shrunk_logodds(road.get("hr_rate"), road.get("pa", 0),
                                                    baseline=0.030)
        hr_shift = (hr_split_logodds or 0.0) * 0.5

        # Clamp
        hit_shift = _clamp(hit_shift, -0.7, 0.7)
        hr_shift = _clamp(hr_shift, -0.9, 0.9)

        adj_hit_p = _sigmoid(_logit(base_hit_p) + hit_shift)
        adj_hr_p = _sigmoid(_logit(max(base_hr_p or 0.05, 0.02)) + hr_shift)

        hit_delta = (adj_hit_p - base_hit_p) * 100
        hr_delta = (adj_hr_p - (base_hr_p or 0)) * 100

        rec = {
            "batter": name,
            "team_abbr": blog.get("team_abbr"),
            "is_home_today": sit["is_home"],
            "is_night_today": sit["is_night"],
            "opponent": sit.get("opponent"),
            "venue": sit.get("venue"),
            "home_pa": home.get("pa"),
            "home_hit_rate": home.get("hit_rate"),
            "home_hr_rate": home.get("hr_rate"),
            "road_pa": road.get("pa"),
            "road_hit_rate": road.get("hit_rate"),
            "road_hr_rate": road.get("hr_rate"),
            "day_pa": day.get("pa"),
            "day_hit_rate": day.get("hit_rate"),
            "night_pa": night.get("pa"),
            "night_hit_rate": night.get("hit_rate"),
            "hit_logodds_shift": round(hit_shift, 3),
            "hr_logodds_shift": round(hr_shift, 3),
            "base_p_1_plus_hit": round(base_hit_p, 4),
            "adj_p_1_plus_hit": round(adj_hit_p, 4),
            "hit_delta_pp": round(hit_delta, 2),
            "base_p_1_plus_hr": round(base_hr_p or 0, 4),
            "adj_p_1_plus_hr": round(adj_hr_p, 4),
            "hr_delta_pp": round(hr_delta, 2),
            "fair_yes_1_hit": _american(adj_hit_p),
            "fair_yes_1_hr": _american(adj_hr_p),
        }
        out_records.append(rec)

    # Rank by hit_delta (biggest situational boosts first)
    top_situational_boost_hit = sorted(out_records, key=lambda x: -x["hit_delta_pp"])[:15]
    top_situational_fade_hit = sorted(out_records, key=lambda x: x["hit_delta_pp"])[:10]
    top_situational_boost_hr = sorted(out_records, key=lambda x: -x["hr_delta_pp"])[:10]

    # Home-only batters (today is home and they crush at home)
    home_today = [r for r in out_records if r["is_home_today"]]
    home_today.sort(key=lambda x: -(x["hit_delta_pp"]))
    # Night-only batters (today is night and they hit better at night)
    night_today = [r for r in out_records if r["is_night_today"]]
    night_today.sort(key=lambda x: -(x["hit_delta_pp"]))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_batters_in_lineups": len(out_records),
        "league_hit_rate_baseline": LEAGUE_HIT_RATE,
        "shrinkage_prior_games": SPLIT_PRIOR_N,
        "top_15_situational_boost_hit": top_situational_boost_hit,
        "top_10_situational_fade_hit": top_situational_fade_hit,
        "top_10_situational_boost_hr": top_situational_boost_hr,
        "all_batters": out_records,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB batter situational splits: {p['n_batters_in_lineups']} batters in today's lineups")
    print(f"\nTop 10 situational HIT boosts (home/away + day/night):")
    for x in p["top_15_situational_boost_hit"][:10]:
        venue = "HOME" if x["is_home_today"] else "ROAD"
        tod = "NIGHT" if x["is_night_today"] else "DAY"
        print(f"  {x['batter'][:22]:22s} ({x['team_abbr']:3s}) [{venue}/{tod}] "
              f"base={x['base_p_1_plus_hit']*100:.0f}% adj={x['adj_p_1_plus_hit']*100:.0f}% "
              f"(d {x['hit_delta_pp']:+.1f}pp) fair={x.get('fair_yes_1_hit','?')}")
    print(f"\nTop 5 situational HR boosts:")
    for x in p["top_10_situational_boost_hr"][:5]:
        venue = "HOME" if x["is_home_today"] else "ROAD"
        print(f"  {x['batter'][:22]:22s} [{venue}] base={x['base_p_1_plus_hr']*100:.1f}% "
              f"adj={x['adj_p_1_plus_hr']*100:.1f}% (d {x['hr_delta_pp']:+.2f}pp)")
