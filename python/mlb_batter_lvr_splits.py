"""
EdgeStat -- MLB BATTER vs L/R pitcher handedness splits.

Brandon asked for deeper player splits. This module:
  1. For each batter in today's posted lineup
  2. Identifies the opposing starter's throwing hand (matchups.json)
  3. Pulls batter's season vsL / vsR splits from MLB Stats API
  4. Compares OPS in the relevant split vs the batter's overall OPS
  5. Applies a log-odds shift to base 1+hit / 1+HR probabilities

Shift size:
   +.100 OPS above overall in the relevant split  ->  +0.30 logit on hit
                                                       +0.40 logit on HR
   shrunk by sample size: w = PA / (PA + 30) so a 30-PA split is half-trusted

Skips batters with < 15 split PA (sample too small).

Output: data/mlb_batter_lvr_splits.json
"""
from __future__ import annotations

import os
import json
import math
import time
import urllib.request
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_batter_lvr_splits.json")
STATS_API = "https://statsapi.mlb.com/api/v1/people/{aid}/stats?stats=statSplits&group=hitting&season={season}&sitCodes={code}"

SHRINK_PRIOR_PA = 80          # 2026-05-21: was 30, too loose. Tightened — small-sample
                              # splits (e.g. 90 PA) now get ~0.53 weight instead of 0.75.
MIN_SPLIT_PA = 15
MAX_DELTA_OPS = 0.150         # 2026-05-21 new: cap delta to prevent outlier OPS swings
                              # (e.g. Juan Soto 1.111 vs 0.696 -> delta 0.415 -> adj 58% HR)
                              # from blowing up the logit shift.
LEAGUE_OPS = 0.720


