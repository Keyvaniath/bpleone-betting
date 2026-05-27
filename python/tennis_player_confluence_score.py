"""
EdgeStat -- Tennis player confluence score.

Composite per-tennis-player score combining:
  - tennis_dominance_alerts (n_signals)
  - tennis_match_win_props (p_match_win)
  - tennis_1st_set_winner (p_1st_set)
  - tennis_aces_props (edge_class)
  - tennis_breaks_of_serve (edge_class)

Score formula:
  score = dom_signals * 2.5 + p_match_win * 10 + p_1st_set * 8
        + aces_over_signal + breaks_over_signal

PLAYER_LOCK = score >= 16 with dom_signals >= 4
PLAYER_STRONG = 10-15
PLAYER_FADE = score <= 2

Output: data/tennis_player_confluence_score.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_player_confluence_score.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _safe(x, default=0.0):
    try:
        if x is None: return default
        return float(x)
    except Exception:
        return default


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def run() -> Dict[str, Any]:
    dom = _load(os.path.join(DATA_DIR, "tennis_dominance_alerts.json"))
    win = _load(os.path.join(DATA_DIR, "tennis_match_win_props.json"))
    set1 = _load(os.path.join(DATA_DIR, "tennis_1st_set_winner.json"))
    aces = _load(os.path.join(DATA_DIR, "tennis_aces_props.json"))
    breaks = _load(os.path.join(DATA_DIR, "tennis_breaks_of_serve.json"))

    dom_idx = {_norm(a.get("player")): a for a in (dom.get("alerts") or []) if isinstance(a, dict)}

    win_idx = {}
    for r in (win.get("rows") or []):
        if isinstance(r, dict):
            win_idx[_norm(r.get("player") or r.get("favorite") or "")] = r

    set1_idx = {}
    for r in (set1.get("rows") or []):
        if isinstance(r, dict):
            set1_idx[_norm(r.get("player") or r.get("favorite") or "")] = r

    aces_idx = {_norm(r.get("player")): r for r in (aces.get("rows") or []) if isinstance(r, dict)}
    breaks_idx = {_norm(r.get("player")): r for r in (breaks.get("rows") or []) if isinstance(r, dict)}

    all_players = (set(dom_idx) | set(win_idx) | set(set1_idx)
                   | set(aces_idx) | set(breaks_idx))

    rows: List[Dict[str, Any]] = []
    for name in all_players:
        d = dom_idx.get(name, {})
        w = win_idx.get(name, {})
        s1 = set1_idx.get(name, {})
        a = aces_idx.get(name, {})
        b = breaks_idx.get(name, {})

        dom_signals = int(d.get("n_signals", 0) or 0)
        p_win = _safe(w.get("p_win") or w.get("p_match_win"))
        p_1st = _safe(s1.get("p_1st_set") or s1.get("p_set1_win"))
        aces_ec = (a.get("edge_class") or "").upper()
        breaks_ec = (b.get("edge_class") or "").upper()
        aces_signal = 2 if "OVER" in aces_ec else 0
        breaks_signal = 2 if "OVER" in breaks_ec else 0

        score = (dom_signals * 2.5
                 + p_win * 10
                 + p_1st * 8
                 + aces_signal
                 + breaks_signal)

        has_data = (dom_signals > 0 or p_win > 0 or p_1st > 0
                    or aces_signal > 0 or breaks_signal > 0)

        if not has_data:
            tier = "NO_DATA"
        elif score >= 16 and dom_signals >= 4:
            tier = "PLAYER_LOCK"
        elif score >= 10:
            tier = "PLAYER_STRONG"
        elif score <= 2:
            tier = "PLAYER_FADE"
        else:
            tier = "PLAYER_NEUTRAL"

        rows.append({
            "player": (d.get("player") or w.get("player") or s1.get("player")
                       or a.get("player") or name.title()),
            "match": d.get("match") or w.get("match") or s1.get("match") or a.get("match"),
            "dom_signals": dom_signals,
            "p_match_win": round(p_win, 3),
            "p_1st_set": round(p_1st, 3),
            "aces_edge": aces_ec or None,
            "breaks_edge": breaks_ec or None,
            "composite_score": round(score, 2),
            "tier": tier,
        })

    rows.sort(key=lambda r: -r["composite_score"])

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_players": len(rows),
        "n_lock": sum(1 for r in rows if r["tier"] == "PLAYER_LOCK"),
        "n_strong": sum(1 for r in rows if r["tier"] == "PLAYER_STRONG"),
        "n_fade": sum(1 for r in rows if r["tier"] == "PLAYER_FADE"),
        "method_note": "Composite tennis player score. dom_signals*2.5 + "
                       "p_match_win*10 + p_1st_set*8 + aces_over_signal + "
                       "breaks_over_signal. LOCK >= 16 with dom>=4; STRONG 10-15.",
        "rows": rows,
        "locks": [r for r in rows if r["tier"] == "PLAYER_LOCK"],
        "fades": [r for r in rows if r["tier"] == "PLAYER_FADE"],
        "top_15": rows[:15],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-confluence] {o['n_players']} players "
          f"({o['n_lock']} LOCK, {o['n_strong']} STRONG, {o['n_fade']} FADE) -> {OUT}")
