"""
EdgeStat -- MLB starter expected pitch count + IP projection.

Brandon can use this to:
   identify starters likely to go deep (low bullpen risk, K-over likely)
   identify starters likely to come out early (bullpen exposure, hits more
     likely for opposing batters in later innings)

Method:
   recent_pc_avg = matchups.json pitch_count_history.avg_pc
   recent_trend = pitch_count_history.trend  (negative = pulled earlier)
   project_today_pc = recent_avg + trend * 1.0
   pitches_per_inning rate = recent_avg / recent_ip_per_start
   projected_ip = project_today_pc / pitches_per_inning
   Apply opp_lineup adjustment: high OBP teams force more pitches per IP

Output: data/mlb_starter_pitch_count.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_starter_pitch_count.json")

LEAGUE_OBP = 0.318


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _project_starter(sp: Dict[str, Any], opp_obp: float) -> Dict[str, Any]:
    if not isinstance(sp, dict): return None
    history = sp.get("pitch_count_history") or {}
    season = sp.get("season") or {}
    name = sp.get("name") or "?"
    avg_pc = history.get("avg_pc")
    trend = history.get("trend") or 0
    n_starts = history.get("n_starts") or 0
    if not avg_pc or n_starts < 2: return None

    # Project today's pitch count
    proj_pc = avg_pc + trend * 0.5
    proj_pc = max(60, min(110, proj_pc))

    # Pitches per IP rate
    season_ip = season.get("ip") or 0
    season_starts = season.get("starts") or 1
    ip_per_start_raw = season_ip / max(1, season_starts)
    # Sanity cap: starters never go 8+ IP per start on average. If higher,
    # season.starts is mislabeling reliever appearances or bullpen days.
    ip_per_start = min(7.5, max(3.0, ip_per_start_raw))

    # If avg_pc is suspiciously low (< 70), the pitcher has been used short
    # (relief / bullpen day / rookie). Skip -- don't pretend to project.
    if avg_pc < 65:
        return None

    pc_per_ip = avg_pc / ip_per_start
    # Sanity check: pc_per_ip should be 14-22 typical. Cap.
    pc_per_ip = min(22, max(13, pc_per_ip))

    # Adjust for opposing lineup OBP (more baserunners = more pitches per IP)
    obp_ratio = opp_obp / LEAGUE_OBP
    adj_pc_per_ip = pc_per_ip * obp_ratio

    # Project IP today
    proj_ip = proj_pc / adj_pc_per_ip
    # Cap at 8 IP (no one goes 9 unless complete game which is rare)
    proj_ip = min(8.0, max(2.5, proj_ip))

    # Classify depth: deep = 6+ IP, shallow = <5 IP
    if proj_ip >= 6.5: depth = "DEEP_GAME"
    elif proj_ip >= 5.5: depth = "TYPICAL"
    elif proj_ip >= 4.5: depth = "SHORT_LEASH"
    else: depth = "EARLY_HOOK"

    # K projection: K/9 * proj_ip
    k9 = season.get("k9") or 8.5
    proj_k = k9 * proj_ip / 9.0

    return {
        "pitcher": name,
        "hand": sp.get("hand"),
        "recent_avg_pc": round(avg_pc, 1),
        "recent_max_pc": history.get("max_pc"),
        "recent_trend_pc": round(trend, 1),
        "n_recent_starts": n_starts,
        "ip_per_start_season": round(ip_per_start, 2),
        "season_k9": round(k9, 2),
        "opp_obp": round(opp_obp, 3),
        "obp_ratio_vs_league": round(obp_ratio, 3),
        "projected_pitch_count": round(proj_pc, 1),
        "projected_ip_today": round(proj_ip, 2),
        "projected_k_today": round(proj_k, 2),
        "depth_tier": depth,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))

    results = []
    for g in (matchups.get("games") or []):
        mu = g.get("matchup")
        home = g.get("home") or {}
        away = g.get("away") or {}
        home_sp = g.get("home_pitcher") or {}
        away_sp = g.get("away_pitcher") or {}

        # Home pitcher faces away lineup
        h_proj = _project_starter(home_sp, away.get("obp") or LEAGUE_OBP)
        if h_proj:
            h_proj["matchup"] = mu
            h_proj["side"] = "HOME"
            h_proj["opp_team_ops"] = away.get("ops")
            results.append(h_proj)

        # Away pitcher faces home lineup
        a_proj = _project_starter(away_sp, home.get("obp") or LEAGUE_OBP)
        if a_proj:
            a_proj["matchup"] = mu
            a_proj["side"] = "AWAY"
            a_proj["opp_team_ops"] = home.get("ops")
            results.append(a_proj)

    # Tier counts
    from collections import Counter
    tier_counts = dict(Counter(r["depth_tier"] for r in results))

    # Sort by projected IP descending
    deep = sorted([r for r in results if r["depth_tier"] in ("DEEP_GAME","TYPICAL")],
                    key=lambda r: -r["projected_ip_today"])
    shallow = sorted([r for r in results if r["depth_tier"] in ("SHORT_LEASH","EARLY_HOOK")],
                       key=lambda r: r["projected_ip_today"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_starters": len(results),
        "tier_counts": tier_counts,
        "league_obp": LEAGUE_OBP,
        "deep_game_candidates": deep[:15],
        "early_hook_candidates": shallow[:10],
        "all_starters": results,
        "note": ("Projected pitch count + IP today driven by recent 5-start "
                  "avg, trend, season IP/start, and opposing lineup OBP. "
                  "DEEP_GAME = 6.5+ IP projected (K-over friendly, bullpen "
                  "shielded). EARLY_HOOK = <4.5 IP (bullpen exposure, "
                  "ER-over risk, opposing batters get late-game ABs)."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB starter pitch count: {p['n_starters']} starters projected")
    print(f"  Tiers: {p['tier_counts']}")
    print(f"\n  Top 5 DEEP_GAME candidates (go 6.5+ IP):")
    for r in p["deep_game_candidates"][:5]:
        print(f"    {r['pitcher'][:22]:22s}  proj IP {r['projected_ip_today']:.1f}  proj K {r['projected_k_today']:.1f}  "
              f"opp OBP {r['opp_obp']:.3f}  [{r['depth_tier']}]")
    print(f"\n  Top 5 EARLY_HOOK candidates (under 5 IP):")
    for r in p["early_hook_candidates"][:5]:
        print(f"    {r['pitcher'][:22]:22s}  proj IP {r['projected_ip_today']:.1f}  proj K {r['projected_k_today']:.1f}  "
              f"opp OBP {r['opp_obp']:.3f}  [{r['depth_tier']}]")
