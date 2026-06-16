"""
EdgeStat -- 2026 World Cup group-advancement Monte Carlo (the deep tournament desk).

The match model (worldcup_model.py) prices ONE game. This sims the REST of the
group stage forward, thousands of times, to answer the questions a desk actually
cares about during the group phase:

  * P(win the group)      -- seeding into the easier knockout half
  * P(finish top 2)       -- the clean advance path
  * P(advance)            -- top 2 OR one of the 8 best third-placed teams
  * most-likely final placing

2026 format: 48 teams, 12 groups of 4. Round of 32 = the 24 group winners/
runners-up PLUS the 8 best third-placed teams across all groups. That last bit
means the groups are NOT independent -- a third-place team's fate depends on how
the OTHER 11 groups' third-place teams do -- so we simulate every remaining group
fixture JOINTLY in one pass and rank the third-placed teams globally each iter.

Engine reuse: the same 3-way strength (worldcup_model.team_elo: seed band blended
with in-tournament record elo) drives per-side expected goals, sampled as two
independent Poissons -> a scoreline -> points + goal difference. Neutral-venue
(no HFA) since "home/away" in a group game is just the fixture orientation.

Deterministic (fixed seed) so the JSON only churns when the standings actually
move -- not on every heartbeat from RNG noise.

Output: data/worldcup_advancement.json
"""
from __future__ import annotations

import os
import json
import math
import random
import datetime as dt
from typing import Any, Dict, List, Tuple

import worldcup_model as wm

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CARDS = os.path.join(DATA_DIR, "worldcup_cards.json")
OUT = os.path.join(DATA_DIR, "worldcup_advancement.json")

N_SIMS = 20000
SEED = 1234            # fixed -> stable output between runs (churn only on real moves)
N_BEST_THIRDS = 8      # 2026 R32 takes the 8 best third-placed teams
GROUP_SIZE = 4


def _load(p) -> Dict[str, Any]:
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _groups() -> List[Dict[str, Any]]:
    """Authoritative group tables. Live ESPN standings first; fall back to the
    groups block already baked into worldcup_cards.json so this runs offline/local."""
    g = wm._groups()
    if g:
        return g
    return (_load(CARDS).get("groups") or [])


def _lambdas(home: str, away: str, st: Dict[str, Dict[str, Any]]) -> Tuple[float, float]:
    """Per-side expected goals from the elo gap -- NEUTRAL venue (no HFA), since a
    group fixture's home/away tag is arbitrary. Mirrors worldcup_model.price_match."""
    he, _, _ = wm.team_elo(home, st)
    ae, _, _ = wm.team_elo(away, st)
    g = (he - ae) / 400.0
    lam_h = max(0.30, min(3.4, wm.HALF_GOALS * math.exp(wm.GOAL_K * g)))
    lam_a = max(0.30, min(3.4, wm.HALF_GOALS * math.exp(-wm.GOAL_K * g)))
    return lam_h, lam_a


def _pois_sample(rng: random.Random, lam: float) -> int:
    """Knuth's Poisson sampler -- the same scoring process the card grid integrates."""
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def _remaining_fixtures(groups: List[Dict[str, Any]],
                        played: set) -> List[Tuple[str, str, str]]:
    """Every group-stage pairing not yet played. A 4-team group is a single
    round-robin (6 matches), so 'all C(n,2) pairs minus the played ones' IS the
    remaining schedule -- no fixture list needed."""
    fixtures: List[Tuple[str, str, str]] = []
    for g in groups:
        teams = [r["team"] for r in (g.get("teams") or []) if r.get("team")]
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                a, b = teams[i], teams[j]
                if (a, b) in played:
                    continue
                fixtures.append((g["name"], a, b))
    return fixtures


