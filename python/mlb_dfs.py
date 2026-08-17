"""
EdgeStat -- MLB DFS desk: DraftKings Classic projections + exact optimal lineup.

The MLB counterpart of nfl_dfs. v1 is deliberately MEAN-BASED and says so:
hitters project from season PER-GAME rates (statsapi via the cached
props_pipeline/stats_repo helpers), probable starters from season PER-START
rates -- no park/opponent/lineup-order adjustment yet and no distributions
(the NFL desk's Monte Carlo treatment is the v2 path). Honest v1 beats a
dressed-up one.

DK MLB CLASSIC SCORING
  Hitters : 1B +3 · 2B +5 · 3B +8 · HR +10 · RBI +2 · R +2 · BB +2 · HBP +2 · SB +5
  Pitchers: IP +2.25 · K +2 · W +4 · ER -2 · H -0.6 · BB -0.6
            (CG/CGSO/no-hitter bonuses ignored -- rare, ~0.05 pts EV)
ROSTER: P, P, C, 1B, 2B, 3B, SS, OF, OF, OF -- $50,000 cap, 10 slots.

Dual-eligibility (DK lists "2B/SS" etc.) is handled EXACTLY: the optimizer may
seat a player at any eligible slot. Pitcher pool = today's PROBABLE starters
only (matchups.json), never the 380-arm bullpen soup.

DISCLOSURES (also in the payload):
  - v1 projections are season-rate means: no lineup-order, park, platoon,
    weather, or opposing-pitcher adjustment, and no floor/ceiling columns yet.
  - A hitter who sits scores 0 in reality; confirm lineups before lock.
  - Pitcher W rate is season wins/start -- crude.
  - DFS rows never enter the betting ledger.

Output: data/mlb_dfs.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import props_pipeline as pp   # resolve_player_id + _batter_season (cached statsapi)
import stats_repo as sr

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SAL_CACHE = os.path.join(DATA_DIR, "mlb_dfs_salaries.json")
OUT = os.path.join(DATA_DIR, "mlb_dfs.json")

SALARY_CAP = 50000
CAPS = (45000, 48000, 50000)
MIN_GP_HITTER = 25         # season games floor for a usable hitter rate
MIN_STARTS_SP = 4          # season starts floor for a usable SP rate
MLB_CLASSIC_TYPE = 28      # DK ContestTypeId for MLB Classic

# Roster: exact counts, no flex. P covers SP/RP draftables.
ROSTER_MAX = {"P": 2, "C": 1, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "OF": 3}
N_SLOTS = 10
POS_ORDER = ["P", "C", "1B", "2B", "3B", "SS", "OF"]
POS_I = {p: i for i, p in enumerate(POS_ORDER)}

H = {"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"}


def _get(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers=H)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write(p: str, obj: Any) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _eligible(pos_str: str) -> List[str]:
    """DK position string -> eligible roster slots. 'SP'/'RP' -> P; dual
    eligibility ('2B/SS') -> both slots."""
    out: List[str] = []
    for p in str(pos_str or "").upper().split("/"):
        p = p.strip()
        if p in ("SP", "RP"):
            p = "P"
        if p in ROSTER_MAX and p not in out:
            out.append(p)
    return out


# --------------------------------------------------------------------------
# 1. Slate (DK MLB Classic -- ContestTypeId 28; suffix None == the Main slate)
# --------------------------------------------------------------------------

def fetch_slate() -> Optional[Dict[str, Any]]:
    try:
        lobby = _get("https://www.draftkings.com/lobby/getcontests?sport=MLB")
        groups = lobby.get("DraftGroups") or []
    except Exception as e:
        print(f"[mlb-dfs] DK lobby unreachable ({e!r}) -- using cached slate if any")
        cached = _load(SAL_CACHE)
        return cached if cached.get("players") else None

    today = dt.date.today().isoformat()
    candidates = []
    for g in groups:
        if g.get("ContestTypeId") != MLB_CLASSIC_TYPE:
            continue
        start = str(g.get("StartDateEst") or "")[:10]
        if start >= today:
            candidates.append((start, str(g.get("ContestStartTimeSuffix") or ""),
                               g.get("DraftGroupId")))
    if not candidates:
        cached = _load(SAL_CACHE)
        return cached if cached.get("players") else None
    candidates.sort()
    first_day = candidates[0][0]
    # Prefer the suffix-less (Main) group; fall back to the biggest same-day one.
    same_day = [c for c in candidates if c[0] == first_day]
    best = None
    for start, suffix, dgid in sorted(same_day, key=lambda c: (c[1] != "", c[1]))[:3]:
        try:
            dd = _get(f"https://api.draftkings.com/draftgroups/v1/draftgroups/{dgid}/draftables")
        except Exception:
            continue
        seen: Dict[Any, Dict[str, Any]] = {}
        games = set()
        for p in dd.get("draftables") or []:
            pid = p.get("playerDkId")
            if pid in seen or not p.get("salary"):
                continue
            comp = (p.get("competition") or {}).get("name") or ""
            games.add(comp)
            seen[pid] = {"name": p.get("displayName"), "pos": p.get("position"),
                         "salary": p.get("salary"),
                         "team": (p.get("teamAbbreviation") or "").upper(),
                         "game": comp, "status": p.get("status") or ""}
        if seen and (best is None or len(seen) > len(best["players"])):
            best = {"draft_group_id": dgid, "start": start, "suffix": suffix,
                    "players": list(seen.values()), "games": sorted(games)}
        if best and not suffix:
            break     # the Main slate wins outright
    if best:
        best["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
        _write(SAL_CACHE, best)
        return best
    cached = _load(SAL_CACHE)
    return cached if cached.get("players") else None


# --------------------------------------------------------------------------
# 2. Mean projections (season rates; honest v1)
# --------------------------------------------------------------------------

def hitter_dk_mean(season: Dict[str, Any]) -> Optional[float]:
    gp = season.get("gamesPlayed") or 0
    if gp < MIN_GP_HITTER:
        return None
    g = lambda k: float(season.get(k) or 0)
    singles = g("hits") - g("doubles") - g("triples") - g("homeRuns")
    pts = (3.0 * singles + 5.0 * g("doubles") + 8.0 * g("triples")
           + 10.0 * g("homeRuns") + 2.0 * g("rbi") + 2.0 * g("runs")
           + 2.0 * g("baseOnBalls") + 2.0 * g("hitByPitch")
           + 5.0 * g("stolenBases"))
    return round(pts / gp, 2)


def pitcher_dk_mean(season: Dict[str, Any]) -> Optional[float]:
    starts = season.get("gamesStarted") or 0
    if starts < MIN_STARTS_SP:
        return None
    g = lambda k: float(season.get(k) or 0)
    ip = 0.0
    raw_ip = str(season.get("inningsPitched") or "0")
    try:                      # statsapi "123.2" = 123 and 2/3 innings
        whole, _, frac = raw_ip.partition(".")
        ip = int(whole) + (int(frac or 0) / 3.0)
    except Exception:
        pass
    pts = (2.25 * ip + 2.0 * g("strikeOuts") + 4.0 * g("wins")
           - 2.0 * g("earnedRuns") - 0.6 * g("hits") - 0.6 * g("baseOnBalls"))
    return round(pts / starts, 2)


def _probable_pitchers() -> Dict[str, int]:
    """norm name -> mlb id for today's probable starters (matchups.json)."""
    out: Dict[str, int] = {}
    m = _load(os.path.join(DATA_DIR, "matchups.json"))
    for g in m.get("games") or []:
        for side in ("away_pitcher", "home_pitcher"):
            p = g.get(side) or {}
            nm, pid = p.get("name"), p.get("id")
            if nm and pid:
                out[pp._norm_name(nm) if hasattr(pp, "_norm_name") else nm.lower()] = pid
    return out


