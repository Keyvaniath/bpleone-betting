"""
EdgeStat -- trap-bet detector.

Some props LOOK good but have hidden footguns. This module flags every
prop in best_bets where one of the following red flags applies:

  1. UMP K-MULT MISALIGNED: K prop OVER recommended but tonight's HP
     ump suppresses Ks (low K mult). Or K UNDER recommended with K-friendly ump.
  2. SHARP MONEY AGAINST: line moved against our side in last cycle
     (line_timing flagged "ACT NOW" -- but our edge is small -- maybe market knows)
  3. THIN N + LARGE EDGE: edge_pct >= 8 but per-player model_accuracy.n_props < 10
     (model hasn't seen enough samples to be trusted on this player)
  4. WEATHER AGAINST: prop is HR/TB OVER but weather lean is UNDER (wind in / cold)
  5. SP FATIGUE AGAINST K OVER: K OVER but SP has HIGH early-hook risk
  6. PARK ANTI-LEAN: HR OVER at a pitcher-friendly park (PNC, Petco etc.)
  7. STREAK FADE: COLD player on hit prop OVER
  8. BvP RED FLAG: pitcher career-owns this batter (BvP OPS < 0.500 in 10+ AB)

Output: data/trap_alerts.json -- props that triggered 1+ flags
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BB_PATH = os.path.join(DATA_DIR, "best_bets.json")
BD_PATH = os.path.join(DATA_DIR, "player_breakdowns.json")
WX_PATH = os.path.join(DATA_DIR, "weather_conditional.json")
FATIGUE_PATH = os.path.join(DATA_DIR, "pitcher_fatigue.json")
LINE_PATH = os.path.join(DATA_DIR, "line_timing.json")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
OUT_PATH = os.path.join(DATA_DIR, "trap_alerts.json")

PITCHER_FRIENDLY_PARKS = {"PNC Park", "Petco Park", "Oracle Park", "Tropicana Field",
                          "Oakland Coliseum", "Citi Field", "American Family Field"}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _hand(bd: Dict[str, Any]) -> str:
    return ((bd.get("tonight") or {}).get("vs_pitcher_hand")) or "?"


def _matchup_park(matchup: str, today: Dict[str, Any]) -> str:
    for g in today.get("games") or []:
        if g.get("matchup") == matchup:
            return g.get("park") or ""
    return ""


def _wx_for_matchup(matchup: str, wx: Dict[str, Any]) -> Dict[str, Any]:
    for g in wx.get("by_game") or []:
        if g.get("matchup") == matchup:
            return g
    return {}


def _fatigue_for_player(name: str, fatigue: Dict[str, Any]) -> Dict[str, Any]:
    for r in fatigue.get("by_pitcher") or []:
        if r.get("name") == name:
            return r
    return {}


def run() -> Dict[str, Any]:
    bb = _load(BB_PATH).get("bets") or []
    bd = (_load(BD_PATH).get("by_id") or {})
    wx = _load(WX_PATH)
    fatigue = _load(FATIGUE_PATH)
    today = _load(TODAY_PATH)
    line_data = _load(LINE_PATH)

    # Index act-now alerts by player_id
    act_now = {}
    for a in line_data.get("alerts") or []:
        if a.get("signal") == "ACT NOW" and a.get("player_id"):
            act_now[a["player_id"]] = a

    traps: List[Dict[str, Any]] = []
    for b in bb:
        pid = b.get("player_id")
        market = (b.get("market") or "")
        play = (b.get("play") or "").upper()
        edge = b.get("edge_pct") or 0
        flags: List[str] = []

        bdp = bd.get(str(pid)) or {}
        acc = bdp.get("model_accuracy") or {}
        n_props = acc.get("n_props", 0)

        # 3. THIN N + LARGE EDGE
        if edge >= 8 and n_props < 10:
            flags.append(f"Edge +{edge:.1f}% looks big but only {n_props} settled props on this player — model unproven")

        # Matchup-driven flags
        tonight = bdp.get("tonight") or {}
        matchup = tonight.get("matchup") or b.get("matchup")
        park = _matchup_park(matchup or "", today)
        weather = _wx_for_matchup(matchup or "", wx)
        wx_lean = (weather.get("lean") or "neutral").upper()

        # 4. WEATHER AGAINST (HR / TB)
        if market in ("batter_home_runs", "batter_total_bases") and play == "OVER" and wx_lean == "UNDER":
            flags.append(f"Weather suppresses HR/TB ({weather.get('reason','')}) — but we're betting OVER")
        if market in ("batter_home_runs", "batter_total_bases") and play == "UNDER" and wx_lean == "OVER":
            flags.append(f"Weather aids HR/TB ({weather.get('reason','')}) — but we're betting UNDER")

        # 5. SP FATIGUE / K OVER
        if market == "pitcher_strikeouts" and play == "OVER":
            f = _fatigue_for_player(b.get("player"), fatigue)
            if f.get("early_hook_risk") == "high":
                flags.append(f"SP {b.get('player')} HIGH early-hook risk — K OVER less likely")

        # 6. PARK ANTI-LEAN
        if market == "batter_home_runs" and play == "OVER" and park in PITCHER_FRIENDLY_PARKS:
            flags.append(f"HR OVER at pitcher-friendly park ({park})")

        # 7. STREAK FADE
        hc = ((bdp.get("form") or {}).get("hot_cold") or "").lower()
        if play == "OVER" and "cooling" in hc:
            flags.append(f"Batter cooling: {hc}")
        if play == "UNDER" and "heating up" in hc:
            flags.append(f"Batter heating up: {hc}")

        # 8. BvP red flag (career H2H vs tonight's SP)
        bvp = tonight.get("bvp_career") or {}
        ab = bvp.get("ab", 0)
        if ab >= 10 and bvp.get("ops") is not None:
            if play == "OVER" and bvp["ops"] < 0.500:
                flags.append(f"Pitcher owns this batter career: {bvp.get('hits',0)}-for-{ab}, {bvp['ops']:.3f} OPS")
            if play == "UNDER" and bvp["ops"] > 0.900:
                flags.append(f"Batter destroys this pitcher career: {bvp.get('hits',0)}-for-{ab}, {bvp['ops']:.3f} OPS")

        # 2. SHARP MONEY AGAINST
        if act_now.get(pid):
            a = act_now[pid]
            if a.get("market") == market:
                flags.append(f"Line sharpened against this side ({a.get('cents_moved')}c move) -- sharp money knows")

        # 1. UMP K-mult misaligned -- skipping for now (need to join today.json ump info per matchup)

        if flags:
            traps.append({
                "rank": b.get("rank"),
                "label": b.get("label"),
                "player": b.get("player"),
                "player_id": pid,
                "market": market,
                "line": b.get("line"),
                "play": play,
                "source": b.get("source"),
                "edge_pct": edge,
                "quality_score": b.get("quality_score"),
                "flags": flags,
                "severity": "high" if len(flags) >= 2 else "low",
            })

    traps.sort(key=lambda t: (-(len(t["flags"])), -(t.get("edge_pct") or 0)))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_traps": len(traps),
        "n_high_severity": sum(1 for t in traps if t["severity"] == "high"),
        "traps": traps,
        "note": ("These props passed the model's best_bets gate but have at least "
                  "one structural red flag. Don't auto-fade -- treat as 'review more carefully'."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Trap flags: {p['n_traps']} ({p['n_high_severity']} high-severity)")
    for t in p["traps"][:5]:
        print(f"  - {t['label']} ({t['severity']}):")
        for fl in t["flags"]:
            print(f"      ! {fl}")
