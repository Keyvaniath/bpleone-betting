"""
EdgeStat -- MLB lineup quality index.

For each game on the slate, produces a normalized 0-100 quality score per
lineup (HOME, AWAY) by aggregating every starter's:
  - Recent-form OPS (last_14 games, real data preferred)
  - Season-long OPS
  - Power index (HR-rate proxy)
  - Hot/cold flag

Score interpretation:
  85+  Elite lineup (1-2 per slate, e.g. peak Dodgers / Yankees stack)
  70-84 Above average
  55-69 League average
  40-54 Weak
  <40   Bottom-tier

Consumer modules:
  - Validates pitcher props (high-K vs weak lineup = STRONG_UNDER bias)
  - Boosts team total OVER for elite lineups
  - Boosts HR/TB props when entire lineup is hot

Method:
  Per-batter score = 50 + (OPS_real-0.72)*60 + power_bonus
  Lineup score = weighted_avg(top-9 batters), top-of-order weighted higher

Output: data/mlb_lineup_quality_index.json
  {
    "games": [
      {"matchup": "BOS @ NYY",
       "home": {"team": "NYY", "score": 78.4, "tier": "above_avg", "hot_count": 3},
       "away": {"team": "BOS", "score": 62.1, "tier": "league_avg", "hot_count": 1}}
    ]
  }
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_lineup_quality_index.json")


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


def _tier(score: float) -> str:
    # Calibrated against observed league spread (~48-72 range for full lineups
    # using split_ops). League midpoint ~52, elite stacks ~70+.
    if score >= 70: return "elite"
    if score >= 60: return "above_avg"
    if score >= 50: return "league_avg"
    if score >= 42: return "weak"
    return "bottom_tier"


def _order_weight(order: int) -> float:
    # Top-of-order batters drive more PAs; weight them ~25% higher
    if order <= 3: return 1.25
    if order <= 6: return 1.05
    return 0.85


def _batter_score(batter: Dict[str, Any],
                  lvr_idx: Dict[str, Any],
                  blog_idx: Dict[str, Any],
                  hot_set: set,
                  cold_set: set) -> Dict[str, Any]:
    """Score a single batter: 0-100 scale."""
    name = batter.get("name") or batter.get("fullName") or ""
    name_l = name.lower()
    lvr = lvr_idx.get(name_l, {})
    blog = blog_idx.get(name_l, {})

    # Priority: real_recent OPS > matchup split_ops > season_ops_estimate > neutral
    # (season_ops_estimate is known unreliable; matchup split_ops is the
    # actual vs-handedness OPS which best reflects tonight's matchup)
    blog_stats = (blog.get("season_stats") or {}) if blog else {}
    real_ops = _safe(blog_stats.get("ops"))
    split_ops = _safe(lvr.get("split_ops"))
    season_ops = _safe(lvr.get("season_ops_estimate"), 0.720)
    if real_ops > 0.300:
        ops_used = real_ops
    elif split_ops > 0.300:
        ops_used = split_ops
    elif season_ops > 0.300:
        ops_used = season_ops
    else:
        ops_used = 0.720

    # Power bonus from ISO (SLG - AVG approx)
    iso = _safe(blog_stats.get("iso"))
    power_bonus = min(15, max(0, (iso - 0.150) * 100))

    # Base score from OPS spread
    base = 50.0 + (ops_used - 0.720) * 60.0 + power_bonus

    # Hot/cold modifiers
    if name_l in hot_set:
        base += 5
    if name_l in cold_set:
        base -= 5

    base = max(10.0, min(100.0, base))
    return {
        "name": name,
        "order": batter.get("order") or 9,
        "ops_used": round(ops_used, 3),
        "power_bonus": round(power_bonus, 1),
        "score": round(base, 1),
        "is_hot": name_l in hot_set,
        "is_cold": name_l in cold_set,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    lvr = _load(os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    hot_streaks = _load(os.path.join(DATA_DIR, "hot_streaks.json"))

    lvr_idx = {(r.get("batter") or "").lower(): r for r in (lvr.get("all_batters") or [])}
    blog_idx = {(b.get("name") or "").lower(): b for b in (batter_logs.get("batters") or [])}
    hot_set = {(b.get("name") or "").lower() for b in (hot_streaks.get("hot_batters") or [])}
    cold_set = {(b.get("name") or "").lower() for b in (hot_streaks.get("cold_batters") or [])}

    games = matchups.get("games") or []
    out_games: List[Dict[str, Any]] = []
    all_lineup_scores: List[float] = []

    for g in games:
        matchup = g.get("matchup") or ""
        lineups = g.get("lineups") or {}
        side_out: Dict[str, Any] = {}
        for side in ("home", "away"):
            lineup = lineups.get(side) or []
            if not lineup:
                continue
            batters_scored = []
            weighted_sum = 0.0
            weight_total = 0.0
            for b in lineup[:9]:
                if not isinstance(b, dict): continue
                bs = _batter_score(b, lvr_idx, blog_idx, hot_set, cold_set)
                batters_scored.append(bs)
                w = _order_weight(bs["order"])
                weighted_sum += bs["score"] * w
                weight_total += w

            lineup_score = weighted_sum / max(weight_total, 1.0) if weight_total else 50.0
            lineup_score = round(lineup_score, 1)
            all_lineup_scores.append(lineup_score)

            hot_count = sum(1 for b in batters_scored if b["is_hot"])
            cold_count = sum(1 for b in batters_scored if b["is_cold"])
            avg_power = round(sum(b["power_bonus"] for b in batters_scored) / max(len(batters_scored), 1), 1)

            team_abbr = (g.get(side) or {}).get("team") if isinstance(g.get(side), dict) else side.upper()

            side_out[side] = {
                "team": team_abbr,
                "score": lineup_score,
                "tier": _tier(lineup_score),
                "hot_count": hot_count,
                "cold_count": cold_count,
                "avg_power_bonus": avg_power,
                "n_batters": len(batters_scored),
                "top_3_batters": [{"name": b["name"], "score": b["score"]} for b in batters_scored[:3]],
            }

        if side_out:
            out_games.append({
                "matchup": matchup,
                "home": side_out.get("home"),
                "away": side_out.get("away"),
                "advantage": _advantage_label(side_out),
            })

    # Aggregate stats
    n_elite = sum(1 for g in out_games for side in ("home", "away")
                  if (g.get(side) or {}).get("tier") == "elite")
    n_bottom = sum(1 for g in out_games for side in ("home", "away")
                   if (g.get(side) or {}).get("tier") == "bottom_tier")

    avg_score = round(sum(all_lineup_scores) / max(len(all_lineup_scores), 1), 1)

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(out_games),
        "n_lineups": len(all_lineup_scores),
        "n_elite_lineups": n_elite,
        "n_bottom_lineups": n_bottom,
        "avg_lineup_score": avg_score,
        "method_note": "Per-batter score = 50 + (OPS-0.72)*60 + ISO_power_bonus. "
                       "Lineup score = order-weighted avg (top-of-order +25%). "
                       "Hot/cold modifiers +/- 5 from hot_streaks.json. "
                       "Used by pitcher/team/HR modules as a quality multiplier.",
        "games": out_games,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


def _advantage_label(side_out: Dict[str, Any]) -> str:
    home_score = (side_out.get("home") or {}).get("score", 50)
    away_score = (side_out.get("away") or {}).get("score", 50)
    diff = home_score - away_score
    if diff >= 10: return "HOME_STRONG"
    if diff >= 4: return "HOME_LEAN"
    if diff <= -10: return "AWAY_STRONG"
    if diff <= -4: return "AWAY_LEAN"
    return "EVEN"


if __name__ == "__main__":
    o = run()
    print(f"[lineup-qual] {o['n_games']} games, {o['n_elite_lineups']} elite, "
          f"{o['n_bottom_lineups']} bottom, avg {o['avg_lineup_score']} -> {OUT}")
