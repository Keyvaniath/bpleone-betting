"""
EdgeStat -- NFL DFS desk: weekly DraftKings projections from OUR model + exact
salary-cap optimal lineups.

PIPELINE
  1. SLATE: DraftKings' public lobby (getcontests) -> the next CLASSIC draft
     group at/after Week 1 (preseason slates are skipped -- same honesty gate as
     nfl_player_props) -> draftables = every salaried player on the slate.
  2. PROJECTIONS (skill players): per-player DK fantasy-point DISTRIBUTIONS from
     the same play-level Monte Carlo the props desk uses (nfl_simulator via
     nfl_player_props._sim_player). Baselines, in priority order:
       a. curated NFL_PLAYER_DB priors (28 stars),
       b. 2025 season per-game rates from ESPN's athlete statistics API
          (fetched once per player, cached in data/nfl_2025_baselines.json),
       c. in-season: current-year gamelogs blend in automatically through
          _sim_player's _recent_base/_blend machinery, and players with >= 3
          current-season games get a gamelog-only baseline (covers rookies).
     DK scoring is applied PER SIMULATION so the 100/300-yard bonuses are
     captured on the tail sims, not bolted onto a point estimate. We publish
     mean / floor (p10) / ceiling (p90) -- the distribution IS the edge.
  3. DST: Vegas-implied -- opponent implied total (from the free ESPN/DK line
     for the slate date) through DK's points-allowed tiers + league-average
     sacks/takeaways/return-TD rates. Explicitly labeled bookline-derived, NOT
     the player MC. No lines posted yet -> flat league-average projection and
     the page says the DST slot is a salary-saver until lines post.
  4. OPTIMIZER: EXACT 0/1 dynamic program over (position-counts x salary in
     $100 units) -- DK Classic: QB, 2 RB, 3 WR, TE, FLEX(RB/WR/TE), DST,
     $50,000 cap. Three builds (mean / ceiling p90 / floor p10) + budget
     variants read off the same DP table. Verified against brute-force
     enumeration on small pools in the __main__ self-test.

HONESTY DISCLOSURES (also published in the payload):
  - Rookies/players with no 2025 NFL stats and < 3 current-season games have no
    baseline -> excluded from the pool, count + biggest-salary names disclosed.
  - 2025 baselines carry a usage-change blind spot (trades, new roles) until
    current-season gamelogs accumulate.
  - Fumbles lost / 2-pt conversions are not simulated (~0.1-0.3 pts).
  - Pass/rush/receive sim groups are index-aligned within a group but
    independent ACROSS groups (slightly narrows QB rush correlation tails).
  - DFS projections are NOT wagers and never enter the betting ledger.

Output: data/nfl_dfs.json
"""
from __future__ import annotations

import os
import json
import re
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import nfl_player_props as npp
import nfl_baselines as nb

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SAL_CACHE = os.path.join(DATA_DIR, "nfl_dfs_salaries.json")
OUT = os.path.join(DATA_DIR, "nfl_dfs.json")

SIM_N = 2000            # per-player sims (mean se ~0.3 pts; props desk uses 4000 on 28)
SALARY_CAP = 50000
BUDGET_VARIANTS = (45000, 48000, 50000)
NFL_2026_WEEK1 = "2026-09-08"

# DK Classic roster: QB, RB, RB, WR, WR, WR, TE, FLEX(RB/WR/TE), DST.
POS_MIN = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
POS_MAX = {"QB": 1, "RB": 3, "WR": 4, "TE": 2, "DST": 1}
N_SLOTS = 9
FLEX_TOTAL = 7          # RB + WR + TE combined

H = {"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"}

# League-average DST components (DK points): sacks ~2.4/gm x1, takeaways
# ~1.35/gm x2, defensive/return TD ~0.14/gm x6.
DST_BASE = 2.4 * 1.0 + 1.35 * 2.0 + 0.14 * 6.0     # ~5.94
# DK points-allowed tiers, interpolated at tier midpoints for a smooth curve.
DST_PA_CURVE = [(0.0, 10.0), (3.5, 7.0), (10.0, 4.0), (17.0, 1.0),
                (24.0, 0.0), (31.0, -1.0), (38.0, -4.0)]


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


# Name normalization + roster/baseline machinery live in nfl_baselines (shared
# with the props desk so the two universes can't drift).
_norm_name = nb.norm_name


