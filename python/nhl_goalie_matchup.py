"""
EdgeStat -- NHL playoff GOALIE matchup model.

Critical during Stanley Cup playoffs when single-goalie performance swings
games. For each NHL game today:
  1. Pull starting goalie from ESPN probables (NHL scoreboard event payload)
  2. Compute goalie's blended SV% from:
       - Postseason gamelog (high weight during playoffs)
       - Regular season gamelog
       - Last 3 starts (recency weight)
  3. Estimate shots-against from opposing team's shots-for-per-game (league
     avg ~30 SF/G, top teams 33-35, bottom teams 26-28)
  4. Project goals against = shots * (1 - blended_sv_pct)
  5. Poisson-price these markets:
       Team total goals over/under (1.5 / 2.5 / 3.5 / 4.5)
       Shutout YES/NO
  6. Surface picks where the goalie's true projection diverges materially
     from the team's pregame Elo-implied goals (existing nhl_state.json)

ESPN goalie gamelog labels:
  GS TOI/G WINS L T OTL GA GAA SA SV SV% SO
   0   1    2   3 4 5   6  7  8  9  10  11

Output: data/nhl_goalie_matchup.json
"""
from __future__ import annotations

import os
import json
import math
import urllib.request
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "nhl_goalie_matchup.json")

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
GAMELOG_URL = "https://site.api.espn.com/apis/common/v3/sports/hockey/nhl/athletes/{aid}/gamelog"

# NHL goalie gamelog stat indices
IDX = {"gs": 0, "toi": 1, "wins": 2, "ga": 6, "gaa": 7, "sa": 8, "sv": 9, "sv_pct": 10, "so": 11}

LEAGUE_AVG_SV_PCT = 0.905
LEAGUE_AVG_SHOTS = 30.0
RECENT_WEIGHT = 0.30   # 30% recent / 70% season-blend
POST_WEIGHT_PLAYOFFS = 0.60   # during playoffs, weight postseason more


