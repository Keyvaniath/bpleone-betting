"""
EdgeStat -- MLB team confluence score.

Composite per-team score combining team-level synthesizers:
  - mlb_team_total_edge (team total direction)
  - mlb_offensive_explosion_alerts (n_positive_signals)
  - mlb_matchup_confluence_alerts (fade+explosion confluence)
  - mlb_lineup_quality_index (lineup tier/score)
  - mlb_team_5plus_runs (p_5plus)
  - mlb_race_to_3_runs (run-prob lean)

Score formula:
  score = explosion_signals * 2.5 + tt_over_strength + lineup_score / 10
        + p_5plus * 25 + race_lean + confluence_pair_bonus(3 if in pair)

TEAM_LOCK = score >= 18 with explosion_signals >= 4 OR matchup_confluence
TEAM_STRONG = 12-17
TEAM_FADE = score <= 2

Output: data/mlb_team_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_team_confluence_score.json")


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


def _key(matchup: str, side: str) -> str:
    return f"{matchup or ''}|{(side or '').upper()}"


def run() -> Dict[str, Any]:
    tt = _load(os.path.join(DATA_DIR, "mlb_team_total_edge.json"))
    expl = _load(os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json"))
    matchup_conf = _load(os.path.join(DATA_DIR, "mlb_matchup_confluence_alerts.json"))
    lq = _load(os.path.join(DATA_DIR, "mlb_lineup_quality_index.json"))
    five_plus = _load(os.path.join(DATA_DIR, "mlb_team_5plus_runs.json"))
    race = _load(os.path.join(DATA_DIR, "mlb_race_to_3_runs.json"))

    # Index by (matchup, side)
    tt_idx: Dict[str, Dict[str, Any]] = {}
    for r in (tt.get("rows") or []):
        if not isinstance(r, dict): continue
        tt_idx[_key(r.get("matchup"), r.get("side"))] = r

    expl_idx: Dict[str, Dict[str, Any]] = {}
    for a in (expl.get("alerts") or []):
        if not isinstance(a, dict): continue
        expl_idx[_key(a.get("matchup"), a.get("side"))] = a

    # Matchup confluence (by matchup only -- pairs are at matchup level)
    matchup_conf_by_m: Dict[str, Dict[str, Any]] = {}
    for c in (matchup_conf.get("confluences") or []):
        if not isinstance(c, dict): continue
        m = c.get("matchup", "")
        if m: matchup_conf_by_m[m] = c

    # Lineup quality by (matchup, side)
    lq_idx: Dict[str, Dict[str, Any]] = {}
    for g in (lq.get("games") or []):
        for side in ("home", "away"):
            sd = g.get(side) or {}
            lq_idx[_key(g.get("matchup"), side)] = sd

    five_idx: Dict[str, Dict[str, Any]] = {}
    for r in (five_plus.get("rows") or []):
        if not isinstance(r, dict): continue
        five_idx[_key(r.get("matchup"), r.get("side"))] = r

    race_idx: Dict[str, Dict[str, Any]] = {}
    for r in (race.get("rows") or []):
        if not isinstance(r, dict): continue
        race_idx[_key(r.get("matchup"), r.get("side"))] = r

    all_keys = (set(tt_idx) | set(expl_idx) | set(lq_idx)
                | set(five_idx) | set(race_idx))

    rows: List[Dict[str, Any]] = []
    for k in all_keys:
        matchup, side = (k.split("|", 1) + [""])[:2]
        ttr = tt_idx.get(k, {})
        exr = expl_idx.get(k, {})
        lqr = lq_idx.get(k, {})
        fpr = five_idx.get(k, {})
        rcr = race_idx.get(k, {})

        explosion_signals = int(exr.get("n_positive_signals", 0) or 0)
        tt_dir = (ttr.get("direction") or "").upper()
        tt_over_strength = 0
        if tt_dir == "STRONG_OVER": tt_over_strength = 4
        elif tt_dir == "LEAN_OVER": tt_over_strength = 2
        elif tt_dir == "LEAN_UNDER": tt_over_strength = -2
        elif tt_dir == "STRONG_UNDER": tt_over_strength = -4

        lineup_score = _safe(lqr.get("score"))
        p_5plus = _safe(fpr.get("p_5plus"))
        race_p = _safe(rcr.get("p"))
        race_lean = race_p * 5  # 0-5 points based on race-to-3 prob

        # Matchup confluence bonus
        matchup_conf_bonus = 0
        if matchup in matchup_conf_by_m:
            conf = matchup_conf_by_m[matchup]
            # Side matches explosion team in confluence?
            if (conf.get("explosion_team") or "") == (ttr.get("team") or exr.get("team") or ""):
                matchup_conf_bonus = 3 if conf.get("tier") in ("CONFLUENCE_ELITE",) else 2

        has_data = (explosion_signals > 0 or abs(tt_over_strength) > 0
                    or lineup_score > 0 or p_5plus > 0)
        if not has_data: continue

        score = (explosion_signals * 2.5
                 + tt_over_strength
                 + lineup_score / 10.0
                 + p_5plus * 25
                 + race_lean
                 + matchup_conf_bonus)

        # Baseline score for an average team is around 7-9 (lineup score / 10 ~= 5,
        # tt_over_strength = 0, p_5plus ~= 0.25 -> 6.25). So thresholds need to be
        # well above baseline to flag genuine alignment.
        if score >= 22 and (explosion_signals >= 4 or matchup_conf_bonus > 0):
            tier = "TEAM_LOCK"
        elif score >= 16 and (tt_over_strength >= 2 or explosion_signals >= 3):
            tier = "TEAM_STRONG"
        elif score <= 4 or tt_over_strength <= -3:
            tier = "TEAM_FADE"
        else:
            tier = "TEAM_NEUTRAL"

        rows.append({
            "matchup": matchup,
            "side": side,
            "team": ttr.get("team") or exr.get("team") or lqr.get("team"),
            "explosion_signals": explosion_signals,
            "tt_direction": tt_dir or None,
            "lineup_score": lineup_score,
            "p_5plus": round(p_5plus, 3),
            "race_p": round(race_p, 3),
            "matchup_conf_bonus": matchup_conf_bonus,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_teams": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "TEAM_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "TEAM_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "TEAM_FADE"),
        "method_note": "Composite MLB team score. explosion_signals*2.5 + "
                       "tt_over_strength + lineup_score/10 + p_5plus*25 + "
                       "race_lean + matchup_conf_bonus. LOCK >= 18 with "
                       "explosion>=4 OR matchup conf; STRONG 12-17; "
                       "FADE = score <=2 or strong tt UNDER.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "TEAM_LOCK"],
        "fades": [r for r in rows if r["tier"] == "TEAM_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[team-confluence] {o['n_teams']} teams "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
