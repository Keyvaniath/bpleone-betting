"""
EdgeStat -- MLB pitcher matchup engine.

For each MLB game today (from matchups.json / today.json), looks up both
starting pitchers in mlb_pitcher_logs.json and surfaces:
  - Their K/9, ERA, last-N starts
  - Which pitcher has the bigger K edge vs prop line
  - Pitcher-vs-opposing-team-OBP advantage
  - "Strike out the side" candidates (high K/9 + low opp OBP)

Output: data/mlb_pitcher_matchup.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_matchup.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    # Index pitchers by name (case-insensitive)
    pitchers_by_name: Dict[str, Dict[str, Any]] = {}
    for p in (pitcher_logs.get("pitchers") or []):
        name = (p.get("name") or "").lower()
        pitchers_by_name[name] = p

    matchup_data: List[Dict[str, Any]] = []
    # Prefer matchups.json (has pitcher info); today.json games don't include pitcher dicts.
    games = matchups.get("games") or today.get("games") or []

    for g in games:
        # matchups.json: home_pitcher / away_pitcher are DICTS with .name field
        hp_raw = g.get("home_pitcher")
        ap_raw = g.get("away_pitcher")
        home_sp_name = hp_raw if isinstance(hp_raw, str) else (hp_raw or {}).get("name")
        away_sp_name = ap_raw if isinstance(ap_raw, str) else (ap_raw or {}).get("name")
        home_sp = pitchers_by_name.get((home_sp_name or "").lower())
        away_sp = pitchers_by_name.get((away_sp_name or "").lower())

        # Fallback: use matchups.json rich season blob
        if not home_sp and isinstance(hp_raw, dict) and hp_raw.get("season"):
            season = hp_raw.get("season") or {}
            home_sp = {
                "name": hp_raw.get("name"),
                "team_abbr": g.get("home"),
                "stats": {
                    "avg_k": (season.get("k9", 0) / 9.0) * (season.get("ip", 0) / max(1, season.get("starts", 1))),
                    "avg_er": (season.get("era", 4.0) / 9.0) * (season.get("ip", 0) / max(1, season.get("starts", 1))),
                    "era": season.get("era"),
                    "k_per_9": season.get("k9"),
                },
                "props": {},
            }
        if not away_sp and isinstance(ap_raw, dict) and ap_raw.get("season"):
            season = ap_raw.get("season") or {}
            away_sp = {
                "name": ap_raw.get("name"),
                "team_abbr": g.get("away"),
                "stats": {
                    "avg_k": (season.get("k9", 0) / 9.0) * (season.get("ip", 0) / max(1, season.get("starts", 1))),
                    "avg_er": (season.get("era", 4.0) / 9.0) * (season.get("ip", 0) / max(1, season.get("starts", 1))),
                    "era": season.get("era"),
                    "k_per_9": season.get("k9"),
                },
                "props": {},
            }

        # Now skip if STILL no data after fallback
        if not (home_sp or away_sp):
            continue

        record = {
            "matchup": g.get("matchup") or f"{g.get('away_team')} @ {g.get('home_team')}",
            "home_team": g.get("home_team"),
            "away_team": g.get("away_team"),
            "home_pitcher": home_sp.get("name") if home_sp else home_sp_name,
            "away_pitcher": away_sp.get("name") if away_sp else away_sp_name,
            "home_pitcher_era": (home_sp or {}).get("stats", {}).get("era"),
            "away_pitcher_era": (away_sp or {}).get("stats", {}).get("era"),
            "home_pitcher_k_per_9": (home_sp or {}).get("stats", {}).get("k_per_9"),
            "away_pitcher_k_per_9": (away_sp or {}).get("stats", {}).get("k_per_9"),
            "home_pitcher_avg_k": (home_sp or {}).get("stats", {}).get("avg_k"),
            "away_pitcher_avg_k": (away_sp or {}).get("stats", {}).get("avg_k"),
        }

        # Compute K edge: derive sweet-spot line from avg_k (without rich pre-computed props)
        import math
        def _poisson_p_over(lam, line):
            if lam <= 0: return 0
            thr = int(math.floor(line)) + 1
            s = 0
            for k in range(thr): s += (lam ** k) * math.exp(-lam) / math.factorial(k)
            return max(0.0, min(1.0, 1 - s))
        def _american(p):
            if p <= 0.001 or p >= 0.999: return 0
            if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
            return int(round(((1 / p) - 1) * 100))

        candidates = []
        for sp, side in ((home_sp, "HOME"), (away_sp, "AWAY")):
            if not sp: continue
            avg_k = sp.get("stats", {}).get("avg_k", 0) or 0
            for line_val in (4.5, 5.5, 6.5, 7.5):
                p = _poisson_p_over(avg_k, line_val)
                if 0.58 <= p <= 0.78:
                    candidates.append({
                        "pitcher": sp["name"],
                        "side": side,
                        "team": sp.get("team_abbr"),
                        "line": line_val,
                        "p_over": round(p, 4),
                        "fair_over": _american(p),
                        "fair_under": _american(1 - p),
                        "k_per_9": sp.get("stats", {}).get("k_per_9"),
                        "era": sp.get("stats", {}).get("era"),
                    })

        record["k_prop_candidates"] = sorted(candidates, key=lambda c: -c["p_over"])
        record["best_k_play"] = record["k_prop_candidates"][0] if record["k_prop_candidates"] else None

        # ER under candidate: pitcher with ERA < 3.50
        er_cands = []
        for sp, side in ((home_sp, "HOME"), (away_sp, "AWAY")):
            if not sp: continue
            era = sp.get("stats", {}).get("era", 99) or 99
            if era < 3.50:
                avg_er = sp.get("stats", {}).get("avg_er", era / 1.5) or 1.5
                p = 1 - _poisson_p_over(avg_er, 2.5)
                if p >= 0.55:
                    er_cands.append({
                        "pitcher": sp["name"], "side": side,
                        "team": sp.get("team_abbr"),
                        "era": era,
                        "p_under_2_5_er": round(p, 4),
                        "fair_under": _american(p),
                    })
        record["er_under_2_5_candidates"] = sorted(er_cands, key=lambda c: -c["p_under_2_5_er"])

        matchup_data.append(record)

    # Aggregate stats
    has_k_play = sum(1 for m in matchup_data if m.get("best_k_play"))
    has_er_play = sum(1 for m in matchup_data if m.get("er_under_2_5_candidates"))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games_with_pitcher_data": len(matchup_data),
        "n_with_k_play": has_k_play,
        "n_with_er_play": has_er_play,
        "matchups": matchup_data,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB pitcher matchup: {p['n_games_with_pitcher_data']} games analyzed")
    print(f"  Games with K prop play: {p['n_with_k_play']}")
    print(f"  Games with ER under play: {p['n_with_er_play']}")
    for m in p["matchups"][:5]:
        best = m.get("best_k_play") or {}
        if best:
            print(f"  {m['matchup']:35} | {best['pitcher']} OVER {best['line']} K ({best['p_over']*100:.0f}%) fair {best.get('fair_over','?')}")
