"""
EdgeStat -- MLB pitcher rest-day advantage model.

Days rest matters for starting pitcher performance. The standard MLB rotation
is 5 days, so a pitcher starting on 4 days rest is on SHORT rest (small fatigue
hit). 5 days = standard, 6 days = bonus rest (fresh, slight K-rate boost),
7+ days = "too much rest" (rust factor, modest fade in command).

Method:
  Each pitcher today is matched to gamelog to get days_rest before this start.
  Apply multiplier to expected_K, expected_IP, expected_ER:
    3 days rest: K -3%%, IP -5%%
    4 days rest: K -1%%, IP -2%%
    5 days rest: baseline
    6 days rest: K +2%%, IP +1%%
    7-9 days rest: K +1%%, IP 0%%
    10+ days rest: K -2%% (rust), IP -3%%

  Surface biggest rest_advantage (or disadvantage) edges -- pitchers who get
  significantly more or less rest than the opposing starter.

Output: data/mlb_pitcher_rest_advantage.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_pitcher_rest_advantage.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _rest_multipliers(days_rest: Optional[int]) -> Dict[str, float]:
    """Return K_mult, IP_mult based on days rest."""
    if days_rest is None: return {"k_mult": 1.0, "ip_mult": 1.0, "grade": "UNKNOWN"}
    if days_rest <= 2:  return {"k_mult": 0.93, "ip_mult": 0.92, "grade": "F"}   # 0-2: very short
    if days_rest == 3:  return {"k_mult": 0.97, "ip_mult": 0.95, "grade": "D"}   # 3: short
    if days_rest == 4:  return {"k_mult": 0.99, "ip_mult": 0.98, "grade": "C"}   # 4: slight short
    if days_rest == 5:  return {"k_mult": 1.00, "ip_mult": 1.00, "grade": "B"}   # 5: standard
    if days_rest == 6:  return {"k_mult": 1.02, "ip_mult": 1.01, "grade": "A"}   # 6: sweet spot
    if days_rest <= 9:  return {"k_mult": 1.01, "ip_mult": 1.00, "grade": "B"}   # 7-9: extra
    return {"k_mult": 0.98, "ip_mult": 0.97, "grade": "C"}                       # 10+: rust


def _grade_to_value(grade: str) -> int:
    return {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1, "UNKNOWN": 0}.get(grade, 0)


def run() -> Dict[str, Any]:
    matchups = _load(os.path.join(DATA_DIR, "matchups.json"))
    pitcher_logs = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))
    today = _load(os.path.join(DATA_DIR, "today.json"))

    # Build pitcher last-start map from gamelogs (most recent date per pitcher)
    pitcher_last_start = {}
    for p in (pitcher_logs.get("pitchers") or []):
        nm = (p.get("name") or "").lower()
        if not nm: continue
        gamelog = p.get("gamelog") or []
        if not gamelog: continue
        # Find most recent date
        dates = []
        for entry in gamelog:
            d = entry.get("date") or entry.get("gameDate")
            if d:
                try:
                    dates.append(dt.date.fromisoformat(d[:10]))
                except Exception:
                    pass
        if dates:
            pitcher_last_start[nm] = max(dates)

    games = matchups.get("games") or today.get("games") or []
    today_date = dt.date.today()

    rows: List[Dict[str, Any]] = []

    for g in games:
        matchup_str = g.get("matchup") or ""
        home_starter = (g.get("home") or {}).get("starter") or g.get("home_pitcher") or ""
        away_starter = (g.get("away") or {}).get("starter") or g.get("away_pitcher") or ""
        if isinstance(home_starter, dict): home_starter = home_starter.get("name") or ""
        if isinstance(away_starter, dict): away_starter = away_starter.get("name") or ""
        if not home_starter and not away_starter: continue

        details = {}
        for side, name in (("home", home_starter), ("away", away_starter)):
            if not name: continue
            last = pitcher_last_start.get(name.lower())
            days_rest = (today_date - last).days if last else None
            mults = _rest_multipliers(days_rest)
            details[side] = {
                "pitcher": name,
                "days_rest": days_rest,
                "k_mult": mults["k_mult"],
                "ip_mult": mults["ip_mult"],
                "grade": mults["grade"],
            }

        # Surface STRONG when rest grade is A or F (top/bottom of distribution)
        # plus delta vs opposing starter
        edge_flag = "NONE"
        edge_note = ""
        if "home" in details and "away" in details:
            hg = _grade_to_value(details["home"]["grade"])
            ag = _grade_to_value(details["away"]["grade"])
            if abs(hg - ag) >= 3:
                edge_flag = "STRONG_REST_DELTA"
                better_side = "home" if hg > ag else "away"
                edge_note = (
                    f"{details[better_side]['pitcher']} has significant rest advantage "
                    f"(grade {details[better_side]['grade']} vs "
                    f"{details['away' if better_side=='home' else 'home']['grade']})"
                )
            elif "A" in (details["home"]["grade"], details["away"]["grade"]):
                edge_flag = "FRESH_STARTER"
                fresh_side = "home" if details["home"]["grade"] == "A" else "away"
                edge_note = (
                    f"{details[fresh_side]['pitcher']} on optimal 6 days rest "
                    f"(K +2%, IP +1%)"
                )
            elif "F" in (details["home"]["grade"], details["away"]["grade"]):
                edge_flag = "TIRED_STARTER"
                tired_side = "home" if details["home"]["grade"] == "F" else "away"
                edge_note = (
                    f"{details[tired_side]['pitcher']} on short rest "
                    f"(K -7%, IP -8%) - fade their props"
                )

        rows.append({
            "matchup": matchup_str,
            "home": details.get("home"),
            "away": details.get("away"),
            "edge_flag": edge_flag,
            "edge_note": edge_note,
        })

    strong = [r for r in rows if r["edge_flag"] != "NONE"]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_games": len(rows),
        "n_with_edge": len(strong),
        "method_note": "Days-rest multipliers: 5d standard, 6d sweet-spot (+2% K), "
                       "3d short (-3% K), 10d+ rust (-2% K). STRONG = >=3-grade delta "
                       "between starters or A/F grade.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[pitcher-rest] {o['n_games']} games, {o['n_with_edge']} rest edges -> {OUT}")
