"""
EdgeStat -- MLB BATTER vs STARTING PITCHER matchup edges.

This is the "deep-data" batter prop board Brandon wanted:
  - For each batter in TODAY's posted lineups
  - Adjust their base 1+hit / 2+hit / 1+HR probability by:
       (a) pitch-arsenal-weighted xwOBA matchup (matchups.json already has this --
           it's the pitcher's per-pitch usage * batter's xwOBA vs that pitch)
       (b) opposing pitcher's BAA / FIP (pitcher quality)
       (c) batter career-vs-this-pitcher (with shrinkage for tiny samples)

  Output: per-batter matchup-adjusted hit/HR probabilities, ranked by edge
  vs the batter's "neutral" baseline.

The point: surface batters whose matchup-adjusted hit prob is materially
HIGHER than their generic recent-form prob, so Brandon knows which batter
props to size up *today* vs which to fade.

Output: data/mlb_batter_sp_edges.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_sp_edges.json")

LEAGUE_XWOBA = 0.320
LEAGUE_BAA = 0.245
LEAGUE_FIP = 4.20
LEAGUE_K_RATE = 0.226   # league-avg per-PA K rate

# Shrinkage prior for career vs-pitcher matchup
CAREER_PRIOR_PA = 25   # need 25 PA before career data dominates baseline


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p):
    if p <= 0.001: return None
    if p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _logit(p):
    p = _clamp(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z):
    if z > 500: return 1.0
    if z < -500: return 0.0
    return 1.0 / (1.0 + math.exp(-z))


def _matchup_logodds_shift(batter: Dict[str, Any],
                            opp_sp: Optional[Dict[str, Any]]):
    """
    Return (hit_shift, hr_shift, k_shift) -- ADDITIVE log-odds shifts that
    represent how much the matchup moves probability from neutral baseline.

    Empirically calibrated coefficients (per std of pitcher quality * arsenal):
      hit_shift     in roughly [-0.7, +0.7]   (~ +/- 15 pp at 50% baseline)
      hr_shift      in roughly [-1.0, +1.0]
      k_shift       in roughly [-0.6, +0.6]
    """
    if not opp_sp:
        return (0.0, 0.0, 0.0)

    season = opp_sp.get("season") or {}
    baa = season.get("baa") or LEAGUE_BAA
    fip = season.get("fip") or LEAGUE_FIP
    k9 = season.get("k9") or 8.5

    # Pitcher-quality log-odds contribution
    # baa deviation: +/- 0.05 BAA from league -> +/- 0.4 logit on hit
    hit_shift_pitch = ((baa - LEAGUE_BAA) / 0.05) * 0.40
    # fip deviation: +/- 1.0 FIP from league -> +/- 0.5 logit on hr
    hr_shift_pitch = ((fip - LEAGUE_FIP) / 1.0) * 0.50
    # k9 deviation: +/- 2.0 K/9 -> +/- 0.4 logit on K
    k_shift_pitch = ((k9 - 8.5) / 2.0) * 0.40

    # Pitch-arsenal xwOBA matchup
    xwoba_info = batter.get("vs_pitcher_xwoba_matchup") or {}
    delta_xwoba = xwoba_info.get("delta_vs_league") or 0.0
    # +0.020 xwOBA above league -> +0.30 logit on hit, +0.40 on HR
    arsenal_hit_shift = (delta_xwoba / 0.020) * 0.30
    arsenal_hr_shift = (delta_xwoba / 0.020) * 0.40
    arsenal_k_shift = -(delta_xwoba / 0.020) * 0.20   # higher xwOBA -> lower K

    # Career vs-pitcher shrinkage
    career = batter.get("vs_pitcher_career") or {}
    ab = career.get("ab") or 0
    career_hit_shift = 0.0
    career_hr_shift = 0.0
    if ab >= 5:
        cavg = (career.get("hits") or 0) / max(1, ab)
        # Shrink toward .250 with prior of CAREER_PRIOR_PA
        w = ab / (ab + CAREER_PRIOR_PA)
        # Shift = w * (cavg - .250) / .080 * 0.50
        career_hit_shift = w * ((cavg - 0.250) / 0.080) * 0.50
        slg = career.get("slg") or 0.4
        career_hr_shift = w * ((slg - 0.400) / 0.150) * 0.30

    hit_shift = _clamp(hit_shift_pitch + arsenal_hit_shift + career_hit_shift, -1.2, 1.2)
    hr_shift = _clamp(hr_shift_pitch + arsenal_hr_shift + career_hr_shift, -1.5, 1.5)
    k_shift = _clamp(k_shift_pitch + arsenal_k_shift, -1.0, 1.0)
    return (hit_shift, hr_shift, k_shift)


def _shift_prob(base_p, logodds_shift):
    """Apply additive log-odds shift to a probability."""
    if base_p is None or base_p <= 0: return base_p
    return _sigmoid(_logit(base_p) + logodds_shift)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))

    # Index batters by name
    batters_by_name: Dict[str, Dict[str, Any]] = {}
    for b in (batter_logs.get("batters") or []):
        nm = (b.get("name") or "").lower()
        batters_by_name[nm] = b

    games_out: List[Dict[str, Any]] = []
    all_edges: List[Dict[str, Any]] = []

    for g in (matchups.get("games") or []):
        mu = g.get("matchup") or ""
        home_sp = g.get("home_pitcher") or {}
        away_sp = g.get("away_pitcher") or {}
        lineups = g.get("lineups") or {}
        home_lu = lineups.get("home") or []
        away_lu = lineups.get("away") or []

        per_batter: List[Dict[str, Any]] = []

        for batter_list, opp_sp, side in (
            (home_lu, away_sp, "HOME"),
            (away_lu, home_sp, "AWAY"),
        ):
            for b in batter_list:
                bname = (b.get("name") or "").lower()
                blog = batters_by_name.get(bname)
                if not blog: continue   # no recent-form baseline
                base_props = blog.get("props") or {}
                base_hit_p = (base_props.get("1_plus_hit") or {}).get("p")
                base_2h_p = (base_props.get("2_plus_hits") or {}).get("p")
                base_hr_p = (base_props.get("1_plus_hr") or {}).get("p")
                if base_hit_p is None: continue

                hit_shift, hr_shift, k_shift = _matchup_logodds_shift(b, opp_sp)

                adj_hit_p = _shift_prob(base_hit_p, hit_shift)
                adj_2h_p = _shift_prob(base_2h_p or 0.20, hit_shift * 1.10)   # 2H scales slightly more
                adj_hr_p = _shift_prob(max(base_hr_p or 0.05, 0.02), hr_shift)

                hit_delta = (adj_hit_p - base_hit_p) * 100
                hr_delta = (adj_hr_p - (base_hr_p or 0)) * 100

                xwoba_info = b.get("vs_pitcher_xwoba_matchup") or {}
                career = b.get("vs_pitcher_career") or {}
                ab_vs = career.get("ab") or 0

                rec = {
                    "matchup": mu,
                    "side": side,
                    "batter": b.get("name"),
                    "team_abbr": blog.get("team_abbr"),
                    "order": b.get("order"),
                    "pos": b.get("pos"),
                    "opp_pitcher": opp_sp.get("name") if opp_sp else None,
                    "opp_pitcher_hand": opp_sp.get("hand") if opp_sp else None,
                    "opp_pitcher_baa": (opp_sp.get("season") or {}).get("baa"),
                    "opp_pitcher_fip": (opp_sp.get("season") or {}).get("fip"),
                    "opp_pitcher_k9": (opp_sp.get("season") or {}).get("k9"),
                    "matchup_xwoba": xwoba_info.get("matchup_xwoba"),
                    "delta_vs_league_xwoba": xwoba_info.get("delta_vs_league"),
                    "career_vs_sp_ab": ab_vs,
                    "career_vs_sp_ops": career.get("ops") if ab_vs >= 5 else None,
                    "hit_logodds_shift": round(hit_shift, 3),
                    "hr_logodds_shift": round(hr_shift, 3),
                    "k_logodds_shift": round(k_shift, 3),
                    "base_p_1_plus_hit": round(base_hit_p, 4),
                    "adj_p_1_plus_hit": round(adj_hit_p, 4),
                    "hit_delta_pp": round(hit_delta, 2),
                    "base_p_1_plus_hr": round((base_hr_p or 0), 4),
                    "adj_p_1_plus_hr": round(adj_hr_p, 4),
                    "hr_delta_pp": round(hr_delta, 2),
                    "adj_p_2_plus_hits": round(adj_2h_p, 4),
                    "fair_yes_1_hit": _american(adj_hit_p),
                    "fair_yes_2_hit": _american(adj_2h_p),
                    "fair_yes_1_hr": _american(adj_hr_p),
                }
                per_batter.append(rec)
                all_edges.append(rec)

        games_out.append({
            "matchup": mu,
            "home_pitcher": home_sp.get("name") if isinstance(home_sp, dict) else home_sp,
            "away_pitcher": away_sp.get("name") if isinstance(away_sp, dict) else away_sp,
            "n_batters_analyzed": len(per_batter),
            "batters": per_batter,
        })

    # Top boosted (matchup INCREASES hit prob vs neutral form)
    top_boosted_hit = sorted(all_edges, key=lambda x: -x["hit_delta_pp"])[:15]
    top_boosted_hr = sorted(all_edges, key=lambda x: -x["hr_delta_pp"])[:15]
    # Top fade (matchup DECREASES hit prob)
    top_fade_hit = sorted(all_edges, key=lambda x: x["hit_delta_pp"])[:10]

    # Top adjusted absolute probabilities -- the BEST plays today
    top_hit_today = sorted(all_edges, key=lambda x: -x["adj_p_1_plus_hit"])[:15]
    top_hr_today = sorted(all_edges, key=lambda x: -x["adj_p_1_plus_hr"])[:10]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "n_batters_total": len(all_edges),
        "league_xwoba_baseline": LEAGUE_XWOBA,
        "league_baa_baseline": LEAGUE_BAA,
        "top_15_hit_boost": top_boosted_hit,
        "top_15_hr_boost": top_boosted_hr,
        "top_10_hit_fade": top_fade_hit,
        "top_15_hit_today_absolute": top_hit_today,
        "top_10_hr_today_absolute": top_hr_today,
        "games": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB batter-vs-SP edges: {p['n_batters_total']} batters across {p['n_games']} games")
    print(f"\nTop 10 matchup-boosted 1+HIT probabilities:")
    for x in p["top_15_hit_boost"][:10]:
        print(f"  {(x['batter'] or '?')[:22]:22s} ({x['team_abbr']}) vs {(x['opp_pitcher'] or '?')[:18]:18s} "
              f"base={x['base_p_1_plus_hit']*100:.0f}% -> adj={x['adj_p_1_plus_hit']*100:.0f}% "
              f"(+{x['hit_delta_pp']:.1f}pp) fair={x.get('fair_yes_1_hit','?')}")
    print(f"\nTop 5 matchup-boosted 1+HR probabilities:")
    for x in p["top_15_hr_boost"][:5]:
        print(f"  {(x['batter'] or '?')[:22]:22s} ({x['team_abbr']}) vs {(x['opp_pitcher'] or '?')[:18]:18s} "
              f"base={x['base_p_1_plus_hr']*100:.1f}% -> adj={x['adj_p_1_plus_hr']*100:.1f}% "
              f"(+{x['hr_delta_pp']:.2f}pp) fair={x.get('fair_yes_1_hr','?')}")
    print(f"\nTop 5 absolute 1+HIT probabilities today:")
    for x in p["top_15_hit_today_absolute"][:5]:
        print(f"  {(x['batter'] or '?')[:22]:22s} adj_p={x['adj_p_1_plus_hit']*100:.0f}% "
              f"vs {(x['opp_pitcher'] or '?')[:20]:20s} ({(x['opp_pitcher_hand'] or '?')}HP)")
