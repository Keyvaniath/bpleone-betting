"""
EdgeStat -- LIVE data accuracy + freshness checker.

The "is my data actually live?" audit. For every key sport/feed:
  - hits the upstream source DIRECTLY (MLB API, ESPN, etc.)
  - compares to what's in our local data/*.json
  - flags any artifact where local count != upstream count, or where local
    is missing a game upstream has, or where local data is stub/empty when
    upstream has games.

This is the "Brandon's gone for hours, is the data actually live" check.
Writes data/data_health.json with per-feed status + per-artifact verdict.

The audit covers stub/quota issues that the existing pipeline_audit misses:
  - props.json says n=0 (does upstream Odds API have player props available?)
  - live_state.json says no games (are MLB games actually in progress now?)
  - NBA/NHL state says n=1 (is that right or did ESPN return more?)

Output: data/data_health.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
import urllib.error
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "data_health.json")


def _http(url, timeout=12):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EdgeStat/1.0", "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _load(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return None
    try:
        with open(p) as f: return json.load(f)
    except Exception: return None


def _age_min(name):
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p): return None
    return round((dt.datetime.now().timestamp() - os.path.getmtime(p)) / 60)


def _check_mlb():
    """Cross-check MLB schedule + live state.
    today.json includes only Pre-Game/Scheduled (pipeline.py filters In-Progress
    out), so we compare today.json against the PRE-GAME count, not total."""
    today = dt.date.today().isoformat()
    upstream = _http(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}")
    if not upstream:
        return {"feed": "mlb", "status": "red", "finding": "MLB API unreachable"}
    games = (upstream.get("dates") or [{}])[0].get("games", [])
    n_upstream_total = len(games)
    # In-progress: status code 'L' (Live)
    n_live = sum(1 for g in games if g.get("status", {}).get("abstractGameCode") == "L")
    # Final: status code 'F'
    n_final = sum(1 for g in games if g.get("status", {}).get("abstractGameCode") == "F")
    # Pre-game: status code 'P' (Preview)
    n_pregame = sum(1 for g in games if g.get("status", {}).get("abstractGameCode") == "P")

    local = _load("today.json") or {}
    local_games = local.get("games") or []
    n_local = len(local_games)

    live_state = _load("live_state.json") or {}
    n_local_live = live_state.get("games_in_progress", 0)

    findings = []
    status = "green"
    # today.json should match PRE-GAME count from upstream (since live games filtered out)
    # Allow tolerance of ±1 because games can flip status mid-poll
    if abs(n_local - n_pregame) > 1 and n_local < n_upstream_total:
        status = "yellow"
        findings.append(f"today.json count off: local={n_local} vs upstream pre-game={n_pregame} (total={n_upstream_total}, live={n_live}, final={n_final})")
    age = _age_min("live_state.json")
    if age is None: age = 999
    if n_live > 0 and (n_local_live == 0 or age > 30):
        status = "red"
        findings.append(f"MLB has {n_live} live games but live_state.json shows {n_local_live} (age {age}min)")
    if not findings:
        findings.append(f"{n_upstream_total} total ({n_pregame} pre / {n_live} live / {n_final} final), local pre={n_local}, live={n_local_live}")
    return {"feed": "mlb", "status": status, "findings": findings,
            "upstream_count": n_upstream_total, "upstream_pregame": n_pregame,
            "upstream_live": n_live, "upstream_final": n_final,
            "local_count": n_local, "local_live": n_local_live,
            "live_state_age_min": age}


def _check_espn(sport, espn_url, local_file):
    """Cross-check ESPN-driven sports."""
    up = _http(espn_url)
    if not up:
        return {"feed": sport, "status": "yellow", "findings": ["ESPN unreachable"]}
    events = up.get("events", [])
    n_up = len(events)
    n_up_live = sum(1 for e in events
                     if e.get("status", {}).get("type", {}).get("state") == "in")
    local = _load(local_file) or {}
    local_games = local.get("games") or []
    n_local = len(local_games)
    age = _age_min(local_file)
    if age is None: age = 999   # file missing → unknown age

    findings = []
    status = "green"
    if n_local != n_up:
        status = "red" if n_up > 0 else "yellow"
        findings.append(f"{sport.upper()} count mismatch: local={n_local} vs ESPN={n_up}")
    if n_up_live > 0 and age > 30:
        status = "red"
        findings.append(f"{sport.upper()} has {n_up_live} live, local age {age}min")
    if not findings:
        findings.append(f"{n_up} events matched ({n_up_live} live)")
    return {"feed": sport, "status": status, "findings": findings,
            "upstream_count": n_up, "local_count": n_local,
            "upstream_live": n_up_live, "local_age_min": age}


def _check_props():
    """Surface the Odds API quota / API key state HONESTLY.

    props.json is empty whenever player-prop book odds can't be fetched, but that
    is NOT automatically a red alarm. The usual cause is the paid Odds API key
    being quota-exhausted -- key valid, just no request budget -- a known, expected
    degraded state with a clear lever (raise the plan tier), not a broken feed. We
    defer to odds_key_preflight's persisted verdict (odds_key_status.json) so the
    canary reserves RED for a genuinely missing/unset key and uses YELLOW for the
    known quota degradation. A permanently-red canary masks real new failures.
    Game lines + model/calibration boards are unaffected (they need no paid key).
    """
    p = _load("props.json") or {}
    props = p.get("props") or []
    games = p.get("games") or []
    if props or games:
        return {"feed": "props", "status": "green",
                "findings": [f"{len(props)} props across {len(games)} games"],
                "n_props": len(props), "n_games": len(games)}
    # Empty props.json -> classify by the AUTHORITATIVE key state, not a guess.
    ks = _load("odds_key_status.json") or {}
    state = ks.get("state")
    headline = ks.get("headline")
    if state in ("exhausted", "low_quota"):
        status = "yellow"  # valid key, no request budget: degraded, not broken
        findings = [headline or "Odds key valid but quota exhausted -- player props dark until the plan tier is raised.",
                    "Game lines + model/calibration boards unaffected (they don't need the paid key)."]
    elif state == "active":
        status = "yellow"  # has budget but still empty -> a real, unexpected gap
        findings = ["Odds key ACTIVE (quota available) but props.json has 0 props -- check run_props_batch / upstream player-prop availability."]
    elif state == "dormant" or ks.get("key_set") is False:
        status = "red"  # genuine config problem: the secret is missing/unset
        findings = ["ODDS_API_KEY not set (preflight: dormant) -- the GitHub secret is missing/unset."]
    else:
        has_key_env = bool(os.environ.get("ODDS_API_KEY"))
        status = "red" if not has_key_env else "yellow"
        findings = ["props.json empty and odds_key_status.json unavailable.",
                    ("ODDS_API_KEY not set in env (locally) -- check the GitHub secret." if not has_key_env
                     else "Key present in env; props empty -- likely quota exhausted.")]
    return {"feed": "props", "status": status, "findings": findings,
            "n_props": len(props), "n_games": len(games), "odds_key_state": state}


def _check_pitcher_matchup():
    """Verify pitcher_matchup reflects today's PRE-GAME probables.
    Live/finished games are filtered out of mlb_pitcher_matchup.json by design
    (we don't project K-props for games already in progress), so we restrict
    upstream comparison to pre-game probables only."""
    today_iso = dt.date.today().isoformat()
    upstream = _http(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today_iso}&hydrate=probablePitcher")
    if not upstream:
        return {"feed": "pitcher_matchup", "status": "yellow", "findings": ["MLB API unreachable"]}
    games = (upstream.get("dates") or [{}])[0].get("games", [])
    upstream_pitchers = set()
    for g in games:
        # Only count pitchers from PRE-GAME games (matches today.json filter)
        status_code = (g.get("status") or {}).get("abstractGameCode")
        if status_code != "P": continue   # P = Preview (Pre-Game)
        for side in ("home", "away"):
            p = g.get("teams", {}).get(side, {}).get("probablePitcher", {})
            if p and p.get("fullName"):
                upstream_pitchers.add(p["fullName"])

    local = _load("mlb_pitcher_matchup.json") or {}
    matchups = local.get("matchups") or []
    local_pitchers = set()
    for m in matchups:
        for k in ("home_pitcher", "away_pitcher"):
            if m.get(k): local_pitchers.add(m[k])

    overlap = upstream_pitchers & local_pitchers
    missing = upstream_pitchers - local_pitchers
    findings = []
    status = "green"
    if not upstream_pitchers:
        findings.append("no pre-game probables upstream (all games live or final)")
    elif not local_pitchers:
        status = "red"
        findings.append("pitcher_matchup local has 0 pitchers")
    elif len(overlap) < len(upstream_pitchers) * 0.5:
        status = "yellow"
        findings.append(f"only {len(overlap)}/{len(upstream_pitchers)} pre-game probables in local")
    else:
        findings.append(f"{len(overlap)}/{len(upstream_pitchers)} pre-game probables matched")
    if missing and len(missing) > 0:
        findings.append(f"missing: {sorted(list(missing))[:3]}{'...' if len(missing)>3 else ''}")
    return {"feed": "pitcher_matchup", "status": status, "findings": findings,
            "upstream_count": len(upstream_pitchers), "local_count": len(local_pitchers),
            "matched": len(overlap)}


def _check_golf():
    """Golf - PGA tour active tournament?"""
    up = _http("https://site.api.espn.com/apis/site/v2/sports/golf/pga/scoreboard")
    if not up:
        return {"feed": "golf", "status": "yellow", "findings": ["ESPN PGA unreachable"]}
    events = up.get("events", [])
    n_up_players = 0
    n_active_tourneys = 0
    for ev in events:
        comps = ev.get("competitions", [{}])[0].get("competitors", [])
        n_up_players += len(comps)
        if ev.get("status", {}).get("type", {}).get("state") in ("pre", "in"):
            n_active_tourneys += 1
    local = _load("golf_state.json") or {}
    n_local = local.get("n_players", 0)
    age = _age_min("golf_state.json")
    if age is None: age = 999
    findings = []
    status = "green"
    if n_up_players > 0 and n_local == 0:
        status = "red"
        findings.append(f"ESPN has {n_up_players} golfers, local has 0")
    elif age > 60 and n_active_tourneys > 0:
        status = "yellow"
        findings.append(f"golf data {age}min stale during active tournament")
    else:
        findings.append(f"{n_local} golfers tracked ({n_active_tourneys} active events)")
    return {"feed": "golf", "status": status, "findings": findings,
            "upstream_players": n_up_players, "local_players": n_local,
            "local_age_min": age}


# Core artifacts that EVERY pipeline/heartbeat run regenerates regardless of season.
# If any is stale, the engine itself has gone dark (a cron failure) -- season-
# independent, so it won't false-alarm on off-season desks.
FRESHNESS_TARGETS = [
    ("today.json", 28), ("ledger_summary.json", 28), ("sport_coverage.json", 28),
    ("todays_top_plays.json", 28), ("alpha_pick_of_day.json", 30),
    ("alerts_feed.json", 10), ("calibration_map.json", 30), ("espn_odds.json", 14),
]


def _gen_age_h(d):
    g = (d or {}).get("generated_at") or (d or {}).get("updated_at")
    if not g:
        return None
    try:
        t = dt.datetime.fromisoformat(str(g).replace("Z", "").split("+")[0])
        return (dt.datetime.now() - t).total_seconds() / 3600
    except Exception:
        return None


def _check_freshness():
    """Catch silent cron failures: a core artifact that hasn't refreshed within its
    window means the producing pipeline has gone dark. This is the 'notice when a
    feed goes dark' monitor an official site needs."""
    stale = []
    ages = {}
    for fn, max_h in FRESHNESS_TARGETS:
        d = _load(fn)
        if d is None:
            stale.append(f"{fn}: MISSING")
            continue
        age = _gen_age_h(d)
        if age is None:
            age = (_age_min(fn) or 0) / 60.0
        ages[fn] = round(age, 1)
        if age > max_h:
            stale.append(f"{fn}: {age:.0f}h old (>{max_h}h)")
    status = "red" if stale else "green"
    findings = stale if stale else [f"{len(FRESHNESS_TARGETS)} core artifacts fresh"]
    return {"feed": "freshness", "status": status, "findings": findings,
            "n_stale": len(stale), "ages_h": ages}


# Per-DESK producers the per-sport checks above don't cover. Unlike the core artifacts
# these are SEASON-DEPENDENT: content legitimately empties off-season / between events,
# so we monitor ONLY whether the producer still runs (generated_at advancing) and cap
# the alarm at YELLOW -- a quiet desk is usually off-season, not breakage. Thresholds
# are generous so the normal 3x/day pipeline cadence never trips a false alarm.
DESK_FRESHNESS = [
    ("tennis_state.json", 18), ("ufc_state.json", 36), ("f1_state.json", 30),
    ("kbo_state.json", 18), ("cs_state.json", 18), ("cws_state.json", 36),
    ("worldcup_cards.json", 18),
]


def _check_desks():
    """Producer-liveness monitor for desks the per-sport checks don't cover. Catches a
    silently-dead desk feed (a pipeline step that stopped writing its artifact) without
    false-alarming on a legitimately-empty off-season desk -- it inspects generated_at
    age only, not content, and tops out at YELLOW."""
    stale, ages = [], {}
    for fn, max_h in DESK_FRESHNESS:
        d = _load(fn)
        if d is None:
            continue  # artifact absent -> desk may simply be off; not an error here
        age = _gen_age_h(d)
        if age is None:
            continue
        ages[fn] = round(age, 1)
        if age > max_h:
            stale.append(f"{fn}: {age:.0f}h old (>{max_h}h)")
    status = "yellow" if stale else "green"
    if stale:
        findings = stale + ["Desk producer(s) quiet -- likely off-season/between-events, "
                            "but verify the feed if unexpected."]
    else:
        findings = [f"{len(ages)} desk producers fresh"]
    return {"feed": "desks", "status": status, "findings": findings,
            "n_stale": len(stale), "ages_h": ages}


def run() -> Dict[str, Any]:
    checks = [
        _check_freshness(),
        _check_mlb(),
        _check_espn("nba", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard", "nba_state.json"),
        _check_espn("wnba", "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard", "wnba_state.json"),
        _check_espn("nhl", "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard", "nhl_state.json"),
        _check_espn("mls", "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard", "mls_state.json"),
        _check_espn("epl", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard", "epl_state.json"),
        _check_pitcher_matchup(),
        _check_props(),
        _check_golf(),
        _check_desks(),
    ]
    n_green = sum(1 for c in checks if c.get("status") == "green")
    n_yellow = sum(1 for c in checks if c.get("status") == "yellow")
    n_red = sum(1 for c in checks if c.get("status") == "red")
    overall = "red" if n_red else ("yellow" if n_yellow else "green")
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "n_green": n_green, "n_yellow": n_yellow, "n_red": n_red,
        "checks": checks,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Data health: {p['overall'].upper()} (g={p['n_green']} y={p['n_yellow']} r={p['n_red']})")
    for c in p["checks"]:
        emoji = "OK" if c["status"] == "green" else ("WARN" if c["status"] == "yellow" else "FAIL")
        print(f"  [{emoji}] {c['feed']:18} | {' | '.join(c.get('findings', []))}")
