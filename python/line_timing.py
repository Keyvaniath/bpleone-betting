"""
EdgeStat -- line movement / bet timing tracker.

Diffs current props.json + pickem.json prices against the prior snapshot
saved on the last run (typically ~3 hours ago since props pipeline runs
3x daily). Tells Brandon WHEN to bet:

  - "ACT NOW": line moved in OUR direction in the last cycle
    (book is sharpening against our side -- the price is getting WORSE,
     so bet before it moves further). Surfaced as an alert.
  - "WAIT": line moved AGAINST our direction (price getting BETTER for
    us; wait for it to drift further toward closing).
  - "STABLE": no meaningful movement.

Output: data/line_timing.json
  {
    "generated_at": "...",
    "n_props": 250, "n_act_now": 8, "n_wait": 4, "n_stable": 238,
    "alerts": [
      { player, market, line, src, our_play, prev_price, curr_price,
        cents_moved, direction, signal: "ACT NOW" | "WAIT", note }
    ]
  }

Snapshot lives at data/.line_prev.json.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROPS_PATH = os.path.join(DATA_DIR, "props.json")
PICKEM_PATH = os.path.join(DATA_DIR, "pickem.json")
PREV_PATH = os.path.join(DATA_DIR, ".line_prev.json")
OUT_PATH = os.path.join(DATA_DIR, "line_timing.json")

MIN_CENTS_MOVE = 5    # ignore tiny shifts (within typical line-tightening noise)


def _load(p: str) -> Dict[str, Any]:
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _key(p: Dict[str, Any], src: str) -> str:
    line = p.get("line") if src == "DK" else p.get("pp_line")
    return f"{src}|{p.get('player_id')}|{p.get('market')}|{line}"


def _snapshot_props() -> Dict[str, Dict[str, Any]]:
    """Map (src|pid|market|line) -> {dk_over, dk_under, pp_line, model_prob_over, play}."""
    out: Dict[str, Dict[str, Any]] = {}
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        out[_key(p, "DK")] = {
            "dk_over": p.get("dk_over"),
            "dk_under": p.get("dk_under"),
            "play": p.get("play"),
            "model_prob_over": p.get("model_prob_over"),
        }
    for p in (_load(PICKEM_PATH).get("props") or []):
        out[_key(p, "PP")] = {
            "pp_line": p.get("pp_line"),
            "dk_line": p.get("dk_line"),
            "play": ("OVER" if (p.get("model_prob_over") or 0) >= (p.get("model_prob_under") or 0) else "UNDER"),
            "model_prob_over": p.get("model_prob_over"),
        }
    return out


def _cents_diff(old: Optional[int], new: Optional[int]) -> Optional[int]:
    """Net cents moved (>0 = price tightened i.e. odds worse for the bettor)."""
    if old is None or new is None:
        return None
    # American-cent move: if both negative, more negative is worse for bettor
    # We'll compute |new - old| with sign relative to typical 'tightening' direction
    return new - old


def _classify(old: Dict[str, Any], new: Dict[str, Any], src: str, current_prop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    play = (new.get("play") or "").upper()
    if play not in ("OVER", "UNDER"):
        return None
    # Look at the price for our play side
    if src == "DK":
        old_p = old.get("dk_over") if play == "OVER" else old.get("dk_under")
        new_p = new.get("dk_over") if play == "OVER" else new.get("dk_under")
    else:
        # PP uses static -119 typically; line shift detection on pp_line
        old_line = old.get("pp_line"); new_line = new.get("pp_line")
        if old_line is None or new_line is None:
            return None
        diff = (new_line - old_line)
        if abs(diff) < 0.25:
            return None
        # For PP: line moving UP is worse for OVER, better for UNDER
        if play == "OVER" and diff > 0:
            signal = "WAIT"; note = f"PP line moved {old_line} -> {new_line} (UP, OVER easier to find)"
        elif play == "OVER" and diff < 0:
            signal = "ACT NOW"; note = f"PP line moved {old_line} -> {new_line} (DOWN, OVER tightening)"
        elif play == "UNDER" and diff > 0:
            signal = "ACT NOW"; note = f"PP line moved {old_line} -> {new_line} (UP, UNDER tightening)"
        else:
            signal = "WAIT"; note = f"PP line moved {old_line} -> {new_line} (DOWN, UNDER easier to find)"
        return {"signal": signal, "note": note, "cents_moved": diff,
                "prev_price": old_line, "curr_price": new_line}
    if old_p is None or new_p is None:
        return None
    cents = _cents_diff(old_p, new_p)
    if cents is None or abs(cents) < MIN_CENTS_MOVE:
        return None
    # American odds: bigger negative = worse for bettor (favored side)
    # If old=-110, new=-125, cents = -15, price WORSENED for bettor
    if cents < 0:
        signal = "ACT NOW"
        note = f"Price worsened by {abs(cents)} cents ({old_p} -> {new_p}); book is sharpening against this side."
    else:
        signal = "WAIT"
        note = f"Price improved by {cents} cents ({old_p} -> {new_p}); line drifting toward our side -- patience may pay."
    return {"signal": signal, "note": note, "cents_moved": cents,
            "prev_price": old_p, "curr_price": new_p}


def run() -> Dict[str, Any]:
    curr = _snapshot_props()
    prev = _load(PREV_PATH)
    alerts: List[Dict[str, Any]] = []
    n_act_now = n_wait = n_stable = 0

    # Build lookup of current full prop records for output enrichment
    full_props: Dict[str, Dict[str, Any]] = {}
    for p in (_load(PROPS_PATH).get("top_edges") or []):
        full_props[_key(p, "DK")] = p
    for p in (_load(PICKEM_PATH).get("props") or []):
        full_props[_key(p, "PP")] = p

    for k, new in curr.items():
        if k not in prev:
            n_stable += 1
            continue
        src = k.split("|")[0]
        info = _classify(prev[k], new, src, full_props.get(k, {}))
        if info is None:
            n_stable += 1
            continue
        if info["signal"] == "ACT NOW":
            n_act_now += 1
        elif info["signal"] == "WAIT":
            n_wait += 1
        fp = full_props.get(k, {})
        alerts.append({
            "src": src,
            "player": fp.get("player"),
            "player_id": fp.get("player_id"),
            "market": fp.get("market"),
            "line": fp.get("line") if src == "DK" else fp.get("pp_line"),
            "our_play": new.get("play"),
            **info,
        })
    # Sort alerts: ACT NOW first, then by absolute cents moved
    alerts.sort(key=lambda a: (0 if a["signal"] == "ACT NOW" else 1, -abs(a["cents_moved"])))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_props": len(curr),
        "n_act_now": n_act_now,
        "n_wait": n_wait,
        "n_stable": n_stable,
        "alerts": alerts[:50],
        "note": ("If prev snapshot missing (first run) all props show STABLE. "
                  "Subsequent runs detect cycle-over-cycle line movement and "
                  "classify each prop as ACT NOW (sharpening against us) / "
                  "WAIT (drifting toward us) / STABLE."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    # Persist current snapshot for next run
    with open(PREV_PATH, "w") as f:
        json.dump(curr, f)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT_PATH}")
    print(f"  Tracked: {p['n_props']} props")
    print(f"  ACT NOW alerts: {p['n_act_now']}")
    print(f"  WAIT alerts:    {p['n_wait']}")
    print(f"  STABLE:         {p['n_stable']}")
    for a in p["alerts"][:5]:
        print(f"    [{a['signal']}] {a.get('player')} {a.get('our_play')} {a.get('line')} {a.get('market','').replace('_',' ')} -- {a['note']}")
