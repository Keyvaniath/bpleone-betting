"""
EdgeStat --matchup engine.

For each game in today's slate, build a deep "research digest":
  - Pitcher season stats vs. career baseline
  - Pitcher recent form (last 3 starts) vs. season
  - Pitcher vs. L / vs. R splits this season
  - Pitcher head-to-head vs. the opposing team this season (from game logs)
  - Team offense vs. league
  - Park factor + venue notes
  - Plain-English "narrative" string for each finding

Writes data/matchups.json --consumed by research.html.

Designed to run as part of the daily pipeline. ~5–15s for a full slate
(amortized by stats_repo's 6-hour cache).
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

import stats_repo as sr


OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "matchups.json")


def build_matchup(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Build one matchup digest from a pipeline _meta block."""
    home_tid = meta.get("home_team_id")
    away_tid = meta.get("away_team_id")
    home_pid = meta.get("home_pitcher_id")
    away_pid = meta.get("away_pitcher_id")

    return {
        "gamePk": meta.get("gamePk"),
        "venue": meta.get("venue"),
        "home": _team_block(home_tid),
        "away": _team_block(away_tid),
        "home_pitcher": _pitcher_block(home_pid, meta.get("home_pitcher_name"), opp_team_id=away_tid),
        "away_pitcher": _pitcher_block(away_pid, meta.get("away_pitcher_name"), opp_team_id=home_tid),
    }


def _team_block(tid: Optional[int]) -> Dict[str, Any]:
    if not tid:
        return {}
    s = sr.team_season_stats(tid)
    if not s:
        return {"team_id": tid}
    return {
        "team_id": tid,
        "ops": round(s.get("h_ops", 0), 3) if s.get("h_ops") else None,
        "obp": round(s.get("h_obp", 0), 3) if s.get("h_obp") else None,
        "slg": round(s.get("h_slg", 0), 3) if s.get("h_slg") else None,
        "runs": s.get("h_runs"),
        "team_era": s.get("p_era"),
        "team_whip": s.get("p_whip"),
        "offensive_index": sr.team_offensive_index(tid),
        "bullpen_delta": sr.team_bullpen_delta(tid),
    }


def _pitcher_block(pid: Optional[int], name: Optional[str], opp_team_id: Optional[int]) -> Dict[str, Any]:
    if not pid:
        return {"name": name or "TBD", "id": None, "starts_this_season": 0}
    season = sr.pitcher_season(pid)
    career = sr.pitcher_career(pid)
    splits = sr.pitcher_splits(pid)
    recent = sr.pitcher_recent_form(pid, n=3)
    hand = sr.pitcher_hand(pid)
    vs_team = sr.pitcher_vs_team(pid, opp_team_id) if opp_team_id else {"starts": 0}

    return {
        "id": pid,
        "name": name,
        "hand": hand,
        "season": _line(season),
        "career": _line(career),
        "splits": {
            "vsL": _line(splits.get("vsL", {})),
            "vsR": _line(splits.get("vsR", {})),
        },
        "recent": recent,
        "vs_opp_this_season": vs_team,
        "narrative": _narrative(name, hand, season, career, recent, splits, vs_team),
    }


def _line(s: Dict[str, Any]) -> Dict[str, Any]:
    """Compact one-row stat line."""
    if not s:
        return {}
    return {
        "ip": s.get("inningsPitched"),
        "era": s.get("era"),
        "whip": s.get("whip"),
        "k9": s.get("strikeoutsPer9Inn"),
        "bb9": s.get("walksPer9Inn"),
        "hr9": s.get("homeRunsPer9"),
        "baa": s.get("avg"),
        "starts": s.get("gamesStarted"),
        "fip": _fip(s),
    }


