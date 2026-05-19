"""
EdgeStat -- MLB extended player props.

Adds prop projections beyond the existing mlb_batter_logs basics:

Batter props (Poisson on L14 per-game rate):
  - 1+ Total Base / 2+ TB / 3+ TB / 4+ TB
  - 1+ Walk / 2+ Walks
  - 1+ Strikeout / 2+ Strikeouts
  - HRR combo (1+ Hits+Runs+RBI total)

Pitcher props (Poisson on per-start average):
  - 1+ Walk / 2+ Walks / 3+ Walks
  - 5+/8+/10+ Strikeouts (extension of existing 4.5/5.5/6.5/7.5)
  - 15+/18+/21+ Outs Recorded
  - 1+/2+/3+ Earned Runs (under markets)

Output: data/mlb_extended_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "mlb_extended_props.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _poisson_p_over(lam: float, line: float) -> float:
    """P(X > line) where X ~ Poisson(lam). For 1+ X, line=0.5 gives P(X>=1)."""
    if lam <= 0: return 0.0
    thr = int(math.floor(line)) + 1
    s = 0.0
    for k in range(thr):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _batter_props(b: Dict[str, Any]) -> Dict[str, Any]:
    """Compute extended batter props from L14 stats."""
    s = b.get("stats_last_14") or {}
    n = s.get("n_games_logged") or b.get("n_games_logged") or 0
    if not n: return {}
    # Per-game rates
    tb_rate = (s.get("tb") or 0) / max(1, n)
    bb_rate = (s.get("bb") or 0) / max(1, n)
    so_rate = (s.get("so") or 0) / max(1, n)
    h_rate = (s.get("h") or 0) / max(1, n)
    r_rate = (s.get("r") or 0) / max(1, n) if s.get("r") is not None else 0
    rbi_rate = (s.get("rbi") or 0) / max(1, n) if s.get("rbi") is not None else 0
    hrr_rate = h_rate + r_rate + rbi_rate

    props: Dict[str, Any] = {}
    # Total bases (1+ / 2+ / 3+ / 4+)
    for n_tb in (1, 2, 3, 4):
        p = _poisson_p_over(tb_rate, n_tb - 0.5)
        if 0.05 < p < 0.99:
            props[f"{n_tb}_plus_tb"] = {"p": round(p, 4),
                                         "fair_yes": _american(p),
                                         "fair_no": _american(1 - p)}
    # Walks (1+ / 2+)
    for n_bb in (1, 2):
        p = _poisson_p_over(bb_rate, n_bb - 0.5)
        if 0.05 < p < 0.99:
            props[f"{n_bb}_plus_bb"] = {"p": round(p, 4),
                                         "fair_yes": _american(p),
                                         "fair_no": _american(1 - p)}
    # Strikeouts (1+ / 2+)
    for n_so in (1, 2):
        p = _poisson_p_over(so_rate, n_so - 0.5)
        if 0.05 < p < 0.99:
            props[f"{n_so}_plus_so"] = {"p": round(p, 4),
                                         "fair_yes": _american(p),
                                         "fair_no": _american(1 - p)}
    # HRR combo (1+ / 2+ / 3+)
    for n_hrr in (1, 2, 3):
        p = _poisson_p_over(hrr_rate, n_hrr - 0.5)
        if 0.05 < p < 0.99:
            props[f"{n_hrr}_plus_hrr"] = {"p": round(p, 4),
                                            "fair_yes": _american(p),
                                            "fair_no": _american(1 - p)}
    return {
        "tb_rate": round(tb_rate, 3),
        "bb_rate": round(bb_rate, 3),
        "so_rate": round(so_rate, 3),
        "hrr_rate": round(hrr_rate, 3),
        "props": props,
    }


def _pitcher_props(p: Dict[str, Any]) -> Dict[str, Any]:
    """Compute extended pitcher props from per-start averages."""
    s = p.get("stats") or {}
    avg_k = s.get("avg_k") or 0
    avg_er = s.get("avg_er") or 0
    avg_ip = s.get("avg_ip") or 5.5
    tot_bb = s.get("tot_bb") or 0
    tot_ip = s.get("tot_ip") or 1
    n_starts = s.get("n_starts_logged") or p.get("n_starts_logged") or 1
    # Walk rate per start (BB / starts)
    avg_bb = tot_bb / max(1, n_starts)
    # Outs per start = IP * 3
    avg_outs = avg_ip * 3.0

    props: Dict[str, Any] = {}
    # Extended K props (5+/6+/7+/8+/9+/10+/11+)
    for k_line in (5, 6, 7, 8, 9, 10, 11):
        prob = _poisson_p_over(avg_k, k_line - 0.5)
        if 0.05 < prob < 0.99:
            props[f"{k_line}_plus_k"] = {"p": round(prob, 4),
                                          "fair_yes": _american(prob),
                                          "fair_no": _american(1 - prob)}
    # Walk props (1+/2+/3+)
    for bb_line in (1, 2, 3):
        prob = _poisson_p_over(avg_bb, bb_line - 0.5)
        if 0.05 < prob < 0.99:
            props[f"{bb_line}_plus_bb"] = {"p": round(prob, 4),
                                              "fair_yes": _american(prob),
                                              "fair_no": _american(1 - prob)}
    # ER props (1+/2+/3+ — under markets typically)
    for er_line in (1, 2, 3, 4):
        prob_over = _poisson_p_over(avg_er, er_line - 0.5)
        prob_under = 1 - prob_over
        if 0.05 < prob_under < 0.99:
            props[f"under_{er_line}_plus_er"] = {
                "p_under": round(prob_under, 4),
                "fair_under": _american(prob_under),
            }
    # Outs recorded (15/18/21 = 5/6/7 innings)
    for outs_line in (12, 15, 18, 21):
        prob = _poisson_p_over(avg_outs, outs_line - 0.5)
        if 0.05 < prob < 0.99:
            props[f"{outs_line}_plus_outs"] = {"p": round(prob, 4),
                                                  "fair_yes": _american(prob),
                                                  "fair_no": _american(1 - prob)}
    return {
        "avg_k": round(avg_k, 2),
        "avg_bb": round(avg_bb, 2),
        "avg_er": round(avg_er, 2),
        "avg_outs": round(avg_outs, 1),
        "props": props,
    }


def run() -> Dict[str, Any]:
    batters_doc = _load(os.path.join(DATA_DIR, "mlb_batter_logs.json"))
    pitchers_doc = _load(os.path.join(DATA_DIR, "mlb_pitcher_logs.json"))

    batters_out = []
    for b in (batters_doc.get("batters") or []):
        ext = _batter_props(b)
        if not ext.get("props"): continue
        batters_out.append({
            "name": b.get("name"),
            "team_abbr": b.get("team_abbr"),
            "n_games": b.get("n_games_logged"),
            **ext,
        })

    pitchers_out = []
    for p in (pitchers_doc.get("pitchers") or []):
        ext = _pitcher_props(p)
        if not ext.get("props"): continue
        pitchers_out.append({
            "name": p.get("name"),
            "team_abbr": p.get("team_abbr"),
            "n_starts": p.get("n_starts_logged"),
            **ext,
        })

    # Top picks: any prop with p between 0.65 and 0.90 = strong-but-not-locked
    top_picks = []
    for b in batters_out:
        for mkt, info in (b.get("props") or {}).items():
            p = info.get("p") or info.get("p_under")
            if not p or not (0.65 <= p <= 0.90): continue
            top_picks.append({
                "type": "BATTER",
                "name": b["name"], "team": b["team_abbr"],
                "market": mkt, "prob": p,
                "fair": info.get("fair_yes") or info.get("fair_under"),
            })
    for p in pitchers_out:
        for mkt, info in (p.get("props") or {}).items():
            prob = info.get("p") or info.get("p_under")
            if not prob or not (0.65 <= prob <= 0.90): continue
            top_picks.append({
                "type": "PITCHER",
                "name": p["name"], "team": p["team_abbr"],
                "market": mkt, "prob": prob,
                "fair": info.get("fair_yes") or info.get("fair_under"),
            })
    top_picks.sort(key=lambda x: -x["prob"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_batters": len(batters_out),
        "n_pitchers": len(pitchers_out),
        "n_total_batter_props": sum(len(b.get("props") or {}) for b in batters_out),
        "n_total_pitcher_props": sum(len(p.get("props") or {}) for p in pitchers_out),
        "n_sweet_spot_picks": len(top_picks),
        "top_picks": top_picks[:50],
        "batters": batters_out,
        "pitchers": pitchers_out,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"MLB extended props: {p['n_batters']} batters ({p['n_total_batter_props']} props) + "
          f"{p['n_pitchers']} pitchers ({p['n_total_pitcher_props']} props)")
    print(f"  Sweet-spot (65-90% prob): {p['n_sweet_spot_picks']} picks")
    print("  Top 15:")
    for pick in p["top_picks"][:15]:
        print(f"    [{pick['type']:7s}] {pick['name']:25s} ({pick['team']:3s}) "
              f"{pick['market']:25s} p={pick['prob']*100:.0f}% fair={pick['fair']}")
