"""
EdgeStat -- prop rationale generator.

For each prop in props.json + pickem.json, generates a plain-English
"why this play" summary explaining what drove the model's projection.
Reads season stats, Statcast metrics, opponent context, recent form.

Writes data/rationales.json:
  {
    "by_key": {
      "{player_id}_{market}_{line}": {
        "player": "Aaron Nola",
        "market": "pitcher_strikeouts",
        "line": 5.5,
        "headline": "Model says OVER 5.5 at 64% (+8% edge)",
        "drivers": [
          "Season K/9 of 10.13 well above 8.6 league avg",
          "Last 3 starts: avg 6.3 Ks per start vs 5.5 line",
          "TOR lineup whiffs at 24% — third-highest K% on slate",
          "Statcast K% 28.4% blended with season trend"
        ],
        "caveats": [
          "Only 13.1 IP this season -- thin sample",
          "Calibration loop applied 0.85x correction (model has been overconfident)"
        ],
        "verdict": "OVER 5.5 -- model probability 64%, edge after correction +8.2%"
      }
    }
  }

Frontend props.html + pickem.html read this to show a "Why" expandable
panel under each prop row.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
INJURIES_PATH = os.path.join(DATA_DIR, "injuries_live.json")
OUT_PATH = os.path.join(DATA_DIR, "rationales.json")
CAL_PATH = os.path.join(DATA_DIR, "calibration_live.json")

# Built once per run() call: { batter_team_code: {opp_pitcher_id, opp_team_id, venue, batter_pitcher_hand} }
GAME_CTX: Dict[str, Dict[str, Any]] = {}
INJURY_INDEX: Dict[int, Dict[str, Any]] = {}


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _key(pid: Any, market: str, line: float) -> str:
    return f"{pid}_{market}_{line}"


def _format_pct(p: Optional[float]) -> str:
    return f"{p * 100:.1f}%" if p is not None else "?"


def _drivers_for_pitcher_ks(pid: int, line: float, prob_over: Optional[float]) -> Dict[str, Any]:
    drivers, caveats = [], []
    season = sr.pitcher_season(pid) or {}
    ip = float(season.get("inningsPitched") or 0)
    k9 = float(season.get("strikeoutsPer9Inn") or 0)
    starts = int(season.get("gamesStarted") or 0)
    if k9:
        if k9 > 9.5:
            drivers.append(f"Season K/9 of {k9:.2f} well above 8.6 league avg -- strong K profile")
        elif k9 > 8:
            drivers.append(f"Season K/9 of {k9:.2f} slightly above league avg")
        else:
            drivers.append(f"Season K/9 of {k9:.2f} below league avg ({8.6:.1f})")
    if ip and starts:
        avg_ip = ip / starts
        drivers.append(f"Averaging {avg_ip:.1f} IP per start over {starts} starts -- expected workload")
    # Statcast
    try:
        import statcast as sc
        sb = sc.pitcher_stats(pid) or {}
        k_pct = sb.get("k_percent")
        whiff = sb.get("whiff_percent")
        if k_pct:
            whiff_str = f" (whiff% {whiff:.1f}%)" if whiff is not None else ""
            drivers.append(f"Statcast K% {k_pct:.1f}%{whiff_str} -- predicts K rate better than K/9 alone")
    except Exception:
        pass
    # Recent form
    try:
        form = sr.pitcher_recent_form(pid, n=3) or {}
        rec_k = form.get("avg_k")
        if rec_k is not None:
            if rec_k > line:
                drivers.append(f"Last 3 starts: averaging {rec_k:.1f} Ks per start (vs line {line})")
            else:
                drivers.append(f"Last 3 starts: averaging {rec_k:.1f} Ks per start (below line {line})")
    except Exception:
        pass
    # Pitcher platoon split: vs L / vs R
    try:
        splits = sr.pitcher_splits(pid) or {}
        vsl = splits.get("vsL") or splits.get("vsLeft") or {}
        vsr = splits.get("vsR") or splits.get("vsRight") or {}
        if vsl.get("avg") or vsr.get("avg"):
            l_avg = vsl.get("avg")
            r_avg = vsr.get("avg")
            if l_avg and r_avg:
                drivers.append(f"Splits: vs L .{int(float(l_avg)*1000):03d} / vs R .{int(float(r_avg)*1000):03d} -- "
                               + ("strong reverse split" if float(l_avg) < float(r_avg) - 0.030 else
                                  "normal R-bias" if float(r_avg) < float(l_avg) - 0.030 else
                                  "balanced"))
    except Exception:
        pass
    # Caveats
    if ip < 30:
        caveats.append(f"Only {ip:.1f} IP this season -- thin sample, projection has noise")
    if starts < 5:
        caveats.append(f"Only {starts} starts -- bias may be miscalibrated for this pitcher")
    return {"drivers": drivers, "caveats": caveats}


def _matchup_context(player: Dict[str, Any]) -> Dict[str, Any]:
    """Look up the opp pitcher / venue / order for a batter prop via GAME_CTX.

    GAME_CTX is keyed by team code (e.g., "PHI"). The player dict carries
    `team` from Bovada (e.g., "PHI"). Returns {opp_pitcher_id, opp_pitcher_name,
    venue, pitcher_hand} or {} if not found.
    """
    team = (player.get("team") or "").upper()
    if not team or team not in GAME_CTX:
        return {}
    return GAME_CTX[team]


def _drivers_for_matchup(bid: int, ctx: Dict[str, Any], market: str) -> List[str]:
    """BvP H2H + arsenal-vs-batter signals -- the player-matchup drivers
    that sharp prop bettors live on."""
    drivers: List[str] = []
    opp_pid = ctx.get("opp_pitcher_id")
    opp_name = ctx.get("opp_pitcher_name")
    if not opp_pid or not bid:
        return drivers

    # BvP career H2H
    try:
        h2h = sr.pitcher_vs_batter(opp_pid, bid) or {}
        ab = h2h.get("ab", 0)
        if ab >= 3:
            avg = h2h.get("avg") or "?"
            ops = h2h.get("ops") or "?"
            hits = h2h.get("hits", 0)
            hr = h2h.get("hr", 0)
            so = h2h.get("so", 0)
            line = f"Career vs {opp_name}: {hits}-for-{ab}"
            if hr: line += f", {hr} HR"
            if so >= 2: line += f", {so} K"
            line += f" (.{avg.replace('0.','') if isinstance(avg, str) else int(avg*1000):03d} avg / .{ops.replace('0.','') if isinstance(ops, str) else int(ops*1000):03d} OPS)" if avg != "?" else ""
            drivers.append(line)
    except Exception:
        pass

    # Arsenal matchup (Statcast pitch-mix vs batter pitch-type strength)
    if market in ("batter_hits", "batter_total_bases", "batter_home_runs",
                   "batter_singles", "batter_doubles"):
        try:
            import statcast as sc
            ars = sc.pitcher_arsenal(opp_pid)
            bvp = sc.batter_vs_pitch(bid)
            if ars and bvp:
                mu = sc.matchup_xwoba(ars, bvp) or {}
                w = mu.get("matchup_xwoba")
                if w is not None:
                    league = 0.320
                    delta = w - league
                    flav = ("ELITE matchup" if delta > 0.05 else
                            "strong matchup" if delta > 0.02 else
                            "neutral matchup" if abs(delta) <= 0.02 else
                            "tough matchup" if delta > -0.05 else
                            "BRUTAL matchup")
                    drivers.append(
                        f"Statcast arsenal matchup xwOBA {w:.3f} vs league .320 ({flav})"
                    )
                    # Surface the biggest pitch-type edge
                    bkd = mu.get("breakdown") or []
                    if bkd:
                        # Pitch with highest batter xwOBA weighted by usage
                        best = max(bkd, key=lambda r: (r.get("pitcher_usage_pct") or 0)
                                   * ((r.get("batter_xwoba_vs") or 0) - league))
                        if (best.get("pitcher_usage_pct") or 0) >= 10:
                            pname = best.get("pitch_name") or best.get("pitch_type") or "primary pitch"
                            drivers.append(
                                f"Faces {pname} ({best.get('pitcher_usage_pct'):.0f}% of arsenal) -- batter slugs xwOBA {best.get('batter_xwoba_vs'):.3f} vs that pitch"
                            )
        except Exception:
            pass

    return drivers


def _drivers_for_batter(pid: int, market: str, line: float, prob_over: Optional[float],
                        player: Optional[Dict[str, Any]], season_field: str, label: str) -> Dict[str, Any]:
    drivers, caveats = [], []
    # Stats from people endpoint (uncached batter season)
    try:
        import requests
        sched_year = dt.date.today().year
        url = f"https://statsapi.mlb.com/api/v1/people/{pid}/stats"
        season = (requests.get(url, params={"stats":"season","group":"hitting","season":sched_year}, timeout=8)
                  .json().get("stats", [{}])[0].get("splits", [{}])[0].get("stat") or {})
    except Exception:
        season = {}
    if season:
        pa = int(season.get("plateAppearances") or 0)
        val = season.get(season_field)
        if val is not None and pa:
            per_g = float(val) / max(1, int(season.get("gamesPlayed") or 1))
            drivers.append(f"Season {label}: {val} in {pa} PA ({per_g:.2f} per game)")
        if 0 < pa < 80:
            caveats.append(f"Only {pa} PA -- small sample, projection uncertain")
    # Statcast
    try:
        import statcast as sc
        sb = sc.batter_stats(pid) or {}
        xba = sb.get("xba")
        xslg = sb.get("xslg")
        barrel = sb.get("barrel_batted_rate")
        if xslg is not None and market == "batter_total_bases":
            drivers.append(f"Statcast xSLG {xslg:.3f} -- predicts TB rate independent of luck")
        if xba is not None and market == "batter_hits":
            drivers.append(f"Statcast xBA {xba:.3f} -- expected hit rate vs league avg ~.250")
        if barrel and market == "batter_home_runs":
            drivers.append(f"Barrel% {barrel:.1f}% -- {('elite' if barrel > 12 else 'above-avg' if barrel > 8 else 'avg')} contact quality")
    except Exception:
        pass

    # Matchup drivers: BvP H2H + arsenal-vs-batter xwOBA + park
    ctx = _matchup_context(player or {})
    drivers.extend(_drivers_for_matchup(pid, ctx, market))
    if ctx.get("park_factor") is not None and ctx["park_factor"] != 1.0:
        pf = ctx["park_factor"]
        if pf > 1.10:
            drivers.append(f"Park: {ctx.get('venue','?')} (factor {pf:.2f}, hitter-friendly -- boosts {label})")
        elif pf < 0.90:
            drivers.append(f"Park: {ctx.get('venue','?')} (factor {pf:.2f}, pitcher-friendly -- suppresses {label})")
        else:
            drivers.append(f"Park: {ctx.get('venue','?')} (factor {pf:.2f}, neutral)")
    # Lineup order
    if ctx.get("batting_order"):
        ord_ = ctx["batting_order"]
        order_note = ("top-of-order -- more PAs expected" if ord_ <= 2
                      else "middle of order -- RBI/run leverage" if ord_ <= 5
                      else "bottom of order -- fewer PAs")
        drivers.append(f"Batting #{ord_} ({order_note})")
    # Injury awareness
    inj = INJURY_INDEX.get(pid)
    if inj:
        caveats.append(f"INJURY: {inj.get('status', 'flagged')} -- {inj.get('description', 'see injuries page')}")

    # Lineup confirmation gate signal (passed through from props.json if present)
    ls = (player or {}).get("lineup_status")
    if ls == "pending":
        caveats.append("Lineup not yet posted -- ~10% scratch risk; treat projection as conditional")
    elif ls == "scratched":
        caveats.append("NOT IN POSTED LINEUP -- skip; player is scratched today")
    elif ls == "confirmed":
        drivers.append("Lineup CONFIRMED -- starting today, no scratch risk")

    return {"drivers": drivers, "caveats": caveats}


MARKET_LABELS = {
    "pitcher_strikeouts": "K",
    "batter_total_bases": "TB",
    "batter_hits": "hit",
    "batter_home_runs": "HR",
    "batter_runs_scored": "R",
    "batter_rbis": "RBI",
    "batter_singles": "1B",
    "batter_doubles": "2B",
}


def build_rationale(p: Dict[str, Any], corrections: Dict[str, float]) -> Optional[Dict[str, Any]]:
    pid = p.get("player_id")
    market = p.get("market")
    line = p.get("line") if "line" in p else p.get("pp_line")
    player = p.get("player")
    prob_over = p.get("model_prob_over")
    if pid is None or market is None or line is None:
        return None
    if market == "pitcher_strikeouts":
        d = _drivers_for_pitcher_ks(pid, line, prob_over)
    elif market == "batter_hits":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "hits", "hits")
    elif market == "batter_total_bases":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "totalBases", "total bases")
    elif market == "batter_home_runs":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "homeRuns", "HRs")
    elif market == "batter_runs_scored":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "runs", "runs")
    elif market == "batter_rbis":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "rbi", "RBIs")
    elif market == "batter_doubles":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "doubles", "doubles")
    elif market == "batter_singles":
        d = _drivers_for_batter(pid, market, line, prob_over, p, "hits", "singles")
    else:
        d = {"drivers": [], "caveats": []}

    # Calibration disclaimer
    cf = corrections.get(market)
    if cf is not None and abs(cf - 1) > 0.001:
        d["caveats"].append(
            f"Calibration applied {cf:.3f}x correction "
            f"({'shrink' if cf < 1 else 'boost'} OVER by {abs((cf-1)*100):.1f}%) "
            f"because the model has been {'over' if cf < 1 else 'under'}-confident on this market"
        )

    # Verdict
    label = MARKET_LABELS.get(market, market.replace("_", " "))
    play = p.get("play") or ("OVER" if (prob_over or 0) >= 0.5 else "UNDER")
    edge = p.get("best_edge_pct") or p.get("edge_pct")
    edge_str = f"+{edge:.1f}%" if isinstance(edge, (int, float)) else "(no real-line edge)"
    verdict = (f"{play} {line} {label} -- model probability "
               f"{_format_pct(prob_over if play == 'OVER' else 1 - prob_over)}, edge {edge_str}")

    return {
        "player": player,
        "player_id": pid,
        "market": market,
        "line": line,
        "play": play,
        "model_prob_over": prob_over,
        "headline": f"Model leans {play} on {player} {label} {line}",
        "drivers": d["drivers"],
        "caveats": d["caveats"],
        "verdict": verdict,
    }


def _build_game_ctx() -> Dict[str, Dict[str, Any]]:
    """Pull today's MLB schedule with probable pitchers; build a
    {team_code: {opp_pitcher_id, opp_pitcher_name, opp_team_id, venue,
    park_factor}} index so each batter prop knows its matchup.

    Hits MLB Stats API directly (cached schedule via stats_repo). today.json
    strips pitcher IDs in the snapshot, so we can't read from there.
    """
    out: Dict[str, Dict[str, Any]] = {}
    try:
        from pipeline import PARK_FACTORS, TEAM_CODE
    except Exception:
        PARK_FACTORS, TEAM_CODE = {}, {}

    import datetime as _dt
    import requests
    try:
        sched = requests.get(
            "https://statsapi.mlb.com/api/v1/schedule",
            params={"sportId": 1, "date": _dt.date.today().isoformat(),
                    "hydrate": "probablePitcher"},
            timeout=10,
        ).json()
    except Exception:
        return out

    for date_block in sched.get("dates", []):
        for g in date_block.get("games", []):
            try:
                home_name = g["teams"]["home"]["team"]["name"]
                away_name = g["teams"]["away"]["team"]["name"]
                home_code = TEAM_CODE.get(home_name, home_name[:3].upper())
                away_code = TEAM_CODE.get(away_name, away_name[:3].upper())
                home_pid = (g["teams"]["home"].get("probablePitcher") or {}).get("id")
                home_pname = (g["teams"]["home"].get("probablePitcher") or {}).get("fullName")
                away_pid = (g["teams"]["away"].get("probablePitcher") or {}).get("id")
                away_pname = (g["teams"]["away"].get("probablePitcher") or {}).get("fullName")
                home_tid = g["teams"]["home"]["team"]["id"]
                away_tid = g["teams"]["away"]["team"]["id"]
                venue = (g.get("venue") or {}).get("name") or ""
                pf = PARK_FACTORS.get(venue, 1.00)
                out[away_code] = {
                    "opp_pitcher_id": home_pid, "opp_pitcher_name": home_pname,
                    "opp_team_id": home_tid, "venue": venue, "park_factor": pf,
                }
                out[home_code] = {
                    "opp_pitcher_id": away_pid, "opp_pitcher_name": away_pname,
                    "opp_team_id": away_tid, "venue": venue, "park_factor": pf,
                }
            except Exception:
                continue
    return out


def _build_injury_index() -> Dict[int, Dict[str, Any]]:
    """From injuries_live.json, build {player_id: {status, description}}.

    Schema: { teams: { team_name: { players: [{player_id, status, description, ...}] } } }
    """
    inj = _load(INJURIES_PATH)
    out: Dict[int, Dict[str, Any]] = {}
    teams = inj.get("teams") or {}
    if isinstance(teams, dict):
        for team_name, td in teams.items():
            for p in (td.get("players") or []):
                pid = p.get("player_id") or p.get("id")
                if pid:
                    out[int(pid)] = {
                        "status": p.get("status") or p.get("injury_status") or "IL",
                        "description": p.get("description") or p.get("note") or "",
                    }
    return out


def run() -> Dict[str, Any]:
    global GAME_CTX, INJURY_INDEX
    GAME_CTX = _build_game_ctx()
    INJURY_INDEX = _build_injury_index()
    cal = _load(CAL_PATH)
    corrections = {k: v.get("correction_factor", 1.0)
                   for k, v in (cal.get("markets") or {}).items()}

    by_key: Dict[str, Dict[str, Any]] = {}

    # Each prop costs a few HTTP calls (season stats, statcast cache, recent form),
    # so cap how many we materialize per source. Frontend uses lazy-keyed lookups
    # so a missing rationale is fine -- just shows "no rationale" instead.
    MAX_PROPS_RATIONALE = 300
    MAX_PICKEM_RATIONALE = 200

    # Props.json (DraftKings primary OR Bovada fallback) -- prioritized
    props = _load(PROPS_PATH)
    props_sorted = sorted(props.get("top_edges", []),
                          key=lambda r: r.get("best_edge_pct") or 0, reverse=True)
    for p in props_sorted[:MAX_PROPS_RATIONALE]:
        r = build_rationale(p, corrections)
        if r:
            by_key[_key(r["player_id"], r["market"], r["line"])] = r

    # Pickem.json -- adds top-confidence PrizePicks props not already in DK
    pickem = _load(PICKEM_PATH)
    pe_sorted = sorted(pickem.get("props", []),
                       key=lambda r: max(r.get("model_prob_over", 0) or 0,
                                          r.get("model_prob_under", 0) or 0), reverse=True)
    added = 0
    for p in pe_sorted:
        if added >= MAX_PICKEM_RATIONALE:
            break
        p2 = dict(p)
        p2["line"] = p.get("pp_line")
        if p2.get("player_id") is None:
            continue
        k = _key(p2["player_id"], p2["market"], p2["line"])
        if k in by_key:
            continue
        r = build_rationale(p2, corrections)
        if r:
            by_key[k] = r
            added += 1

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "count": len(by_key),
        "by_key": by_key,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}: {p['count']} rationales")
    # Sample 3
    for k, r in list(p["by_key"].items())[:3]:
        print()
        print(f"  {r['headline']}")
        for d in r["drivers"]:
            print(f"    + {d}")
        for c in r["caveats"]:
            print(f"    ! {c}")
        print(f"    -> {r['verdict']}")