def simulate(groups: List[Dict[str, Any]], st: Dict[str, Dict[str, Any]],
             results: List[Dict[str, Any]], n: int = N_SIMS) -> Dict[str, Any]:
    played = {(m.get("home"), m.get("away")) for m in results}
    played |= {(m.get("away"), m.get("home")) for m in results}
    fixtures = _remaining_fixtures(groups, played)

    rng = random.Random(SEED)
    teams_by_group: Dict[str, List[str]] = {
        g["name"]: [r["team"] for r in (g.get("teams") or []) if r.get("team")] for g in groups
    }
    base: Dict[str, Dict[str, Any]] = {}
    for g in groups:
        for r in (g.get("teams") or []):
            t = r.get("team")
            if t:
                base[t] = {"pts": int(r.get("pts") or 0), "gf": int(r.get("gf") or 0),
                           "ga": int(r.get("ga") or 0), "gp": int(r.get("gp") or 0),
                           "group": g["name"], "advanced": bool(r.get("advanced"))}

    # Precompute each remaining fixture's expected goals ONCE (strength is fixed
    # for the iteration set -- we don't re-blend elo mid-sim).
    fx = [(grp, h, a, *_lambdas(h, a, st)) for grp, h, a in fixtures]

    finish = {t: [0, 0, 0, 0] for t in base}   # counts of finishing 1st/2nd/3rd/4th
    advance = {t: 0 for t in base}
    win_group = {t: 0 for t in base}

    for _ in range(n):
        pts = {t: base[t]["pts"] for t in base}
        gd = {t: base[t]["gf"] - base[t]["ga"] for t in base}
        gf = {t: base[t]["gf"] for t in base}
        for grp, h, a, lh, la in fx:
            hs, as_ = _pois_sample(rng, lh), _pois_sample(rng, la)
            gd[h] += hs - as_; gd[a] += as_ - hs
            gf[h] += hs; gf[a] += as_
            if hs > as_:
                pts[h] += 3
            elif hs < as_:
                pts[a] += 3
            else:
                pts[h] += 1; pts[a] += 1

        thirds: List[Tuple[str, int, int, int]] = []
        for grp, teams in teams_by_group.items():
            # FIFA order: points, then goal difference, then goals for; random
            # draw of lots as the last resort (the rng tiebreak).
            order = sorted(teams, key=lambda t: (pts[t], gd[t], gf[t], rng.random()), reverse=True)
            for pos, t in enumerate(order[:4]):
                finish[t][pos] += 1
            if order:
                win_group[order[0]] += 1
                advance[order[0]] += 1
            if len(order) > 1:
                advance[order[1]] += 1
            if len(order) > 2:
                t3 = order[2]
                thirds.append((t3, pts[t3], gd[t3], gf[t3]))

        # 8 best third-placed teams advance -- ranked across ALL groups jointly.
        thirds.sort(key=lambda x: (x[1], x[2], x[3], rng.random()), reverse=True)
        for t, *_ in thirds[:N_BEST_THIRDS]:
            advance[t] += 1

    out_groups: List[Dict[str, Any]] = []
    for g in groups:
        rows = []
        for r in (g.get("teams") or []):
            t = r.get("team")
            if not t or t not in base:
                continue
            f = finish[t]
            p_adv = advance[t] / n
            rows.append({
                "team": t, "pts": base[t]["pts"], "gp": base[t]["gp"],
                "gd": base[t]["gf"] - base[t]["ga"], "gf": base[t]["gf"],
                "p_win_group": round(win_group[t] / n, 4),
                "p_top2": round((f[0] + f[1]) / n, 4),
                "p_advance": round(p_adv, 4),
                "p_first": round(f[0] / n, 4), "p_second": round(f[1] / n, 4),
                "p_third": round(f[2] / n, 4),
                "clinched": bool(base[t]["advanced"]) or p_adv >= 0.9995,
                "eliminated": p_adv <= 0.0005,
            })
        rows.sort(key=lambda x: (-x["p_advance"], -x["p_win_group"], -x["pts"]))
        out_groups.append({"name": g["name"], "teams": rows})

    return {"groups": out_groups, "n_fixtures_remaining": len(fixtures),
            "n_teams": len(base)}


def run() -> Dict[str, Any]:
    results = wm._wc_results()
    st = wm._standings(results)
    groups = _groups()

    if not groups:
        out = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_sims": 0, "available": False,
            "note": "No group tables yet (ESPN standings empty + no cards fallback). "
                    "Fills in once the group stage is underway.",
            "groups": [],
        }
    else:
        sim = simulate(groups, st, results, N_SIMS)
        out = {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_sims": N_SIMS, "available": True,
            "n_fixtures_remaining": sim["n_fixtures_remaining"],
            "n_teams": sim["n_teams"],
            "format_note": (
                f"{N_SIMS:,} Monte Carlo sims of every remaining group fixture. Each match "
                "is scored as two independent Poissons off the model's elo-gap expected goals "
                "(neutral venue); standings roll forward with FIFA tiebreakers (points, goal "
                "difference, goals for, then drawing of lots). Advance = finish top 2 OR rank "
                f"among the {N_BEST_THIRDS} best third-placed teams across all 12 groups -- "
                "the third-place race is simulated JOINTLY since the groups aren't independent."),
            "groups": sim["groups"],
        }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    if not o.get("available"):
        print(f"[wc-advance] not available: {o.get('note')}")
    else:
        print(f"[wc-advance] {o['n_sims']:,} sims, {o['n_fixtures_remaining']} fixtures remaining, "
              f"{o['n_teams']} teams -> {OUT}")
        for g in o["groups"][:4]:
            print(f"  {g['name']}:")
            for t in g["teams"]:
                print(f"    {t['team']:18s} {t['pts']}pts gp{t['gp']}  "
                      f"win-grp {t['p_win_group']:.0%}  advance {t['p_advance']:.0%}"
                      f"{'  CLINCHED' if t['clinched'] else ''}{'  OUT' if t['eliminated'] else ''}")
