"""
EdgeStat -- UFC method-of-victory projector.

For each upcoming UFC fight, projects:
  - P(fight ends in finish)  -- KO/TKO or Submission, not Decision
  - P(KO/TKO win for each fighter)
  - P(Submission for each fighter)
  - P(Decision)
  - 'Fight goes the distance' Yes/No market

Approach: weight-class average finish rates (from UFC stats compiled
historically) + adjustment from each fighter's career record (more wins
than fights implies higher finish-rate proxy).

Output: data/ufc_method_of_victory.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "ufc_method_of_victory.json")


# Weight-class average finish rates (empirical from UFC stats 2018-2024)
# (finish_rate, ko_share, sub_share)  -- ko + sub = 1.0 (within finishes)
WEIGHT_CLASS_FINISH = {
    "Heavyweight":         (0.70, 0.85, 0.15),
    "Light Heavyweight":   (0.62, 0.78, 0.22),
    "Middleweight":        (0.55, 0.65, 0.35),
    "Welterweight":        (0.48, 0.60, 0.40),
    "Lightweight":         (0.45, 0.55, 0.45),
    "Featherweight":       (0.42, 0.55, 0.45),
    "Bantamweight":        (0.38, 0.50, 0.50),
    "Flyweight":           (0.32, 0.45, 0.55),

    # Women's classes
    "Women's Bantamweight": (0.40, 0.55, 0.45),
    "Women's Featherweight": (0.45, 0.60, 0.40),
    "Women's Flyweight":   (0.30, 0.45, 0.55),
    "Women's Strawweight": (0.28, 0.40, 0.60),
}
DEFAULT_FINISH = (0.45, 0.55, 0.45)


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p):
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _parse_rec(r):
    if not r or not isinstance(r, str): return None
    parts = r.split("-")
    try:
        w = int(parts[0]); l = int(parts[1])
        d = int(parts[2]) if len(parts) > 2 else 0
        return {"w": w, "l": l, "d": d, "total": w + l + d,
                "win_pct": w / max(1, w + l + d)}
    except Exception:
        return None


def _classify_weight_class(s: Optional[str]) -> str:
    """ESPN sometimes returns weight class as a timestamp string. Try heuristic."""
    if not s or not isinstance(s, str): return "Unknown"
    sl = s.lower()
    if "heavy" in sl and "light" not in sl: return "Heavyweight"
    if "light heavy" in sl: return "Light Heavyweight"
    if "middle" in sl: return "Middleweight"
    if "welter" in sl: return "Welterweight"
    if "lightweight" in sl: return "Lightweight"
    if "feather" in sl: return "Featherweight"
    if "bantam" in sl and "women" in sl: return "Women's Bantamweight"
    if "bantam" in sl: return "Bantamweight"
    if "fly" in sl and "women" in sl: return "Women's Flyweight"
    if "fly" in sl: return "Flyweight"
    if "straw" in sl: return "Women's Strawweight"
    return "Unknown"


def _project_fight(fa: str, fb: str, ra: str, rb: str, weight_class: str,
                    p_a_wins: float) -> Dict[str, Any]:
    """Project method-of-victory probabilities for the fight."""
    finish_rate, ko_share, sub_share = WEIGHT_CLASS_FINISH.get(weight_class, DEFAULT_FINISH)

    # Per-fighter finish rate adjustment: higher win-pct → higher finish skew
    # (proxy: finishers tend to win more than 60%)
    ra_d = _parse_rec(ra) or {"win_pct": 0.5}
    rb_d = _parse_rec(rb) or {"win_pct": 0.5}

    # Adjust class finish rate by avg fighter finish-proxy
    avg_winpct = (ra_d["win_pct"] + rb_d["win_pct"]) / 2
    finish_adj = finish_rate + 0.10 * (avg_winpct - 0.5)
    finish_adj = max(0.20, min(0.85, finish_adj))

    p_finish = finish_adj
    p_decision = 1 - p_finish

    # Distribute finishes to A vs B based on win prob
    p_a_finish = p_finish * p_a_wins
    p_b_finish = p_finish * (1 - p_a_wins)

    # Split each finisher's chance into KO vs Sub
    return {
        "weight_class": weight_class,
        "p_finish": round(p_finish, 4),
        "p_decision": round(p_decision, 4),
        "p_a_ko_tko": round(p_a_finish * ko_share, 4),
        "p_a_sub": round(p_a_finish * sub_share, 4),
        "p_b_ko_tko": round(p_b_finish * ko_share, 4),
        "p_b_sub": round(p_b_finish * sub_share, 4),
        "fair_distance_yes": _american(p_decision),
        "fair_distance_no": _american(p_finish),
        "ko_share_in_class": ko_share,
        "sub_share_in_class": sub_share,
    }


def run() -> Dict[str, Any]:
    matchup = _load(os.path.join(DATA_DIR, "ufc_matchup.json"))
    fights_in = matchup.get("fights") or []
    if not fights_in:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "n_fights": 0, "fights": []}
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    fights_out: List[Dict[str, Any]] = []
    for f in fights_in:
        weight = _classify_weight_class(f.get("weight_class"))
        p_a = f.get("p_fighter_a_wins") or 0.5
        proj = _project_fight(
            f.get("fighter_a", "A"), f.get("fighter_b", "B"),
            f.get("record_a"), f.get("record_b"),
            weight, p_a
        )
        fights_out.append({
            "event": f.get("event"),
            "fighter_a": f.get("fighter_a"),
            "fighter_b": f.get("fighter_b"),
            "record_a": f.get("record_a"),
            "record_b": f.get("record_b"),
            "p_fighter_a_wins": f.get("p_fighter_a_wins"),
            "p_fighter_b_wins": f.get("p_fighter_b_wins"),
            **proj,
        })

    # Top "fight doesn't go the distance" plays
    no_dist = sorted(
        [f for f in fights_out],
        key=lambda f: -f["p_finish"]
    )

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_fights": len(fights_out),
        "next_event": fights_in[0].get("event") if fights_in else None,
        "fights": fights_out,
        "top_no_distance_picks": no_dist[:10],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


def _american_str(p):
    a = _american(p)
    return f"{a:+d}" if isinstance(a, int) else "--"


if __name__ == "__main__":
    p = run()
    print(f"UFC method-of-victory: {p['n_fights']} fights ({p.get('next_event','?')})")
    print("Top 5 'fight ends inside the distance' picks:")
    for f in p.get("top_no_distance_picks", [])[:5]:
        print(f"  {f['fighter_a']:25s} vs {f['fighter_b']:25s} | "
              f"weight: {f['weight_class']:15s} | "
              f"P(finish)={f['p_finish']*100:.0f}% (fair {f['fair_distance_no']:+d}) | "
              f"P(distance)={f['p_decision']*100:.0f}% (fair {f['fair_distance_yes']:+d})")
    print("\nTop 5 KO/TKO picks for favorite:")
    by_ko = sorted(p["fights"], key=lambda f: -max(f["p_a_ko_tko"], f["p_b_ko_tko"]))
    for f in by_ko[:5]:
        fav = f['fighter_a'] if f['p_a_ko_tko'] >= f['p_b_ko_tko'] else f['fighter_b']
        p_ko = max(f['p_a_ko_tko'], f['p_b_ko_tko'])
        print(f"  {fav:25s} KO/TKO @ {p_ko*100:.0f}% (fair {_american_str(p_ko)})")