# --------------------------------------------------------------------------
# 1. DK slate (lobby -> classic draft group -> salaried draftables)
# --------------------------------------------------------------------------

def fetch_slate() -> Optional[Dict[str, Any]]:
    """Next non-preseason CLASSIC slate. Returns {draft_group_id, start, players,
    games} or the cached copy when DK is unreachable (no-clobber)."""
    try:
        lobby = _get("https://www.draftkings.com/lobby/getcontests?sport=NFL")
        groups = lobby.get("DraftGroups") or []
    except Exception as e:
        print(f"[nfl-dfs] DK lobby unreachable ({e!r}) -- using cached slate if any")
        cached = _load(SAL_CACHE)
        return cached if cached.get("players") else None

    candidates = []
    for g in groups:
        if g.get("ContestTypeId") != 21:      # 21 = Classic
            continue
        suffix = str(g.get("ContestStartTimeSuffix") or "").lower()
        if "preseason" in suffix:
            continue
        start = str(g.get("StartDateEst") or "")[:10]
        if start and start >= NFL_2026_WEEK1:
            candidates.append((start, g.get("DraftGroupId")))
    candidates.sort()
    if not candidates:
        return None

    # Among same-day classics (Main/Early/Late/...), take the one with the most
    # salaried players = the Main slate. Fetch at most 4 candidate groups.
    first_day = candidates[0][0]
    best = None
    for start, dgid in [c for c in candidates if c[0] == first_day][:4]:
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
            seen[pid] = {
                "name": p.get("displayName"),
                "pos": p.get("position"),
                "salary": p.get("salary"),
                "team": (p.get("teamAbbreviation") or "").upper(),
                "game": comp,
                "status": p.get("status") or "",
            }
        if seen and (best is None or len(seen) > len(best["players"])):
            best = {"draft_group_id": dgid, "start": start,
                    "players": list(seen.values()), "games": sorted(games)}
    if best:
        best["fetched_at"] = dt.datetime.now().isoformat(timespec="seconds")
        _write(SAL_CACHE, best)
        return best
    cached = _load(SAL_CACHE)
    return cached if cached.get("players") else None


# --------------------------------------------------------------------------
# 2./3. Baselines + projections (shared machinery in nfl_baselines)
# --------------------------------------------------------------------------

def _pct(sorted_xs: List[float], q: float) -> float:
    i = min(len(sorted_xs) - 1, max(0, int(q * len(sorted_xs))))
    return sorted_xs[i]


# DK Classic scoring lives in nfl_player_props.dk_points_from_sims (one scorer,
# shared with the props/projections artifact so the two can never disagree).
_dk_points = npp.dk_points_from_sims


def _opp_of(player_team: str, game: str) -> Optional[str]:
    if "@" not in (game or ""):
        return None
    away, _, home = [s.strip().upper() for s in game.partition("@")]
    if player_team == home:
        return away
    if player_team == away:
        return home
    return None


def _pa_curve(implied: float) -> float:
    pts = DST_PA_CURVE
    if implied <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if implied <= x1:
            return y0 + (y1 - y0) * (implied - x0) / (x1 - x0)
    return pts[-1][1]


def fetch_slate_lines(slate_dates: List[str]) -> Dict[str, Dict[str, Any]]:
    """matchup 'AWAY @ HOME' -> {spread, total} from ESPN's dated scoreboard."""
    out: Dict[str, Dict[str, Any]] = {}
    for d in slate_dates[:3]:
        try:
            data = _get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                        f"scoreboard?dates={d.replace('-', '')}")
        except Exception:
            continue
        for e in data.get("events") or []:
            comp = (e.get("competitions") or [{}])[0]
            teams = {t.get("homeAway"): t for t in (comp.get("competitors") or [])}
            hab = ((teams.get("home") or {}).get("team") or {}).get("abbreviation")
            aab = ((teams.get("away") or {}).get("team") or {}).get("abbreviation")
            if not hab or not aab:
                continue
            odds = (comp.get("odds") or [{}])[0]
            out[f"{aab.upper()} @ {hab.upper()}"] = {
                "spread": odds.get("spread"), "total": odds.get("overUnder")}
    return out


# --------------------------------------------------------------------------
# 4. Exact lineup optimizer (0/1 DP over position-counts x salary buckets)
# --------------------------------------------------------------------------

