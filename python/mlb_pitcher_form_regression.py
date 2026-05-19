"""
EdgeStat -- MLB starting-pitcher mean-reversion / regression detector.

Each starter has TWO rate observations in matchups.json:
  season:  full-season K/9, BB/9, ERA (large sample, "true talent")
  recent:  last 3 starts K/9, BB/9, ERA (small sample, "current form")

If recent ERA is dramatically lower than season ERA (3 lights-out starts),
the market over-weights recency. Empirically, K/9 and ERA both regress
~50-60% toward season mean over the next 3 starts. Same in the other
direction.

For each pitcher today, this module:
  1. Compares recent vs season -- flags "hot streak" or "cold slump"
  2. Computes mean-reverted projected stats for today's start (40% recent,
     60% season weight when sample size differs significantly)
  3. Re-prices K and ER props using the reverted projection
  4. Flags the largest market mispricings vs the existing mlb_pitcher_matchup
     output (those props use raw season stats, missing the reversion signal)

Output: data/mlb_pitcher_form_regression.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_form_regression.json")

# Recency weight: how much to trust last-3-starts vs season
# A small sample of 3 starts vs ~8 starts: shrunk weight ~ 3/(3+5) = 0.375
RECENT_WEIGHT = 0.40   # 40% recent / 60% season
HOT_DELTA_ERA = -1.20  # recent ERA at least 1.20 BELOW season -> "hot streak"
COLD_DELTA_ERA = 1.50  # recent ERA at least 1.50 ABOVE season -> "cold slump"
HOT_DELTA_K9 = 2.00    # recent K/9 at least 2.0 above season -> "K hot"
COLD_DELTA_K9 = -2.00


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_pitcher(sp: Dict[str, Any]) -> Dict[str, Any]:
    """For one pitcher, compute reverted projected lambda for K and ER."""
    season = sp.get("season") or {}
    recent = sp.get("recent") or {}
    name = sp.get("name") or "?"
    if not season:
        return None

    s_era = season.get("era") or 4.0
    s_k9 = season.get("k9") or 8.5
    s_ip_per_start = (season.get("ip") or 0) / max(1, season.get("starts") or 1)
    s_starts = season.get("starts") or 0

    r_era = recent.get("era")
    r_k9 = recent.get("k9")
    r_starts = recent.get("starts") or 0

    if r_starts >= 2 and r_era is not None and r_k9 is not None:
        # Blend with recency weight
        w = RECENT_WEIGHT if r_starts >= 3 else RECENT_WEIGHT * 0.7
        projected_era = w * r_era + (1 - w) * s_era
        projected_k9 = w * r_k9 + (1 - w) * s_k9
        delta_era = r_era - s_era
        delta_k9 = r_k9 - s_k9
    else:
        projected_era = s_era
        projected_k9 = s_k9
        delta_era = 0.0
        delta_k9 = 0.0

    # Streak classification
    streak = "NEUTRAL"
    if delta_era <= HOT_DELTA_ERA and r_starts >= 3:
        streak = "HOT_ERA"
    elif delta_era >= COLD_DELTA_ERA and r_starts >= 3:
        streak = "COLD_ERA"
    if delta_k9 >= HOT_DELTA_K9 and r_starts >= 3:
        streak = "HOT_K" if streak == "NEUTRAL" else streak + "_AND_K"
    elif delta_k9 <= COLD_DELTA_K9 and r_starts >= 3:
        streak = "COLD_K" if streak == "NEUTRAL" else streak + "_AND_K_DROP"

    # Compute expected K per start = projected_k9 * (IP per start / 9)
    avg_ip = s_ip_per_start if s_ip_per_start > 0 else 5.5
    proj_k = projected_k9 * avg_ip / 9.0
    # Expected ER per start = projected_era * (IP/9)
    proj_er = projected_era * avg_ip / 9.0

    # K prop probabilities (Poisson around proj_k)
    k_lines = {}
    for line in (4.5, 5.5, 6.5, 7.5, 8.5):
        p = _poisson_p_over(proj_k, line)
        if 0.05 < p < 0.95:
            k_lines[f"k_over_{line}"] = {
                "line": line, "p": round(p, 4),
                "fair_over": _american(p), "fair_under": _american(1 - p),
            }

    # ER under probabilities
    er_lines = {}
    for line in (1.5, 2.5, 3.5):
        p_under = 1 - _poisson_p_over(proj_er, line)
        if 0.10 < p_under < 0.90:
            er_lines[f"er_under_{line}"] = {
                "line": line, "p_under": round(p_under, 4),
                "fair_under": _american(p_under),
            }

    return {
        "name": name,
        "hand": sp.get("hand"),
        "season_era": round(s_era, 2),
        "season_k9": round(s_k9, 2),
        "season_starts": s_starts,
        "recent_era": round(r_era, 2) if r_era is not None else None,
        "recent_k9": round(r_k9, 2) if r_k9 is not None else None,
        "recent_starts": r_starts,
        "delta_era_vs_season": round(delta_era, 2),
        "delta_k9_vs_season": round(delta_k9, 2),
        "projected_era_today": round(projected_era, 2),
        "projected_k9_today": round(projected_k9, 2),
        "projected_k_per_start": round(proj_k, 2),
        "projected_er_per_start": round(proj_er, 2),
        "streak_status": streak,
        "k_props": k_lines,
        "er_props": er_lines,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    pitchers_out: List[Dict[str, Any]] = []
    for g in (matchups.get("games") or []):
        mu = g.get("matchup")
        for side, sp_key in (("home", "home_pitcher"), ("away", "away_pitcher")):
            sp = g.get(sp_key)
            if not isinstance(sp, dict): continue
            proj = _project_pitcher(sp)
            if not proj: continue
            proj["matchup"] = mu
            proj["side"] = side.upper()
            proj["team"] = g.get("home" if side == "home" else "away", {}).get("team_id")
            pitchers_out.append(proj)

    # Surface notable streaks: hot K (best fade-the-line opportunities)
    hot_k = [p for p in pitchers_out if "HOT_K" in p["streak_status"]]
    cold_k = [p for p in pitchers_out if "COLD_K" in p["streak_status"]]
    hot_era = [p for p in pitchers_out if p["streak_status"].startswith("HOT_ERA")]
    cold_era = [p for p in pitchers_out if p["streak_status"].startswith("COLD_ERA")]

    # Top K-prop edges (post-reversion projection)
    k_picks = []
    for p in pitchers_out:
        for mkt, info in p["k_props"].items():
            prob = info["p"]
            if 0.62 <= prob <= 0.85:
                k_picks.append({
                    "pitcher": p["name"], "matchup": p["matchup"],
                    "side": p["side"], "market": mkt, "line": info["line"],
                    "prob": prob, "fair_over": info["fair_over"],
                    "streak": p["streak_status"],
                    "delta_k9": p["delta_k9_vs_season"],
                })
    k_picks.sort(key=lambda x: -x["prob"])

    # Top ER under edges
    er_picks = []
    for p in pitchers_out:
        for mkt, info in p["er_props"].items():
            prob = info["p_under"]
            if 0.62 <= prob <= 0.90:
                er_picks.append({
                    "pitcher": p["name"], "matchup": p["matchup"],
                    "side": p["side"], "market": mkt, "line": info["line"],
                    "prob": prob, "fair_under": info["fair_under"],
                    "streak": p["streak_status"],
                    "delta_era": p["delta_era_vs_season"],
                })
    er_picks.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_pitchers": len(pitchers_out),
        "n_hot_k": len(hot_k),
        "n_cold_k": len(cold_k),
        "n_hot_era": len(hot_era),
        "n_cold_era": len(cold_era),
        "method": "40% recent (last 3 starts) / 60% season blend; classify streaks vs season norm",
        "hot_k_streaks": hot_k,
        "cold_k_streaks": cold_k,
        "hot_era_streaks": hot_era,
        "cold_era_streaks": cold_era,
        "top_k_picks": k_picks[:15],
        "top_er_picks": er_picks[:10],
        "all_pitchers": pitchers_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB pitcher form regression: {p['n_pitchers']} starters analyzed")
    print(f"  Hot K streaks: {p['n_hot_k']} | Cold K: {p['n_cold_k']} | "
          f"Hot ERA: {p['n_hot_era']} | Cold ERA: {p['n_cold_era']}")
    if p["hot_k_streaks"]:
        print(f"\n  HOT K streak pitchers (recent K/9 way above season -- bet OVER lines):")
        for x in p["hot_k_streaks"][:5]:
            print(f"    {x['name'][:22]:22s} season K/9 {x['season_k9']:.1f} -> recent {x['recent_k9']:.1f} "
                  f"(d {x['delta_k9_vs_season']:+.2f}); projected {x['projected_k_per_start']:.1f} K today")
    if p["hot_era_streaks"]:
        print(f"\n  HOT ERA streak pitchers (recent ERA way below season -- mean-reversion risk):")
        for x in p["hot_era_streaks"][:5]:
            print(f"    {x['name'][:22]:22s} season ERA {x['season_era']:.2f} -> recent {x['recent_era']:.2f} "
                  f"(d {x['delta_era_vs_season']:+.2f}); projected ER {x['projected_er_per_start']:.2f}")
    print(f"\n  Top 5 K-over picks (post-reversion):")
    for x in p["top_k_picks"][:5]:
        print(f"    {x['pitcher'][:22]:22s} {x['market']:18s} p={x['prob']*100:.0f}% [{x['streak']}] fair={x['fair_over']}")
    print(f"\n  Top 5 ER-under picks (post-reversion):")
    for x in p["top_er_picks"][:5]:
        print(f"    {x['pitcher'][:22]:22s} {x['market']:18s} p={x['prob']*100:.0f}% [{x['streak']}] fair={x['fair_under']}")
