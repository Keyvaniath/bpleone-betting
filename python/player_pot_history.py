"""
EdgeStat -- Player Play of the Day rolling history (LoL + CS + KBO).

Each cron snapshots player_pot.top_5 into a rolling record. Settlement is
sport-dependent:
  - LoL: settle when match completes (player kill/assist counts unknown
    without per-match stats API; mark as INFORMATIONAL after match settles)
  - CS: same -- INFORMATIONAL after match settles
  - KBO: settle when game completes (player box scores unknown; INFORMATIONAL)

In production, we'd add per-player stat capture from a paid stats API
(PandaScore Pro, OddsJam, etc.). For now this tracks predictions for
calibration purposes -- the loop is the prediction record itself.

Output: data/player_pot_history.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
POT_PATH = os.path.join(DATA_DIR, "player_pot.json")
HIST_PATH = os.path.join(DATA_DIR, "player_pot_history.json")


def _load(p):
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _payout_units(american) -> float:
    if american is None:
        return 0
    return american / 100 if american >= 0 else 100 / abs(american)


def _settle_lol(entry: Dict[str, Any], lol_state: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort settlement: if the player's team's match is completed,
    mark INFORMATIONAL (we can't verify the exact kill count). The match-level
    outcome is still recorded for the team-level analysis."""
    player = entry.get("player")
    team_code = entry.get("team")
    if not player or not team_code:
        return entry
    for m in (lol_state.get("all_matches") or []):
        if not m.get("is_completed"):
            continue
        if team_code in (m.get("team_a_code"), m.get("team_b_code")):
            # Player's team played a completed match
            won = m.get("winner") == (m.get("team_a") if team_code == m.get("team_a_code") else m.get("team_b"))
            entry.update({
                "settled": True,
                "outcome": "INFORMATIONAL",
                "team_won": won,
                "actual_match_score": f"{m.get('team_a_score','?')}-{m.get('team_b_score','?')}",
                "note": "Match settled but per-player stat-line unavailable in free API tier; team result recorded.",
            })
            return entry
    return entry


def _settle_cs(entry: Dict[str, Any], cs_state: Dict[str, Any]) -> Dict[str, Any]:
    team = entry.get("team")
    if not team:
        return entry
    for m in (cs_state.get("matches") or []):
        if not m.get("is_completed"):
            continue
        if team in (m.get("team_a"), m.get("team_b")):
            sa, sb = m.get("score_a") or 0, m.get("score_b") or 0
            if sa + sb == 0: return entry
            winner = m.get("team_a") if sa > sb else m.get("team_b")
            won = winner == team
            entry.update({
                "settled": True,
                "outcome": "INFORMATIONAL",
                "team_won": won,
                "actual_match_score": f"{sa}-{sb}",
                "note": "Match settled but per-player kills unavailable in free API tier; team result recorded.",
            })
            return entry
    return entry


def _settle_kbo(entry: Dict[str, Any], kbo_state: Dict[str, Any]) -> Dict[str, Any]:
    team = entry.get("team")
    if not team:
        return entry
    for m in (kbo_state.get("matches") or []):
        if m.get("state") != "post":
            continue
        if team in (m.get("home_team"), m.get("away_team")):
            sh, sa = m.get("home_score") or 0, m.get("away_score") or 0
            winner = m.get("home_team") if sh > sa else m.get("away_team")
            won = winner == team
            entry.update({
                "settled": True,
                "outcome": "INFORMATIONAL",
                "team_won": won,
                "actual_score": f"{sa}-{sh}",
                "note": "Game settled but per-player box-score unavailable in free tier; team result recorded.",
            })
            return entry
    return entry


def run() -> Dict[str, Any]:
    pot = _load(POT_PATH)
    hist = _load(HIST_PATH).get("history") or []
    today = dt.date.today().isoformat()

    # Snapshot top player picks (one per sport so we don't churn)
    top_by_sport = pot.get("top_by_sport") or {}
    for sport, pick in top_by_sport.items():
        key = (sport, pick.get("player"), pick.get("market"), pick.get("play"), pick.get("line"))
        already = any(
            (h.get("sport"), h.get("player"), h.get("market"), h.get("play"), h.get("line")) == key
            and not h.get("settled")
            for h in hist
        )
        if not already:
            hist.append({
                "date": today,
                "sport": sport,
                "player": pick.get("player"),
                "team": pick.get("team"),
                "league": pick.get("league"),
                "role": pick.get("role"),
                "market": pick.get("market"),
                "play": pick.get("play"),
                "line": pick.get("line"),
                "prob": pick.get("prob"),
                "fair_american": pick.get("fair_american"),
                "is_elite": pick.get("is_elite"),
                "quality_score": pick.get("quality_score"),
                "label": pick.get("label"),
                "settled": False,
                "outcome": "PENDING",
                "added_at": dt.datetime.now().isoformat(timespec="seconds"),
            })

    # Settlement passes
    lol_state = _load(os.path.join(DATA_DIR, "lol_state.json"))
    cs_state = _load(os.path.join(DATA_DIR, "cs_state.json"))
    kbo_state = _load(os.path.join(DATA_DIR, "kbo_state.json"))
    for i, e in enumerate(hist):
        if e.get("settled"):
            continue
        sport = e.get("sport")
        if sport == "LOL":
            hist[i] = _settle_lol(e, lol_state)
        elif sport == "CS":
            hist[i] = _settle_cs(e, cs_state)
        elif sport == "KBO":
            hist[i] = _settle_kbo(e, kbo_state)

    # Aggregates -- since outcomes are INFORMATIONAL (team-level only),
    # we track "team-side hit rate" as a proxy: did the player's team win?
    settled = [h for h in hist if h.get("settled")]
    team_wins = sum(1 for h in settled if h.get("team_won"))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "total_player_pots": len(hist),
        "n_settled": len(settled),
        "n_pending": len(hist) - len(settled),
        "team_side_wins": team_wins,
        "team_side_hit_rate": round(team_wins / len(settled), 4) if settled else None,
        "note": "Player props auto-settle as INFORMATIONAL since per-player stat-lines need a paid API tier. Team-side hit rate is the only firm settled metric.",
        "history": sorted(hist, key=lambda h: h.get("date", ""), reverse=True)[:100],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Player POT history: {p['total_player_pots']} total ({p['n_settled']} settled, {p['n_pending']} pending)")
    if p.get("team_side_hit_rate") is not None:
        print(f"  Team-side proxy hit rate: {(p['team_side_hit_rate'] or 0)*100:.1f}% (informational)")