def _norm(s: Any) -> str:
    import re, unicodedata
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", "", s.lower()).strip()


# --------------------------------------------------------------------------
# 3. Exact optimizer: 0/1 DP over position-counts x salary, multi-eligibility
# --------------------------------------------------------------------------

def _count_states() -> List[Tuple[int, ...]]:
    states = []
    for p_ in range(ROSTER_MAX["P"] + 1):
        for c in range(ROSTER_MAX["C"] + 1):
            for b1 in range(ROSTER_MAX["1B"] + 1):
                for b2 in range(ROSTER_MAX["2B"] + 1):
                    for b3 in range(ROSTER_MAX["3B"] + 1):
                        for ss in range(ROSTER_MAX["SS"] + 1):
                            for of in range(ROSTER_MAX["OF"] + 1):
                                if p_ + c + b1 + b2 + b3 + ss + of <= N_SLOTS:
                                    states.append((p_, c, b1, b2, b3, ss, of))
    return states


def optimize(pool: List[Dict[str, Any]], obj_key: str = "proj",
             caps: Tuple[int, ...] = CAPS) -> Dict[int, Dict[str, Any]]:
    """Exact DP. pool rows need: name, elig (list of slots), salary, obj_key.
    A dual-eligible player may be seated at ANY eligible slot -- each DP
    transition tries every eligible position."""
    # LINEUP-PAYLOAD DP (2026-08-17): each cell stores its FULL lineup (tuple of
    # (pool_index, seated_pos)), not a parent pointer. Parent-pointer walk-back
    # is unsound in a value-overwriting knapsack table -- an ancestor cell can
    # improve AFTER a descendant records its provenance, and the mixed-path
    # reconstruction seated the same OF twice on the first real slate (walk-back
    # total 111.17 vs DP value 111.15). Storing the lineup itself makes
    # consistency structural. Memory: ~states x salary x 10 ints -- fine.
    unit = 100
    max_units = max(caps) // unit
    states = _count_states()
    s_index = {s: i for i, s in enumerate(states)}
    NEG = float("-inf")
    best = [[NEG] * (max_units + 1) for _ in states]
    lus: List[List[Optional[Tuple[Tuple[int, str], ...]]]] = \
        [[None] * (max_units + 1) for _ in states]
    zero = s_index[(0,) * len(POS_ORDER)]
    best[zero][0] = 0.0
    lus[zero][0] = ()
    order = sorted(range(len(states)), key=lambda i: -sum(states[i]))

    for pi, p in enumerate(pool):
        w = int(p["salary"]) // unit
        v = float(p.get(obj_key) or 0.0)
        elig = p.get("elig") or []
        for si in order:
            st = states[si]
            row, lrow = best[si], lus[si]
            for pos in elig:
                d = POS_I[pos]
                if st[d] + 1 > ROSTER_MAX[pos]:
                    continue
                new = list(st)
                new[d] += 1
                ni = s_index.get(tuple(new))
                if ni is None:
                    continue
                nrow, nlu = best[ni], lus[ni]
                for sal in range(max_units - w, -1, -1):
                    cur = row[sal]
                    if cur == NEG:
                        continue
                    cand = cur + v
                    if cand > nrow[sal + w]:
                        nrow[sal + w] = cand
                        nlu[sal + w] = lrow[sal] + ((pi, pos),)

    full = s_index[tuple(ROSTER_MAX[p] for p in POS_ORDER)]
    results: Dict[int, Dict[str, Any]] = {}
    for cap in caps:
        cu = cap // unit
        row = best[full]
        top, at = NEG, None
        for sal in range(cu + 1):
            if row[sal] > top:
                top, at = row[sal], sal
        if at is None or lus[full][at] is None:
            results[cap] = {"lineup": [], "salary_used": 0, "total": 0.0,
                            "note": "no feasible lineup at this cap"}
            continue
        picks = lus[full][at]
        assert len({pi for pi, _ in picks}) == len(picks), \
            "optimizer invariant violated: duplicate player in lineup"
        lineup = []
        for pi, pos in picks:
            entry = dict(pool[pi])
            entry["slot_pos"] = pos
            lineup.append(entry)
        results[cap] = {"lineup": lineup,
                        "salary_used": sum(int(x["salary"]) for x in lineup),
                        "total": round(top, 2)}
    return results