_POS_I = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}


def _count_states() -> List[Tuple[int, int, int, int, int]]:
    states = []
    for qb in range(POS_MAX["QB"] + 1):
        for rb in range(POS_MAX["RB"] + 1):
            for wr in range(POS_MAX["WR"] + 1):
                for te in range(POS_MAX["TE"] + 1):
                    for d in range(POS_MAX["DST"] + 1):
                        if rb + wr + te <= FLEX_TOTAL and qb + rb + wr + te + d <= N_SLOTS:
                            states.append((qb, rb, wr, te, d))
    return states


def optimize(pool: List[Dict[str, Any]], obj_key: str,
             caps: Tuple[int, ...] = BUDGET_VARIANTS) -> Dict[str, Any]:
    """Exact DP. pool rows need: name, pos, salary, and obj_key (points).
    Returns {cap: {lineup, salary_used, total}} for each requested cap."""
    # LINEUP-PAYLOAD DP (2026-08-17): cells store their FULL lineup (tuple of
    # pool indices), not parent pointers -- pointer walk-back is unsound in a
    # value-overwriting knapsack table (an ancestor cell can improve after a
    # descendant records provenance; the mixed-path reconstruction seated the
    # same OF twice on the MLB desk's first real slate). Same fix here because
    # the flaw was latent and identical.
    unit = 100
    max_units = max(caps) // unit
    states = _count_states()
    s_index = {s: i for i, s in enumerate(states)}
    NEG = float("-inf")
    best = [[NEG] * (max_units + 1) for _ in states]
    lus: List[List[Optional[Tuple[int, ...]]]] = [[None] * (max_units + 1) for _ in states]
    start_i = s_index[(0, 0, 0, 0, 0)]
    best[start_i][0] = 0.0
    lus[start_i][0] = ()

    order = sorted(range(len(states)), key=lambda i: -sum(states[i]))  # high count first
    for pi, p in enumerate(pool):
        w = int(p["salary"]) // unit
        v = float(p.get(obj_key) or 0.0)
        d = _POS_I[p["pos"]]
        for si in order:
            st = states[si]
            new = list(st)
            new[d] += 1
            if new[d] > POS_MAX[p["pos"]]:
                continue
            if new[1] + new[2] + new[3] > FLEX_TOTAL:
                continue
            ni = s_index.get(tuple(new))
            if ni is None:
                continue
            row, lrow = best[si], lus[si]
            nrow, nlu = best[ni], lus[ni]
            for sal in range(max_units - w, -1, -1):
                cur = row[sal]
                if cur == NEG:
                    continue
                cand = cur + v
                if cand > nrow[sal + w]:
                    nrow[sal + w] = cand
                    nlu[sal + w] = lrow[sal] + (pi,)

    results: Dict[int, Dict[str, Any]] = {}
    valid_states = [s_index[s] for s in states
                    if s[0] == 1 and s[4] == 1 and s[1] >= POS_MIN["RB"]
                    and s[2] >= POS_MIN["WR"] and s[3] >= POS_MIN["TE"]
                    and s[1] + s[2] + s[3] == FLEX_TOTAL]
    for cap in caps:
        cu = cap // unit
        top, at = NEG, None
        for si in valid_states:
            row = best[si]
            for sal in range(cu + 1):
                if row[sal] > top:
                    top, at = row[sal], (si, sal)
        if at is None or lus[at[0]][at[1]] is None:
            results[cap] = {"lineup": [], "salary_used": 0, "total": 0.0,
                            "note": "no feasible lineup at this cap"}
            continue
        picks = lus[at[0]][at[1]]
        assert len(set(picks)) == len(picks), \
            "optimizer invariant violated: duplicate player in lineup"
        lineup = [pool[pi] for pi in picks]
        results[cap] = {
            "lineup": lineup,
            "salary_used": sum(int(p["salary"]) for p in lineup),
            "total": round(top, 2),
        }
    return results


