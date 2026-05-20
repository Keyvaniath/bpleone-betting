"""
EdgeStat -- MLB lineup strength analyzer.

For each posted lineup tonight, compute a weighted strength score using
each batter's last_14 OPS-equivalent (avg + slg approximation) weighted
by batting order position. Top of order batters get 1.1x weight, middle
batters 1.0x, bottom batters 0.85x (lineup multiplier values).

Surfaces:
   ELITE lineups (weighted score >= 0.860) -- offensive threat
   WEAK lineups (weighted score <= 0.660)  -- struggling offense
   MISMATCHES: weak lineup vs an ace pitcher (compound under signal)

Output: data/mlb_lineup_strength.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_lineup_strength.json")

# Position multipliers (top of order > middle > bottom)
ORDER_WEIGHTS = {1: 1.10, 2: 1.10, 3: 1.08, 4: 1.05, 5: 1.0,
                  6: 0.95, 7: 0.90, 8: 0.85, 9: 0.80}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _batter_ops_proxy(blog: Dict[str, Any]) -> float:
    """Real OPS from last_14 stats (OBP + SLG)."""
    s14 = blog.get("stats_last_14") or {}
    ab = s14.get("ab") or 0
    h = s14.get("h") or 0
    bb = s14.get("bb") or 0
    tb = s14.get("tb") or 0
    if ab <= 0: return 0.700   # league avg fallback
    pa = ab + bb
    obp = (h + bb) / max(1, pa)
    slg = tb / max(1, ab)
    ops = obp + slg
    # Cap at 1.5 (extreme) and 0.3 (extreme low)
    return max(0.30, min(1.50, ops))


def _lineup_score(lineup: List[Dict[str, Any]], batters_by_name: Dict[str, Any]) -> Dict[str, Any]:
    """Weighted score for one lineup."""
    if not lineup: return {"score": None, "n_known": 0}
    total_weight = 0
    total_score = 0
    n_known = 0
    contributors = []
    for batter in lineup:
        order = batter.get("order")
        if not order or order > 9: continue
        weight = ORDER_WEIGHTS.get(order, 1.0)
        nlower = (batter.get("name") or "").lower()
        blog = batters_by_name.get(nlower)
        if not blog: continue
        ops_proxy = _batter_ops_proxy(blog)
        total_weight += weight
        total_score += weight * ops_proxy
        n_known += 1
        contributors.append({
            "order": order, "name": batter.get("name"),
            "ops_proxy": round(ops_proxy, 3), "weight": weight,
        })
    if total_weight == 0:
        return {"score": None, "n_known": 0}
    return {
        "score": round(total_score / total_weight, 3),
        "n_known": n_known,
        "contributors": contributors,
    }


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    batter_logs = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))

    batters_by_name = {}
    for b in (batter_logs.get("batters") or []):
        batters_by_name[(b.get("name") or "").lower()] = b

    results = []
    for g in (matchups.get("games") or []):
        lineups = g.get("lineups") or {}
        home_score = _lineup_score(lineups.get("home") or [], batters_by_name)
        away_score = _lineup_score(lineups.get("away") or [], batters_by_name)

        # Parse team abbreviations from matchup string "AWAY @ HOME"
        mu = g.get("matchup") or ""
        home_team_abbr = mu.split(" @ ")[1].strip() if " @ " in mu else g.get("home_team")
        away_team_abbr = mu.split(" @ ")[0].strip() if " @ " in mu else g.get("away_team")

        home_sp = g.get("home_pitcher") or {}
        away_sp = g.get("away_pitcher") or {}
        home_era = (home_sp.get("season") or {}).get("era")
        away_era = (away_sp.get("season") or {}).get("era")

        # Tag mismatches  -- thresholds calibrated to MLB league reality
        # League avg OPS ~ 0.720; elite teams 0.780+, weak teams sub-0.680
        def _classify(score):
            if score is None: return "?"
            if score >= 0.780: return "ELITE"
            if score >= 0.730: return "STRONG"
            if score >= 0.690: return "AVERAGE"
            if score >= 0.640: return "WEAK"
            return "FEEBLE"

        record = {
            "matchup": g.get("matchup"),
            "home_team": home_team_abbr,
            "away_team": away_team_abbr,
            "home_lineup_score": home_score.get("score"),
            "home_lineup_tier": _classify(home_score.get("score")),
            "home_n_known": home_score.get("n_known"),
            "away_lineup_score": away_score.get("score"),
            "away_lineup_tier": _classify(away_score.get("score")),
            "away_n_known": away_score.get("n_known"),
            "home_starter": home_sp.get("name"),
            "home_starter_era": home_era,
            "away_starter": away_sp.get("name"),
            "away_starter_era": away_era,
        }
        # Mismatch detector: weak lineup vs ace
        mismatches = []
        if home_score.get("score") and away_era is not None:
            if home_score["score"] >= 0.780 and away_era >= 4.50:
                mismatches.append(f"Home {record['home_team']} ELITE lineup ({home_score['score']:.3f}) vs away starter ERA {away_era:.2f} -- OVER signal")
            if home_score["score"] <= 0.660 and away_era <= 3.00:
                mismatches.append(f"Home {record['home_team']} weak lineup ({home_score['score']:.3f}) vs ACE {away_sp.get('name')} ({away_era:.2f}) -- compound UNDER")
        if away_score.get("score") and home_era is not None:
            if away_score["score"] >= 0.780 and home_era >= 4.50:
                mismatches.append(f"Away {record['away_team']} ELITE lineup ({away_score['score']:.3f}) vs home starter ERA {home_era:.2f} -- OVER signal")
            if away_score["score"] <= 0.660 and home_era <= 3.00:
                mismatches.append(f"Away {record['away_team']} weak lineup ({away_score['score']:.3f}) vs ACE {home_sp.get('name')} ({home_era:.2f}) -- compound UNDER")
        record["mismatch_signals"] = mismatches
        results.append(record)

    # Rank lineups by strength
    elite_lineups = []
    weak_lineups = []
    for r in results:
        if r["home_lineup_tier"] == "ELITE":
            elite_lineups.append({"team": r["home_team"], "score": r["home_lineup_score"],
                                    "matchup": r["matchup"], "vs_starter": r["away_starter"],
                                    "vs_era": r["away_starter_era"]})
        if r["away_lineup_tier"] == "ELITE":
            elite_lineups.append({"team": r["away_team"], "score": r["away_lineup_score"],
                                    "matchup": r["matchup"], "vs_starter": r["home_starter"],
                                    "vs_era": r["home_starter_era"]})
        if r["home_lineup_tier"] in ("WEAK", "FEEBLE"):
            weak_lineups.append({"team": r["home_team"], "score": r["home_lineup_score"],
                                  "matchup": r["matchup"], "tier": r["home_lineup_tier"]})
        if r["away_lineup_tier"] in ("WEAK", "FEEBLE"):
            weak_lineups.append({"team": r["away_team"], "score": r["away_lineup_score"],
                                  "matchup": r["matchup"], "tier": r["away_lineup_tier"]})

    elite_lineups.sort(key=lambda x: -(x["score"] or 0))
    weak_lineups.sort(key=lambda x: (x["score"] or 1))

    all_mismatches = []
    for r in results:
        for m in r["mismatch_signals"]:
            all_mismatches.append({"matchup": r["matchup"], "signal": m})

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(results),
        "elite_lineups_count": len(elite_lineups),
        "weak_lineups_count": len(weak_lineups),
        "n_mismatch_signals": len(all_mismatches),
        "elite_lineups": elite_lineups,
        "weak_lineups": weak_lineups,
        "mismatch_signals": all_mismatches,
        "games": results,
        "note": ("Lineup score = weighted-avg OPS proxy across all 9 batters "
                  "with top-of-order multipliers (1-2 hitters at 1.10x, 8-9 at 0.85x). "
                  "Mismatch detector flags ELITE-vs-weak-pitcher and weak-vs-ace "
                  "compound signals for over/under bets."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB lineup strength: {p['n_games']} games analyzed")
    print(f"  Elite lineups: {p['elite_lineups_count']} | Weak: {p['weak_lineups_count']} | Mismatches: {p['n_mismatch_signals']}")
    if p["elite_lineups"]:
        print(f"\n  Top 5 elite lineups:")
        for x in p["elite_lineups"][:5]:
            era_str = f"ERA {x['vs_era']:.2f}" if x.get("vs_era") else "?"
            print(f"    {x['team'][:25]:25s}  score {x['score']:.3f}  vs {(x.get('vs_starter') or '?')[:20]:20s} {era_str}")
    if p["weak_lineups"]:
        print(f"\n  Top 5 weak lineups:")
        for x in p["weak_lineups"][:5]:
            team = (x.get('team') or '?')[:25]
            print(f"    {team:25s}  score {x['score']:.3f}  [{x['tier']}]  ({x['matchup']})")
    if p["mismatch_signals"]:
        print(f"\n  Mismatch signals:")
        for m in p["mismatch_signals"][:5]:
            print(f"    [{m['matchup']}] {m['signal']}")