def _slotify(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    order = {"P": 0, "C": 1, "1B": 2, "2B": 3, "3B": 4, "SS": 5, "OF": 6}
    rows = sorted(lineup, key=lambda x: (order.get(x.get("slot_pos"), 9),
                                          -(x.get("proj") or 0)))
    counters: Dict[str, int] = {}
    out = []
    for r in rows:
        pos = r.get("slot_pos")
        counters[pos] = counters.get(pos, 0) + 1
        label = pos if ROSTER_MAX.get(pos, 1) == 1 else f"{pos}{counters[pos]}"
        out.append({"slot": label, "name": r.get("name"), "team": r.get("team"),
                    "pos": r.get("pos"), "salary": r.get("salary"),
                    "proj": r.get("proj")})
    return out


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def run() -> Dict[str, Any]:
    now = dt.datetime.now().isoformat(timespec="seconds")
    slate = fetch_slate()
    if not slate:
        payload = {"generated_at": now, "slate": None,
                   "note": "No DraftKings MLB Classic slate available (or DK unreachable with no cache)."}
        _write(OUT, payload)
        return payload

    players = slate.get("players") or []
    probables = _probable_pitchers()

    projections: List[Dict[str, Any]] = []
    unprojected = 0
    n_sp_pool = 0
    for p in players:
        elig = _eligible(p.get("pos"))
        if not elig:
            continue
        is_pitcher = elig == ["P"]
        nm = _norm(p.get("name"))
        proj = None
        source = None
        if is_pitcher:
            # probable starters only
            pid = probables.get(nm)
            if pid is None:
                continue
            try:
                season = sr.pitcher_season(pid)
            except Exception:
                season = {}
            proj = pitcher_dk_mean(season or {})
            source = "season_per_start"
            if proj is not None:
                n_sp_pool += 1
        else:
            pid = pp.resolve_player_id(p.get("name") or "")
            if pid:
                try:
                    season = pp._batter_season(pid)
                except Exception:
                    season = {}
                proj = hitter_dk_mean(season or {})
                source = "season_per_game"
        if proj is None:
            unprojected += 1
            continue
        projections.append({
            "name": p.get("name"), "pos": p.get("pos"), "elig": elig,
            "team": p.get("team"), "game": p.get("game"),
            "salary": p.get("salary"), "status": p.get("status") or "",
            "proj": proj,
            "value": round(proj / (p["salary"] / 1000.0), 2) if p.get("salary") else None,
            "source": source,
        })

    # Lineup pool: prune per slot family (keep it exact but fast).
    playable = [p for p in projections if p.get("status") not in ("O", "OUT", "IR")]
    def _top(pred, n_by_proj, n_by_value):
        rows = [p for p in playable if pred(p)]
        by_p = sorted(rows, key=lambda x: -(x["proj"] or 0))[:n_by_proj]
        by_v = sorted(rows, key=lambda x: -(x["value"] or 0))[:n_by_value]
        seen, out = set(), []
        for r in by_p + by_v:
            k = (r["name"], r["team"])
            if k not in seen:
                seen.add(k)
                out.append(r)
        return out
    pool = (_top(lambda p: "P" in p["elig"], 10, 4)
            + _top(lambda p: "C" in p["elig"] and p["elig"] != ["P"], 8, 4)
            + _top(lambda p: any(x in p["elig"] for x in ("1B", "2B", "3B", "SS")), 30, 12)
            + _top(lambda p: "OF" in p["elig"], 22, 10))
    # dedup across the family buckets
    seen: set = set()
    pool = [p for p in pool if not ((p["name"], p["team"]) in seen
                                     or seen.add((p["name"], p["team"])))]

    lineups: Dict[str, Any] = {}
    budget_table: List[Dict[str, Any]] = []
    if pool and any("P" in p["elig"] for p in pool):
        res = optimize(pool, "proj")
        main = res.get(SALARY_CAP) or {}
        lineups["optimal"] = {
            "objective": "proj (mean)",
            "slots": _slotify(main.get("lineup") or []),
            "salary_used": main.get("salary_used"),
            "proj_total": main.get("total"),
        }
        for cap in CAPS:
            r = res.get(cap) or {}
            budget_table.append({"cap": cap, "salary_used": r.get("salary_used"),
                                 "proj_total": r.get("total")})

    payload = {
        "generated_at": now,
        "slate": {"draft_group_id": slate.get("draft_group_id"),
                  "start": slate.get("start"), "suffix": slate.get("suffix"),
                  "n_games": len(slate.get("games") or []),
                  "n_salaried": len(players)},
        "universe": {"n_projected": len(projections),
                     "n_probable_sp": n_sp_pool,
                     "n_unprojected": unprojected},
        "projections": sorted(projections, key=lambda x: -(x["proj"] or 0)),
        "lineups": lineups,
        "budget_variants": budget_table,
        "scoring": "DraftKings MLB Classic (hitters 3/5/8/10 + 2s, 5 SB; pitchers 2.25 IP / 2 K / 4 W / -2 ER / -0.6 H,BB)",
        "method_note": ("v1 MEAN projections from season rates -- hitters per-game, "
                        "probable starters per-start (matchups.json probables only; "
                        "the 380-arm bullpen pool is excluded). Exact 0/1 DP optimizer "
                        "over position-counts x $100 salary buckets with FULL "
                        "dual-eligibility (a 2B/SS may be seated at either slot), "
                        "brute-force-verified in the module self-test. No "
                        "lineup-order/park/platoon/weather adjustment yet and no "
                        "floor/ceiling -- that's the v2 Monte Carlo treatment, same "
                        "as the NFL desk."),
        "disclosures": [
            "Mean-based v1: no distributions, no lineup-order/park/platoon/weather adjustment.",
            "A hitter who sits scores 0 -- confirm lineups before lock.",
            "Pitcher W component is season wins-per-start (crude).",
            "CG/no-hitter bonuses ignored (~0.05 pts EV).",
            "DFS projections are informational only and never enter the betting ledger. 21+.",
        ],
    }
    _write(OUT, payload)
    return payload


# --------------------------------------------------------------------------
# self-test: DP (with dual-eligibility) vs brute force
# --------------------------------------------------------------------------

def _self_test() -> bool:
    import itertools, random
    rng = random.Random(7)
    ok = True
    for trial in range(3):
        pool = []
        specs = [("P", 4), ("C", 3), ("1B", 3), ("2B", 3), ("3B", 3), ("SS", 3), ("OF", 5)]
        for pos, n in specs:
            for i in range(n):
                pool.append({"name": f"{pos}{i}", "elig": [pos],
                             "salary": rng.randrange(20, 60) * 100,
                             "proj": round(rng.uniform(3, 22), 2)})
        # two dual-eligible bats
        pool.append({"name": "DUAL_2B_SS", "elig": ["2B", "SS"],
                     "salary": 4100, "proj": 21.5})
        pool.append({"name": "DUAL_1B_OF", "elig": ["1B", "OF"],
                     "salary": 3900, "proj": 20.9})
        cap = 42000
        res = optimize(pool, "proj", caps=(cap,))[cap]
        dp_total = round(res.get("total") or -1, 2)
        # brute force: choose per-slot assignment via itertools over eligible sets
        by_slot = {pos: [p for p in pool if pos in p["elig"]] for pos in POS_ORDER}
        best_bf = -1.0
        for ps in itertools.combinations(by_slot["P"], 2):
            for c in by_slot["C"]:
                for b1 in by_slot["1B"]:
                    for b2 in by_slot["2B"]:
                        for b3 in by_slot["3B"]:
                            for ss in by_slot["SS"]:
                                for ofs in itertools.combinations(by_slot["OF"], 3):
                                    lu = list(ps) + [c, b1, b2, b3, ss] + list(ofs)
                                    names = [x["name"] for x in lu]
                                    if len(set(names)) != 10:
                                        continue
                                    if sum(x["salary"] for x in lu) > cap:
                                        continue
                                    tot = sum(x["proj"] for x in lu)
                                    if tot > best_bf:
                                        best_bf = tot
        if abs(dp_total - round(best_bf, 2)) > 1e-6:
            print(f"  SELF-TEST FAIL trial {trial}: DP {dp_total} vs brute {round(best_bf, 2)}")
            ok = False
        else:
            print(f"  self-test trial {trial}: DP == brute force == {dp_total} OK")
    return ok


if __name__ == "__main__":
    print("[mlb-dfs] optimizer self-test (exact DP + dual-eligibility vs brute force):")
    if not _self_test():
        raise SystemExit("mlb_dfs optimizer self-test FAILED")
    o = run()
    sl = o.get("slate")
    if not sl:
        print(f"[mlb-dfs] {o.get('note')}")
    else:
        u = o.get("universe") or {}
        print(f"[mlb-dfs] slate {sl['draft_group_id']} start {sl['start']} "
              f"({sl.get('suffix') or 'Main'}) · {sl['n_games']} games · "
              f"{sl['n_salaried']} salaried")
        print(f"  projected {u.get('n_projected')} ({u.get('n_probable_sp')} probable SP) "
              f"· unprojected {u.get('n_unprojected')}")
        lu = (o.get("lineups") or {}).get("optimal") or {}
        if lu.get("slots"):
            print(f"  OPTIMAL ({lu.get('salary_used')}/{SALARY_CAP}): {lu.get('proj_total')} pts")
            for s in lu["slots"]:
                print(f"    {s['slot']:4s} {s['name']:24s} {s['team']:4s} "
                      f"${s['salary']}  {s['proj']}")