def _slotify(lineup: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Assign display slots: QB, RB1, RB2, WR1-3, TE, FLEX, DST."""
    by_pos: Dict[str, List[Dict[str, Any]]] = {}
    for p in sorted(lineup, key=lambda x: -(x.get("proj") or 0)):
        by_pos.setdefault(p["pos"], []).append(p)
    slots = []
    def emit(pos, n, label=None):
        for i in range(n):
            if by_pos.get(pos):
                slots.append({"slot": label or (pos if n == 1 else f"{pos}{i+1}"),
                              **by_pos[pos].pop(0)})
    emit("QB", 1)
    emit("RB", 2)
    emit("WR", 3)
    emit("TE", 1)
    flex = (by_pos.get("RB") or []) + (by_pos.get("WR") or []) + (by_pos.get("TE") or [])
    if flex:
        f = max(flex, key=lambda x: x.get("proj") or 0)
        slots.append({"slot": "FLEX", **f})
    emit("DST", 1)
    return slots


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def run() -> Dict[str, Any]:
    now = dt.datetime.now().isoformat(timespec="seconds")
    slate = fetch_slate()
    if not slate:
        payload = {"generated_at": now, "slate": None,
                   "note": ("No non-preseason DraftKings Classic slate available yet "
                            "(or DK unreachable with no cache). DFS resumes with the "
                            "Week 1 slate.")}
        _write(OUT, payload)
        return payload

    players = slate.get("players") or []
    skill = [p for p in players if p.get("pos") in ("QB", "RB", "WR", "TE")]
    dsts = [p for p in players if p.get("pos") == "DST"]

    roster_idx = nb.roster_index()
    gl_all = _load(os.path.join(DATA_DIR, "nfl_player_gamelogs.json")).get("by_name") or {}

    # Resolve espn ids for the slate's skill players (team-aware on collisions).
    needed: List[Tuple[str, str]] = []
    resolved: Dict[str, str] = {}       # dk name -> espn id
    ambiguous = 0
    for p in skill:
        cands = roster_idx.get(_norm_name(p["name"])) or []
        if len(cands) > 1:
            cands = [c for c in cands if c["team"] == p["team"]] or \
                    [c for c in cands if c["pos"] == p["pos"]] or []
        if len(cands) == 1:
            resolved[p["name"]] = cands[0]["id"]
            needed.append((cands[0]["id"], p["name"]))
        elif cands:
            ambiguous += 1
    baselines = nb.ensure_baselines(needed)

    projections: List[Dict[str, Any]] = []
    unprojected: List[Dict[str, Any]] = []
    for p in skill:
        opp = _opp_of(p["team"], p.get("game") or "")
        nm = _norm_name(p["name"])
        info, source = nb.resolve_info(nm, p["pos"], resolved.get(p["name"]),
                                       baselines, gl_all, npp.NFL_PLAYER_DB)
        if info is None:
            unprojected.append(p)
            continue
        pass_f = npp._opp_factor(npp.PASS_DEF, opp or "")
        rush_f = npp._opp_factor(npp.RUSH_DEF, opp or "")
        seed = (sum(ord(c) for c in nm) * 131 + 7) % 1_000_000
        sims = npp._sim_player(nm, info, gl_all, pass_f, rush_f, seed)
        if not sims:
            unprojected.append(p)
            continue
        n = len(next(iter(sims.values())))
        fps = sorted(_dk_points(sims, n))
        mean = sum(fps) / n
        sd = (sum((x - mean) ** 2 for x in fps) / n) ** 0.5
        # Provenance: the baseline sample behind the sim + a primary-source link.
        espn_id = resolved.get(p["name"])
        bl = baselines.get(espn_id) if espn_id else None
        gp_2025 = int(bl.get("gamesPlayed") or 0) if (bl and not bl.get("no_data")) else None
        projections.append({
            "name": p["name"], "pos": p["pos"], "team": p["team"],
            "opp": opp, "game": p.get("game"), "salary": p["salary"],
            "status": p.get("status") or "",
            "proj": round(mean, 2),
            "floor": round(_pct(fps, 0.10), 2),
            "ceiling": round(_pct(fps, 0.90), 2),
            "sd": round(sd, 2),
            "value": round(mean / (p["salary"] / 1000.0), 2) if p["salary"] else None,
            "source": source,
            "gp_2025": gp_2025,
            "espn_id": espn_id,
            "src_url": (f"https://www.espn.com/nfl/player/_/id/{espn_id}"
                        if espn_id else None),
        })

    # DST projections (Vegas-implied; league-average flat when no lines yet).
    slate_dates = sorted({str(slate.get("start") or "")[:10]})
    lines = fetch_slate_lines(slate_dates)
    n_dst_lines = 0
    for p in dsts:
        game_key = None
        implied_opp = None
        for mk, ln in lines.items():
            if p["team"] in mk.split(" @ "):
                game_key = mk
                total, spread = ln.get("total"), ln.get("spread")
                if total is not None and spread is not None:
                    away, _, home = [s.strip() for s in mk.partition("@")]
                    # ESPN spread is the home line (negative = home favored).
                    home_pts = total / 2.0 - spread / 2.0
                    away_pts = total / 2.0 + spread / 2.0
                    implied_opp = away_pts if p["team"] == home.strip() else home_pts
                break
        if implied_opp is not None:
            proj = DST_BASE + _pa_curve(implied_opp)
            source = "vegas_implied"
            n_dst_lines += 1
        else:
            proj = DST_BASE + _pa_curve(21.5)   # league-average game
            source = "league_avg_no_lines"
        projections.append({
            "name": p["name"], "pos": "DST", "team": p["team"],
            "opp": _opp_of(p["team"], p.get("game") or ""), "game": p.get("game"),
            "salary": p["salary"], "status": p.get("status") or "",
            "proj": round(proj, 2), "floor": round(proj - 4.0, 2),
            "ceiling": round(proj + 6.0, 2), "sd": None,
            "value": round(proj / (p["salary"] / 1000.0), 2) if p["salary"] else None,
            "source": source,
        })

    # ---- lineup pools: exclude ruled-out players; prune per position ----
    playable = [p for p in projections if p.get("status") not in ("O", "IR", "OUT")]
    def _top(pos, n_by_proj, n_by_value):
        rows = [p for p in playable if p["pos"] == pos]
        by_p = sorted(rows, key=lambda x: -(x["proj"] or 0))[:n_by_proj]
        by_v = sorted(rows, key=lambda x: -(x["value"] or 0))[:n_by_value]
        seen, out = set(), []
        for r in by_p + by_v:
            k = (r["name"], r["team"])
            if k not in seen:
                seen.add(k)
                out.append(r)
        return out
    pool = (_top("QB", 12, 6) + _top("RB", 24, 10) + _top("WR", 30, 12)
            + _top("TE", 14, 6) + _top("DST", 10, 4))

    lineups: Dict[str, Any] = {}
    budget_table: List[Dict[str, Any]] = []
    if pool and any(p["pos"] == "DST" for p in pool):
        for label, key in (("optimal", "proj"), ("ceiling", "ceiling"), ("cash", "floor")):
            res = optimize(pool, key)
            main = res.get(SALARY_CAP) or {}
            lineups[label] = {
                "objective": key,
                "slots": _slotify(main.get("lineup") or []),
                "salary_used": main.get("salary_used"),
                "proj_total": round(sum(p.get("proj") or 0 for p in main.get("lineup") or []), 2),
                "objective_total": main.get("total"),
            }
            if label == "optimal":
                for cap in BUDGET_VARIANTS:
                    r = res.get(cap) or {}
                    budget_table.append({"cap": cap, "salary_used": r.get("salary_used"),
                                         "proj_total": r.get("total")})

    top_unproj = sorted(unprojected, key=lambda p: -(p.get("salary") or 0))[:6]
    payload = {
        "generated_at": now,
        "slate": {"draft_group_id": slate.get("draft_group_id"),
                  "start": slate.get("start"),
                  "n_games": len(slate.get("games") or []),
                  "n_salaried": len(players)},
        "universe": {
            "n_skill_salaried": len(skill),
            "n_projected": sum(1 for p in projections if p["pos"] != "DST"),
            "n_unprojected": len(unprojected),
            "n_ambiguous_names": ambiguous,
            "n_dst": len(dsts),
            "n_dst_with_lines": n_dst_lines,
            "top_unprojected": [{"name": p["name"], "pos": p["pos"], "salary": p["salary"]}
                                 for p in top_unproj],
        },
        "projections": sorted(projections, key=lambda x: -(x["proj"] or 0)),
        "lineups": lineups,
        "budget_variants": budget_table,
        "scoring": "DraftKings Classic (full PPR, 4pt pass TD, 100/300-yd bonuses per-sim)",
        "method_note": ("Skill projections = the props desk's play-level Monte Carlo "
                        "(NegBinomial counts x Gamma yards x Poisson TDs, opponent-"
                        "adjusted), DK-scored PER SIMULATION so yardage bonuses land on "
                        "the tail sims. Baselines: curated priors > 2025 season rates > "
                        "current-season gamelogs (in-season form blends in "
                        "automatically). DST is Vegas-implied, not the player MC. "
                        "Optimizer is an EXACT DP over position-counts x $100 salary "
                        "buckets (brute-force-verified in the module self-test)."),
        "disclosures": [
            "Rookies/players with no 2025 NFL stats and <3 current-season games have no baseline and are excluded (count above).",
            "2025 baselines carry a usage-change blind spot (trades/new roles) until current-season gamelogs accumulate.",
            "Fumbles lost and 2-pt conversions are not simulated (~0.1-0.3 pts).",
            "Sim groups are independent across pass/rush/receive (slightly narrows dual-threat correlation tails).",
            "DST projection is bookline-derived; with no lines posted it is a flat league-average number -- treat the DST slot as a salary-saver until lines post.",
            "DFS projections are informational only and never enter the betting ledger. 21+.",
        ],
    }
    _write(OUT, payload)
    return payload


# --------------------------------------------------------------------------
# self-test: DP vs brute force on small pools
# --------------------------------------------------------------------------

def _self_test() -> bool:
    import itertools, random
    rng = random.Random(42)
    ok = True
    for trial in range(3):
        pool = []
        for pos, n in (("QB", 3), ("RB", 5), ("WR", 6), ("TE", 3), ("DST", 3)):
            for i in range(n):
                pool.append({"name": f"{pos}{i}", "pos": pos,
                             "salary": rng.randrange(25, 90) * 100,
                             "proj": round(rng.uniform(4, 28), 2)})
        cap = 42000
        res = optimize(pool, "proj", caps=(cap,))[cap]
        # brute force
        by = {pos: [p for p in pool if p["pos"] == pos] for pos in ("QB", "RB", "WR", "TE", "DST")}
        best_bf = -1.0
        for rb_n, wr_n, te_n in ((2, 4, 1), (3, 3, 1), (2, 3, 2)):
            for qb in itertools.combinations(by["QB"], 1):
                for rb in itertools.combinations(by["RB"], rb_n):
                    for wr in itertools.combinations(by["WR"], wr_n):
                        for te in itertools.combinations(by["TE"], te_n):
                            for d in itertools.combinations(by["DST"], 1):
                                lu = qb + rb + wr + te + d
                                if sum(p["salary"] for p in lu) <= cap:
                                    tot = sum(p["proj"] for p in lu)
                                    if tot > best_bf:
                                        best_bf = tot
        dp_total = round(res.get("total") or -1, 2)
        if abs(dp_total - round(best_bf, 2)) > 1e-6:
            print(f"  SELF-TEST FAIL trial {trial}: DP {dp_total} vs brute {round(best_bf,2)}")
            ok = False
        else:
            print(f"  self-test trial {trial}: DP == brute force == {dp_total} OK")
    return ok


if __name__ == "__main__":
    print("[nfl-dfs] optimizer self-test (exact DP vs brute force):")
    if not _self_test():
        raise SystemExit("nfl_dfs optimizer self-test FAILED")
    o = run()
    sl = o.get("slate")
    if not sl:
        print(f"[nfl-dfs] {o.get('note')}")
    else:
        u = o.get("universe") or {}
        print(f"[nfl-dfs] slate {sl['draft_group_id']} start {sl['start']} · "
              f"{sl['n_games']} games · {sl['n_salaried']} salaried")
        print(f"  projected {u.get('n_projected')}/{u.get('n_skill_salaried')} skill + "
              f"{u.get('n_dst')} DST ({u.get('n_dst_with_lines')} with lines) · "
              f"unprojected {u.get('n_unprojected')}")
        lu = (o.get("lineups") or {}).get("optimal") or {}
        if lu.get("slots"):
            print(f"  OPTIMAL ({lu.get('salary_used')}/50000): "
                  f"proj {lu.get('proj_total')} pts")
            for s in lu["slots"]:
                print(f"    {s['slot']:5s} {s['name']:24s} {s['team']:4s} "
                      f"${s['salary']}  {s.get('proj')}")
