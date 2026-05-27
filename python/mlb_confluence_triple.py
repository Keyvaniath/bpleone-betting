"""
EdgeStat -- MLB triple confluence alerts.

The highest-leverage MLB signal possible: when 3 INDEPENDENT synthesizers
all align on the SAME matchup:
  - mlb_matchup_confluence_alerts (fade pitcher + opposing explosion)
  - mlb_stack_builder (recommended team stack)
  - mlb_offensive_explosion_alerts (lineup explosion)

When all three fire on the same game, the multi-leg parlay carries
extreme conviction. TRIPLE_LOCK = all three aligned + ELITE tier from
matchup_confluence; TRIPLE_STRONG = all three aligned at STRONG; PAIR =
only 2 of 3.

Output: data/mlb_confluence_triple.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_confluence_triple.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    matchup_conf = _load(os.path.join(DATA_DIR, "mlb_matchup_confluence_alerts.json"))
    stack = _load(os.path.join(DATA_DIR, "mlb_stack_builder.json"))
    explosion = _load(os.path.join(DATA_DIR, "mlb_offensive_explosion_alerts.json"))

    # Build matchup-keyed indexes
    matchup_conf_by_m: Dict[str, Dict[str, Any]] = {}
    for c in (matchup_conf.get("confluences") or []):
        if not isinstance(c, dict): continue
        m = _norm(c.get("matchup", ""))
        if m:
            matchup_conf_by_m[m] = c

    stack_by_m: Dict[str, Dict[str, Any]] = {}
    for s in (stack.get("stacks") or stack.get("rows") or []):
        if not isinstance(s, dict): continue
        m = _norm(s.get("matchup", ""))
        if m and m not in stack_by_m:
            stack_by_m[m] = s

    explosion_by_m: Dict[str, List[Dict[str, Any]]] = {}
    for e in (explosion.get("alerts") or []):
        if not isinstance(e, dict): continue
        m = _norm(e.get("matchup", ""))
        if m:
            explosion_by_m.setdefault(m, []).append(e)

    # All distinct matchups across all 3
    all_matchups = set(matchup_conf_by_m) | set(stack_by_m) | set(explosion_by_m)

    triples: List[Dict[str, Any]] = []
    for m in all_matchups:
        c = matchup_conf_by_m.get(m)
        s = stack_by_m.get(m)
        es = explosion_by_m.get(m, [])

        present = []
        if c: present.append("MATCHUP_CONFLUENCE")
        if s: present.append("STACK")
        if es: present.append("EXPLOSION")

        n_present = len(present)
        if n_present < 2: continue

        # Best tier across sources
        conf_tier = (c.get("tier") if c else "") or ""
        stack_score = float(s.get("score") or s.get("composite_score") or 0) if s else 0
        explosion_tier = ""
        if es:
            # Highest signal count in any explosion alert
            best = max(es, key=lambda x: x.get("n_positive_signals", 0))
            explosion_tier = best.get("tier", "")

        # Classify
        if (n_present == 3
                and "ELITE" in conf_tier
                and "ELITE" in explosion_tier):
            tier = "TRIPLE_LOCK"
        elif n_present == 3:
            tier = "TRIPLE_STRONG"
        elif n_present == 2:
            tier = "PAIR_SIGNAL"
        else:
            continue

        # Find the explosion team(s) on this matchup
        explosion_teams = [e.get("team") for e in es if e.get("team")]

        triples.append({
            "matchup": (c.get("matchup") if c else (s.get("matchup") if s else (es[0].get("matchup") if es else ""))),
            "sources_aligned": present,
            "n_sources": n_present,
            "matchup_confluence_tier": conf_tier or None,
            "explosion_tier": explosion_tier or None,
            "explosion_teams": explosion_teams,
            "stack_score": stack_score if s else None,
            "fade_pitcher": (c.get("fade_pitcher") if c else None),
            "tier": tier,
        })

    triples.sort(key=lambda t: (-t["n_sources"], -(t.get("stack_score") or 0)))

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_triples": len(triples),
        "n_triple_lock": sum(1 for t in triples if t["tier"] == "TRIPLE_LOCK"),
        "n_triple_strong": sum(1 for t in triples if t["tier"] == "TRIPLE_STRONG"),
        "n_pairs": sum(1 for t in triples if t["tier"] == "PAIR_SIGNAL"),
        "method_note": "Highest-leverage MLB signal: 3 independent synthesizers "
                       "(matchup_confluence + stack_builder + offensive_explosion) "
                       "aligning on same matchup. TRIPLE_LOCK = all 3 at ELITE tier; "
                       "TRIPLE_STRONG = all 3 at any tier; PAIR_SIGNAL = 2 of 3.",
        "triples": triples,
        "triple_locks": [t for t in triples if t["tier"] == "TRIPLE_LOCK"],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[mlb-confluence-triple] {o['n_triples']} alerts "
          f"({o['n_triple_lock']} LOCK, {o['n_triple_strong']} STRONG, "
          f"{o['n_pairs']} PAIR) -> {OUT}")