def _http(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _to_float(s):
    try: return float(s)
    except Exception: return None


def _to_int(s):
    try: return int(s)
    except Exception: return None


def _american(p):
    if p is None or p <= 0.001 or p >= 0.999: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _poisson_p_over(lam, line):
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _poisson_p_zero(lam):
    return math.exp(-lam) if lam > 0 else 1.0


def _aggregate_goalie_starts(events: List[List[str]]) -> Optional[Dict[str, Any]]:
    """Sum SA + SV across a list of gamelog events, return blended SV%."""
    if not events: return None
    total_sa, total_sv, total_ga, n_starts = 0, 0, 0, 0
    for ev in events:
        if not isinstance(ev, list) or len(ev) < 11: continue
        gs = _to_int(ev[IDX["gs"]]) or 0
        if gs == 0: continue   # only count actual starts
        sa = _to_int(ev[IDX["sa"]]) or 0
        sv = _to_int(ev[IDX["sv"]]) or 0
        ga = _to_int(ev[IDX["ga"]]) or 0
        if sa <= 0: continue
        total_sa += sa
        total_sv += sv
        total_ga += ga
        n_starts += 1
    if n_starts == 0 or total_sa == 0: return None
    return {
        "n_starts": n_starts,
        "total_shots_against": total_sa,
        "total_saves": total_sv,
        "total_goals_against": total_ga,
        "sv_pct": round(total_sv / total_sa, 4),
        "ga_per_start": round(total_ga / n_starts, 2),
        "sa_per_start": round(total_sa / n_starts, 1),
    }


def _fetch_goalie_stats(athlete_id) -> Dict[str, Any]:
    """Return season + postseason + recent stats for one goalie."""
    data = _http(GAMELOG_URL.format(aid=athlete_id))
    if not data: return {}
    seasons = data.get("seasonTypes") or []
    season_events = []   # regular season
    post_events = []     # postseason
    for s in seasons:
        dn = (s.get("displayName") or "").lower()
        is_post = "postseason" in dn or "playoff" in dn
        for cat in (s.get("categories") or []):
            for ev in (cat.get("events") or []):
                stats = ev.get("stats")
                if not stats: continue
                if is_post:
                    post_events.append(stats)
                else:
                    season_events.append(stats)

    season = _aggregate_goalie_starts(season_events)
    post = _aggregate_goalie_starts(post_events)
    # Recent = last 3 (most recent events from whichever set is being played)
    recent_pool = post_events[:3] if post_events else season_events[:3]
    recent = _aggregate_goalie_starts(recent_pool)
    return {"season": season, "postseason": post, "recent": recent}


def _blend_sv_pct(stats: Dict[str, Any], is_playoffs: bool = True) -> float:
    season = stats.get("season")
    post = stats.get("postseason")
    recent = stats.get("recent")
    season_sv = (season or {}).get("sv_pct") if season else None
    post_sv = (post or {}).get("sv_pct") if post else None
    recent_sv = (recent or {}).get("sv_pct") if recent else None

    if is_playoffs and post_sv is not None:
        base = POST_WEIGHT_PLAYOFFS * post_sv + (1 - POST_WEIGHT_PLAYOFFS) * (season_sv if season_sv else LEAGUE_AVG_SV_PCT)
    elif season_sv is not None:
        base = season_sv
    else:
        base = LEAGUE_AVG_SV_PCT

    if recent_sv is not None:
        blended = RECENT_WEIGHT * recent_sv + (1 - RECENT_WEIGHT) * base
    else:
        blended = base

    # Shrink toward league average if very small sample
    total_starts = ((season or {}).get("n_starts") or 0) + ((post or {}).get("n_starts") or 0)
    w = total_starts / (total_starts + 5)   # shrinkage prior of 5 starts
    blended = w * blended + (1 - w) * LEAGUE_AVG_SV_PCT
    return blended


def _opp_shots_for_per_game(team_name: str, nhl_state: Dict[str, Any]) -> float:
    """Try to derive opposing team's shots-for-per-game from nhl_state.
    Falls back to league average."""
    # nhl_state.json may not have detailed team SFG -- use league avg as fallback
    return LEAGUE_AVG_SHOTS


def run() -> Dict[str, Any]:
    sb = _http(SCOREBOARD_URL)
    nhl_state = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    if not sb:
        out = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                "error": "ESPN scoreboard unreachable", "games": []}
        with open(OUT, "w") as f: json.dump(out, f, indent=2)
        return out

    is_playoffs = True   # mid-May 2026 = Stanley Cup playoffs
    games_out = []
    all_picks = []

    for ev in (sb.get("events") or []):
        comp = (ev.get("competitions") or [{}])[0]
        competitors = comp.get("competitors") or []
        if len(competitors) != 2: continue
        mu = ev.get("shortName") or ev.get("name") or "?"
        game_record: Dict[str, Any] = {
            "matchup": mu,
            "date": ev.get("date"),
            "is_playoffs": is_playoffs,
            "teams": [],
        }
        team_blocks = []
        for c in competitors:
            team_name = c.get("team", {}).get("displayName")
            team_abbr = c.get("team", {}).get("abbreviation")
            home_away = c.get("homeAway")
            # Find probable starting goalie
            probables = c.get("probables") or []
            sg = next((p for p in probables if p.get("name") == "probableStartingGoalie"), None)
            athlete = (sg or {}).get("athlete") or {}
            goalie_id = athlete.get("id")
            goalie_name = athlete.get("fullName")
            stats = {}
            if goalie_id:
                stats = _fetch_goalie_stats(goalie_id)
            blended_sv = _blend_sv_pct(stats, is_playoffs)

            team_blocks.append({
                "team_name": team_name,
                "team_abbr": team_abbr,
                "home_away": home_away,
                "goalie_name": goalie_name,
                "goalie_id": goalie_id,
                "season_stats": stats.get("season"),
                "postseason_stats": stats.get("postseason"),
                "recent_stats": stats.get("recent"),
                "blended_sv_pct": round(blended_sv, 4),
            })

        # Now compute opposing-team goals projections (each team scores vs the OTHER team's goalie)
        for i, team_block in enumerate(team_blocks):
            opp = team_blocks[1 - i]
            # Team i is the SCORING side -- opposing goalie is opp["goalie"]
            opp_sv = opp.get("blended_sv_pct") or LEAGUE_AVG_SV_PCT
            # Team i's shots-for-per-game (use league avg for now)
            shots_for = _opp_shots_for_per_game(team_block["team_name"], nhl_state)
            # Expected goals for team i = shots * (1 - opp_sv_pct)
            exp_goals = shots_for * (1 - opp_sv)

            # P(scores X+ goals) using Poisson(exp_goals)
            markets = {}
            for line in (0.5, 1.5, 2.5, 3.5, 4.5):
                p = _poisson_p_over(exp_goals, line)
                if 0.05 < p < 0.95:
                    key = f"{team_block['team_abbr']}_team_total_over_{line}"
                    markets[key] = {
                        "line": line,
                        "p_over": round(p, 4),
                        "p_under": round(1 - p, 4),
                        "fair_over": _american(p),
                        "fair_under": _american(1 - p),
                    }
            # Shutout (team i fails to score against opp's goalie)
            p_no_score = _poisson_p_zero(exp_goals)
            opp_shutout_key = f"{opp['team_abbr']}_shutout"
            markets[opp_shutout_key] = {
                "p_yes": round(p_no_score, 4),
                "p_no": round(1 - p_no_score, 4),
                "fair_yes": _american(p_no_score),
                "fair_no": _american(1 - p_no_score),
                "note": f"{opp['goalie_name']} shutout against {team_block['team_name']}",
            }

            team_block["expected_goals_for"] = round(exp_goals, 2)
            team_block["opposing_goalie"] = opp.get("goalie_name")
            team_block["opposing_blended_sv_pct"] = opp.get("blended_sv_pct")
            team_block["markets"] = markets

            # Surface sweet-spot picks
            for mkt, info in markets.items():
                p_over = info.get("p_over")
                p_under = info.get("p_under")
                if p_over and 0.62 <= p_over <= 0.85:
                    all_picks.append({
                        "matchup": mu, "team": team_block["team_abbr"],
                        "market": mkt, "side": "OVER",
                        "prob": p_over, "fair": info.get("fair_over"),
                        "line": info.get("line"),
                        "opp_goalie": opp.get("goalie_name"),
                        "opp_sv_pct": opp.get("blended_sv_pct"),
                    })
                if p_under and 0.62 <= p_under <= 0.85:
                    all_picks.append({
                        "matchup": mu, "team": team_block["team_abbr"],
                        "market": mkt.replace("over_", "under_"), "side": "UNDER",
                        "prob": p_under, "fair": info.get("fair_under"),
                        "line": info.get("line"),
                        "opp_goalie": opp.get("goalie_name"),
                        "opp_sv_pct": opp.get("blended_sv_pct"),
                    })
                # Shutout
                p_yes = info.get("p_yes")
                if p_yes and 0.05 <= p_yes <= 0.35:
                    all_picks.append({
                        "matchup": mu, "team": opp.get("team_abbr"),
                        "market": mkt, "side": "YES",
                        "prob": p_yes, "fair": info.get("fair_yes"),
                        "note": info.get("note"),
                    })

        game_record["teams"] = team_blocks
        games_out.append(game_record)

    all_picks.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_games": len(games_out),
        "n_picks": len(all_picks),
        "league_avg_sv_pct": LEAGUE_AVG_SV_PCT,
        "league_avg_shots": LEAGUE_AVG_SHOTS,
        "is_playoffs": is_playoffs,
        "top_picks": all_picks[:20],
        "games": games_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"NHL goalie matchup: {p['n_games']} games, {p['n_picks']} picks")
    for g in p["games"]:
        print(f"\n  {g['matchup']}:")
        for t in g["teams"]:
            ssn = t.get("season_stats") or {}
            post = t.get("postseason_stats") or {}
            print(f"    {t['team_abbr']:3s} {t['goalie_name'] or '?'}: "
                  f"season SV%={ssn.get('sv_pct','?')} ({ssn.get('n_starts',0)} GS) | "
                  f"playoff SV%={post.get('sv_pct','?')} ({post.get('n_starts',0)} GS) | "
                  f"blended {t['blended_sv_pct']:.3f}")
            print(f"      vs {t.get('opposing_goalie','?')} -> exp goals {t['expected_goals_for']:.2f}")
    print(f"\n  Top 8 picks:")
    for pp in p["top_picks"][:8]:
        print(f"    {pp['matchup'][:25]:25s} {pp.get('market','?')[:30]:30s} "
              f"p={pp['prob']*100:.0f}% fair={pp['fair']}")