def _fip(s: Dict[str, Any]) -> Optional[float]:
    ip = s.get("inningsPitched")
    if not ip:
        return None
    try:
        ip = float(ip)
        hr = float(s.get("homeRuns", 0) or 0)
        bb = float(s.get("baseOnBalls", 0) or 0)
        k = float(s.get("strikeOuts", 0) or 0)
        return round((13 * hr + 3 * bb - 2 * k) / ip + 3.10, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _narrative(name: Optional[str], hand: str,
               season: Dict[str, Any], career: Dict[str, Any],
               recent: Dict[str, Any], splits: Dict[str, Dict[str, Any]],
               vs_team: Dict[str, Any]) -> List[str]:
    """Auto-generated plain-English findings. Each entry is one notable fact."""
    out: List[str] = []
    name = name or "Pitcher"

    # 1. Season vs career drift
    if season and career:
        s_era = season.get("era"); c_era = career.get("era")
        if s_era and c_era and abs(s_era - c_era) >= 0.50:
            direction = "above" if s_era > c_era else "below"
            out.append(f"{name}'s 2026 ERA ({s_era:.2f}) is {abs(s_era - c_era):.2f} runs {direction} his career mark ({c_era:.2f}).")
        s_k9 = season.get("strikeoutsPer9Inn"); c_k9 = career.get("strikeoutsPer9Inn")
        if s_k9 and c_k9 and abs(s_k9 - c_k9) >= 1.5:
            direction = "up" if s_k9 > c_k9 else "down"
            out.append(f"K/9 is {direction} {abs(s_k9 - c_k9):.1f} from career baseline ({s_k9:.1f} vs {c_k9:.1f}).")

    # 2. Recent form vs season
    if recent and season:
        r_era = recent.get("era"); s_era = season.get("era")
        if r_era is not None and s_era and r_era < s_era * 0.6 and recent.get("starts", 0) >= 2:
            out.append(f"Hot streak: last {recent['starts']} starts ERA {r_era:.2f} --dominating relative to {s_era:.2f} season mark.")
        elif r_era is not None and s_era and r_era > s_era * 1.6 and recent.get("starts", 0) >= 2:
            out.append(f"Slump: last {recent['starts']} starts ERA {r_era:.2f} --well off his {s_era:.2f} season pace.")

    # 3. Platoon splits
    vl = splits.get("vsL", {}) or {}
    vr = splits.get("vsR", {}) or {}
    if vl and vr:
        vl_ops = vl.get("ops"); vr_ops = vr.get("ops")
        if vl_ops and vr_ops and abs(vl_ops - vr_ops) >= 0.150:
            weak = "lefties" if vl_ops > vr_ops else "righties"
            strong = "righties" if vl_ops > vr_ops else "lefties"
            out.append(f"Big platoon split: opponents OPS {vl_ops:.3f} vs L / {vr_ops:.3f} vs R --{weak} hit him hard.")

    # 4. Head-to-head vs this opponent
    if vs_team.get("starts", 0) >= 2 and vs_team.get("ip", 0) >= 5:
        era = vs_team.get("era")
        if era is not None:
            verdict = "owned by them" if era >= 5.0 else "owns them" if era <= 2.5 else "has been competent against them"
            out.append(f"H2H this season: {vs_team['starts']} starts, {vs_team['ip']} IP, {era:.2f} ERA --{verdict}.")
    elif vs_team.get("starts", 0) == 1:
        st = vs_team
        out.append(f"Has faced this lineup once in 2026: {st.get('ip')} IP, {st.get('er')} ER, {st.get('k')}K / {st.get('bb')}BB.")

    return out


def build_all_matchups(today_json_path: Optional[str] = None) -> Dict[str, Any]:
    """Read today.json (or fall back to pipeline.build_slate), produce matchups.json."""
    # Prefer reading today.json so we don't re-fetch the schedule.
    today_path = today_json_path or os.path.join(os.path.dirname(__file__), "..", "data", "today.json")
    games: List[Dict[str, Any]] = []
    if os.path.exists(today_path):
        try:
            with open(today_path) as f:
                today = json.load(f)
            games = today.get("games", [])
        except Exception:
            games = []

    # But today.json doesn't carry _meta --we need to re-build the slate to get IDs.
    from pipeline import build_real_slate
    slate = build_real_slate() or []

    matchups = []
    for game in slate:
        meta = game.get("_meta", {})
        if not meta:
            continue
        m = build_matchup(meta)
        m["matchup"] = f"{game['away']['code']} @ {game['home']['code']}"
        m["time"] = game.get("time")
        m["park"] = game.get("park")
        m["market"] = {
            "ml_home": game.get("market_ml_home"),
            "ml_away": game.get("market_ml_away"),
            "total": game.get("market_total"),
        }
        matchups.append(m)

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "games": matchups,
    }
    return payload


def write_matchups(payload: Dict[str, Any], path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote matchups -> {path}")
    print(f"  Games: {len(payload['games'])}")
    total_findings = sum(
        len(g["home_pitcher"].get("narrative", [])) + len(g["away_pitcher"].get("narrative", []))
        for g in payload["games"]
    )
    print(f"  Auto-findings: {total_findings}")


if __name__ == "__main__":
    payload = build_all_matchups()
    write_matchups(payload)
    if payload["games"]:
        # Print first game's full digest for sanity
        print(json.dumps(payload["games"][0], indent=2)[:1500])