def _http(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


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


def _fetch_split(athlete_id, vs_code, season):
    """Get vsL (vl) or vsR (vr) split for one batter."""
    url = STATS_API.format(aid=athlete_id, season=season, code=vs_code)
    data = _http(url)
    if not data: return None
    for s in (data.get("stats") or []):
        for sp in (s.get("splits") or []):
            stat = sp.get("stat") or {}
            pa = int(stat.get("plateAppearances") or 0)
            if pa < 1: continue
            return {
                "pa": pa,
                "ab": int(stat.get("atBats") or 0),
                "hits": int(stat.get("hits") or 0),
                "hr": int(stat.get("homeRuns") or 0),
                "avg": float(stat.get("avg") or 0),
                "obp": float(stat.get("obp") or 0),
                "slg": float(stat.get("slg") or 0),
                "ops": float(stat.get("ops") or 0),
                "k": int(stat.get("strikeOuts") or 0),
            }
    return None


def _split_shift(split: Dict[str, Any], season_ops: float):
    """Compute log-odds shift from split vs season average.

    2026-05-21: tightened to prevent outlier OPS swings from producing
    unrealistic HR probabilities (e.g. Soto 58% HR in a single game).
      - SHRINK_PRIOR_PA bumped 30 -> 80 (Bayesian prior more skeptical)
      - delta_ops clamped to +/- MAX_DELTA_OPS (0.150) before scaling
      - hit_shift clamp +/- 0.5 (was 0.8)
      - hr_shift clamp +/- 0.6 (was 1.0)
    """
    if not split: return (0.0, 0.0)
    pa = split.get("pa") or 0
    if pa < MIN_SPLIT_PA: return (0.0, 0.0)
    ops = split.get("ops") or 0
    raw_delta = ops - (season_ops or LEAGUE_OPS)
    # Cap delta_ops so a single hot split can't dominate
    delta_ops = _clamp(raw_delta, -MAX_DELTA_OPS, MAX_DELTA_OPS)
    # Shrinkage based on PA (Bayesian: more PA -> more weight on split)
    w = pa / (pa + SHRINK_PRIOR_PA)
    # +0.100 OPS above season -> +0.30 logit on hit, +0.40 on HR
    hit_shift = w * (delta_ops / 0.100) * 0.30
    hr_shift = w * (delta_ops / 0.100) * 0.40
    return (_clamp(hit_shift, -0.5, 0.5), _clamp(hr_shift, -0.6, 0.6))


def _season_ops_from_advanced(name: str, adv_idx: Dict[str, Any]) -> float:
    """Clean per-batter season-OPS baseline: PA-weighted mean of the batter's
    home/away SHRUNK OPS from mlb_batter_advanced_splits. Falls back to the league
    prior. Replaces a last-14 proxy that collapsed to a 0.5 FLOOR for ~40% of
    batters, which inflated every vsL/vsR delta (and thus adj_p_1_plus_hit/hr)."""
    b = adv_idx.get((name or "").strip().lower())
    if not b:
        return LEAGUE_OPS
    sp = b.get("splits") or {}
    h, a = sp.get("home") or {}, sp.get("away") or {}

    def _num(x):
        try:
            return float(x) if x is not None else None
        except Exception:
            return None

    ho, ao = _num(h.get("ops_shrunk")), _num(a.get("ops_shrunk"))
    hp, ap = _num(h.get("pa")) or 0.0, _num(a.get("pa")) or 0.0
    if ho is not None and ao is not None and (hp + ap) > 0:
        return (hp * ho + ap * ao) / (hp + ap)
    return ho if ho is not None else ao if ao is not None else LEAGUE_OPS


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    season = dt.date.today().year

    # Index batter base props by name
    by_name = {}
    for b in (batter_logs.get("batters") or []):
        by_name[(b.get("name") or "").lower()] = b
    # Clean season-OPS baseline source (PA-weighted home/away shrunk OPS).
    adv = _load(os.path.join(DATA_DIR, "mlb_batter_advanced_splits.json"))
    adv_idx = {(b.get("name") or "").strip().lower(): b
               for b in (adv.get("batters") or []) if b.get("name")}

    output: List[Dict[str, Any]] = []
    n_fetched = 0

    for g in (matchups.get("games") or []):
        mu = g.get("matchup")
        home_sp = g.get("home_pitcher") or {}
        away_sp = g.get("away_pitcher") or {}
        lineups = g.get("lineups") or {}

        for batter_list, opp_sp, side in (
            (lineups.get("home") or [], away_sp, "HOME"),
            (lineups.get("away") or [], home_sp, "AWAY"),
        ):
            opp_hand = opp_sp.get("hand") if isinstance(opp_sp, dict) else None
            if opp_hand not in ("L", "R"): continue
            vs_code = "vl" if opp_hand == "L" else "vr"

            for batter in batter_list:
                bname = (batter.get("name") or "").lower()
                blog = by_name.get(bname)
                if not blog: continue
                base_props = blog.get("props") or {}
                base_hit_p = (base_props.get("1_plus_hit") or {}).get("p")
                base_hr_p = (base_props.get("1_plus_hr") or {}).get("p")
                if base_hit_p is None: continue

                # Clean per-batter season-OPS baseline (PA-weighted home/away shrunk
                # OPS from advanced splits; league-prior fallback). Replaces a last-14
                # proxy that collapsed to a 0.5 floor for ~40% of batters and inflated
                # the platoon delta / adj_p_1_plus_hit/hr that the hit/HR YN props use.
                season_ops_est = _clamp(_season_ops_from_advanced(bname, adv_idx), 0.400, 1.200)

                athlete_id = batter.get("id")
                if not athlete_id: continue
                split = _fetch_split(athlete_id, vs_code, season)
                n_fetched += 1
                if not split or split.get("pa", 0) < MIN_SPLIT_PA: continue

                hit_shift, hr_shift = _split_shift(split, season_ops_est)
                adj_hit_p = _sigmoid(_logit(base_hit_p) + hit_shift)
                adj_hr_p = _sigmoid(_logit(max(base_hr_p or 0.05, 0.02)) + hr_shift)

                hit_delta = (adj_hit_p - base_hit_p) * 100
                hr_delta = (adj_hr_p - (base_hr_p or 0)) * 100

                output.append({
                    "matchup": mu,
                    "side": side,
                    "batter": batter.get("name"),
                    "team_abbr": blog.get("team_abbr"),
                    "athlete_id": athlete_id,
                    "opp_pitcher": opp_sp.get("name") if isinstance(opp_sp, dict) else None,
                    "opp_hand": opp_hand,
                    "split_pa": split.get("pa"),
                    "split_ops": split.get("ops"),
                    "split_avg": split.get("avg"),
                    "split_hr": split.get("hr"),
                    "season_ops_estimate": round(season_ops_est, 3),
                    "ops_delta_in_split": round(split.get("ops", 0) - season_ops_est, 3),
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
                })
                time.sleep(0.04)   # be gentle with MLB Stats API

    # Rank by hit_delta
    top_hit_boost = sorted(output, key=lambda x: -x["hit_delta_pp"])[:15]
    top_hit_fade = sorted(output, key=lambda x: x["hit_delta_pp"])[:10]
    top_hr_boost = sorted(output, key=lambda x: -x["hr_delta_pp"])[:10]

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "season": season,
        "n_batters_analyzed": len(output),
        "n_api_calls": n_fetched,
        "shrinkage_prior_pa": SHRINK_PRIOR_PA,
        "min_split_pa": MIN_SPLIT_PA,
        "top_15_hit_boost": top_hit_boost,
        "top_10_hit_fade": top_hit_fade,
        "top_10_hr_boost": top_hr_boost,
        "all_batters": output,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB batter LvR splits: {p['n_batters_analyzed']} batters analyzed ({p['n_api_calls']} API calls)")
    print(f"\nTop 8 LvR hit boosts:")
    for x in p["top_15_hit_boost"][:8]:
        print(f"  {x['batter'][:22]:22s} vs {x['opp_hand']}HP {x['opp_pitcher'][:18]:18s} "
              f"split OPS {x['split_ops']:.3f} ({x['split_pa']} PA) "
              f"base={x['base_p_1_plus_hit']*100:.0f}% -> adj={x['adj_p_1_plus_hit']*100:.0f}% "
              f"(d {x['hit_delta_pp']:+.1f}pp)")
    print(f"\nTop 5 LvR HR boosts:")
    for x in p["top_10_hr_boost"][:5]:
        print(f"  {x['batter'][:22]:22s} vs {x['opp_hand']}HP {x['split_hr']} HR in {x['split_pa']} PA "
              f"base HR={x['base_p_1_plus_hr']*100:.1f}% -> adj={x['adj_p_1_plus_hr']*100:.1f}% "
              f"(d {x['hr_delta_pp']:+.2f}pp)")
