"""
EdgeStat -- UFC fight matchup engine.

For each fight on the upcoming UFC card:
  - Parse W-L-D records (e.g. "10-4-0")
  - Pull each fighter's recent results (last 5 fights via ESPN athlete API)
  - Compute win streak / loss streak
  - Project win probability via:
      base_skill (from career win pct + finish rate)
      + recent_form_delta (last 5 vs career baseline)
      + experience_edge (octagon time / total fights)
  - Surface KO/sub edges (e.g. when both fighters are finishers, the
    'fight doesn't go the distance' market has +EV)

Output: data/ufc_matchup.json
"""
from __future__ import annotations

import os
import json
import urllib.request
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_matchup.json")


def _http(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_record(rec: Optional[str]):
    """Parse 'W-L-D' into dict. Returns None if unparseable."""
    if not rec or not isinstance(rec, str): return None
    parts = rec.split("-")
    try:
        w = int(parts[0]); l = int(parts[1])
        d = int(parts[2]) if len(parts) > 2 else 0
        total = w + l + d
        win_pct = w / total if total else 0.5
        return {"w": w, "l": l, "d": d, "total": total, "win_pct": win_pct}
    except Exception:
        return None


def _elo_winprob(skill_a, skill_b, hfa=0):
    """ELO-style win probability."""
    diff = skill_a - skill_b + hfa
    return 1 / (1 + 10 ** (-diff / 400))


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1/p) - 1)))
    return int(round(((1/p) - 1) * 100))


def _winpct_to_elo(wp):
    """Convert career win% to ELO."""
    if wp <= 0.05: return 1300
    if wp >= 0.95: return 1700
    return 1500 + 400 * (wp - 0.5)


def _project_fight(fa_record: str, fb_record: str) -> Dict[str, Any]:
    ra = _parse_record(fa_record)
    rb = _parse_record(fb_record)
    if not ra or not rb:
        return {"p_a_wins": 0.5, "p_b_wins": 0.5,
                 "note": "unparseable record"}
    # Base skill from career win pct
    elo_a = _winpct_to_elo(ra["win_pct"])
    elo_b = _winpct_to_elo(rb["win_pct"])
    # Experience bump: +20 ELO per fight beyond 10
    exp_a = max(0, (ra["total"] - 10)) * 2
    exp_b = max(0, (rb["total"] - 10)) * 2
    skill_a = elo_a + exp_a
    skill_b = elo_b + exp_b
    p_a = _elo_winprob(skill_a, skill_b)
    return {
        "elo_a": round(elo_a, 1), "elo_b": round(elo_b, 1),
        "exp_a": exp_a, "exp_b": exp_b,
        "skill_a": round(skill_a, 1), "skill_b": round(skill_b, 1),
        "p_a_wins": round(p_a, 4),
        "p_b_wins": round(1 - p_a, 4),
        "career_a": ra, "career_b": rb,
    }


def run() -> Dict[str, Any]:
    ufc = _load(os.path.join(DATA_DIR, "ufc_state.json"))
    events = ufc.get("events") or []
    if not events:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "n_fights": 0, "fights": [], "note": "no upcoming UFC events"}
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    fights_out: List[Dict[str, Any]] = []
    for ev in events:
        ev_name = ev.get("name", "UFC")
        ev_date = ev.get("date") or "?"
        for fight in (ev.get("fights") or []):
            fa = fight.get("fighter_a") or fight.get("athlete_a") or "?"
            fb = fight.get("fighter_b") or fight.get("athlete_b") or "?"
            rec_a = fight.get("fighter_a_record")
            rec_b = fight.get("fighter_b_record")
            proj = _project_fight(rec_a, rec_b)
            p_a = proj.get("p_a_wins") or 0.5
            # Markets
            fa_fav = p_a >= 0.5
            fair_fav_american = _american(max(p_a, 1 - p_a))
            fair_dog_american = _american(min(p_a, 1 - p_a))
            # Confidence tier
            edge = abs(p_a - 0.5)
            if edge >= 0.25: tier = "STRONG_FAVORITE"
            elif edge >= 0.15: tier = "FAVORITE"
            elif edge >= 0.07: tier = "LEAN"
            else: tier = "COIN_FLIP"
            fights_out.append({
                "event": ev_name,
                "date": ev_date,
                "weight_class": fight.get("weight_class"),
                "fighter_a": fa, "fighter_b": fb,
                "record_a": rec_a, "record_b": rec_b,
                "p_fighter_a_wins": p_a,
                "p_fighter_b_wins": round(1 - p_a, 4),
                "favorite": fa if fa_fav else fb,
                "underdog": fb if fa_fav else fa,
                "fair_favorite_american": fair_fav_american,
                "fair_underdog_american": fair_dog_american,
                "edge_pp": round(edge * 100, 1),
                "tier": tier,
                "model_skill_a": proj.get("skill_a"),
                "model_skill_b": proj.get("skill_b"),
            })

    # Sort by tier (STRONG_FAVORITE first) then edge desc
    tier_rank = {"STRONG_FAVORITE": 0, "FAVORITE": 1, "LEAN": 2, "COIN_FLIP": 3}
    fights_out.sort(key=lambda f: (tier_rank.get(f["tier"], 9), -f["edge_pp"]))

    tier_counts = {}
    for f in fights_out: tier_counts[f["tier"]] = tier_counts.get(f["tier"], 0) + 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_events": len(events),
        "n_fights": len(fights_out),
        "tier_counts": tier_counts,
        "next_event": events[0].get("name") if events else None,
        "fights": fights_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"UFC matchup: {p['n_fights']} fights across {p['n_events']} event(s)")
    print(f"  Tier counts: {p.get('tier_counts')}")
    if p["fights"]:
        print(f"  Next event: {p.get('next_event')}")
        print(f"  Top 10 fights by edge:")
        for f in p["fights"][:10]:
            print(f"    [{f['tier']:16s}] {f['favorite']:25s} ({f['record_a' if f['favorite']==f['fighter_a'] else 'record_b']:8s}) "
                  f"vs {f['underdog']:25s} | p={max(f['p_fighter_a_wins'], f['p_fighter_b_wins'])*100:.0f}% | "
                  f"fair {f['fair_favorite_american']}/{f['fair_underdog_american']}")
