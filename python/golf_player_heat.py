"""
EdgeStat -- golf player heat tracker (recent form + finish momentum).

For every player who finished the most recent PGA event:
  - Compute finish-position percentile (better than X% of field)
  - Sunday round momentum: was last round better/worse than tournament average?
  - Score-to-par consistency
  - Made-cut flag

For each, classify as:
  - 🔥 HOT: finished top-20% AND closing round better than tournament avg
  - ❄️ COLD: missed cut OR closing round 3+ strokes worse than avg

This builds "who's playing well right now" entering tomorrow's slate.

Output: data/golf_player_heat.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
import urllib.request
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "golf_player_heat.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _parse_to_par(s: Optional[str]) -> Optional[int]:
    """Parse '-9' / '+2' / 'E' / 'CUT' / 'WD' → int strokes vs par, or None."""
    if s is None: return None
    if isinstance(s, (int, float)): return int(s)
    s = str(s).strip()
    if s in ("CUT", "WD", "DQ", "", "--"): return None
    if s == "E": return 0
    try:
        return int(s)
    except Exception:
        return None


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "golf_state.json"))
    tournament = state.get("active_tournament") or {}
    field = state.get("field") or []
    if not field:
        payload = {"generated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    "n_players_analyzed": 0, "note": "no field data"}
        with open(OUT, "w") as f: json.dump(payload, f, indent=2)
        return payload

    # Parse field: total_to_par + rounds + last_round_score
    parsed: List[Dict[str, Any]] = []
    for p in field:
        total = _parse_to_par(p.get("total_to_par"))
        last_round = _parse_to_par(p.get("last_round_score"))
        rounds_played = p.get("rounds_played") or 0
        if rounds_played < 1: continue
        is_cut = bool(p.get("is_cut")) or p.get("total_to_par") == "CUT"
        is_wd = bool(p.get("is_withdrawn")) or p.get("total_to_par") == "WD"
        avg_round = (total / rounds_played) if (total is not None and rounds_played > 0) else None
        last_vs_avg = (last_round - avg_round) if (last_round is not None and avg_round is not None) else None
        parsed.append({
            "name": p.get("name"),
            "country": p.get("country"),
            "espn_id": p.get("espn_id"),
            "finish_pos": p.get("order"),
            "total_to_par": total,
            "rounds_played": rounds_played,
            "last_round_score": last_round,
            "avg_round_vs_par": round(avg_round, 2) if avg_round is not None else None,
            "last_vs_avg": round(last_vs_avg, 2) if last_vs_avg is not None else None,
            "is_cut": is_cut,
            "is_withdrawn": is_wd,
        })

    # Classify HOT vs COLD
    total_field = len(parsed)
    top20_threshold = max(1, int(total_field * 0.20))
    for p in parsed:
        kind = None
        signals = []
        if p["is_withdrawn"]:
            kind = "WD"
            signals.append("withdrew")
        elif p["is_cut"]:
            kind = "COLD"
            signals.append("missed cut")
        else:
            pos = p["finish_pos"]
            lva = p["last_vs_avg"]
            if pos and pos <= top20_threshold and lva is not None and lva < 0:
                kind = "HOT"
                signals.append(f"finished T{pos}, Sunday {lva:.1f} vs tourney avg")
            elif lva is not None and lva >= 3:
                kind = "COLD"
                signals.append(f"Sunday {lva:+.1f} vs tourney avg")
            elif pos and pos <= top20_threshold:
                kind = "HOT"
                signals.append(f"finished T{pos}")
            else:
                kind = "STABLE"
        p["kind"] = kind
        p["signals"] = signals

    hot = sorted([p for p in parsed if p["kind"] == "HOT"], key=lambda p: p.get("finish_pos") or 999)
    cold = sorted([p for p in parsed if p["kind"] == "COLD"], key=lambda p: -(p.get("last_vs_avg") or 0))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "source_tournament": tournament.get("name"),
        "source_complete": tournament.get("is_complete"),
        "n_players_analyzed": len(parsed),
        "top20_threshold_pos": top20_threshold,
        "n_hot": len(hot),
        "n_cold": len(cold),
        "n_withdrew": sum(1 for p in parsed if p["kind"] == "WD"),
        "hot_players": hot[:30],
        "cold_players": cold[:30],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    # Use .get() with defaults — when no field data is available, run() returns
    # an early-exit payload without n_hot/n_cold/source_tournament keys.
    if p.get("note"):
        print(f"Golf player heat: {p['note']} (analyzed 0 players)")
        raise SystemExit(0)
    print(f"Golf player heat: {p.get('n_hot', 0)} HOT, {p.get('n_cold', 0)} COLD "
          f"(of {p.get('n_players_analyzed', 0)} from {p.get('source_tournament')})")
    def _safe(v, fmt="{}", fallback="--"):
        try: return fmt.format(v) if v is not None else fallback
        except Exception: return fallback

    print("Top 10 HOT (best finish + closing round momentum):")
    for a in p["hot_players"][:10]:
        sig = " · ".join(a.get("signals") or [])
        pos = _safe(a.get("finish_pos"), "T{:>3}")
        ttp = _safe(a.get("total_to_par"), "{:+d}")
        lrs = _safe(a.get("last_round_score"), "{:+d}")
        avg = _safe(a.get("avg_round_vs_par"), "{:+.1f}")
        print(f"  {pos} {a.get('name','?'):25s} ({a.get('country','?'):12s}) "
              f"{ttp} total · last R{lrs} (avg {avg}) -- {sig}")
    print("Top 10 COLD (poor closing rounds):")
    for a in p["cold_players"][:10]:
        sig = " · ".join(a.get("signals") or [])
        pos = _safe(a.get("finish_pos"), "T{:>3}")
        print(f"  {pos} {a.get('name','?'):25s} ({a.get('country','?'):12s}) -- {sig}")
