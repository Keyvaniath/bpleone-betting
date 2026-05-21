"""
EdgeStat -- F1 qualifying position predictor.

For each upcoming F1 race, projects per-driver:
  - P(pole position / Q1 fastest)
  - P(top-3 qualifying / front row)
  - P(Q3 / top-10 qualifying)

Approach:
  Driver one-lap pace differs from race pace -- some are pure qualifiers
  (Verstappen, Leclerc, Sainz on Ferrari), others race better than they qualify
  (Hamilton historical, Russell in heavy fuel).

  We use driver_quali_z which is ~0.85*driver_race_z (one-lap variance is
  smaller than race-pace variance). Plus a track-specific factor.

  Common markets:
    - Pole position (-200 to +500)
    - Top-3 grid (~+250 to +700)
    - Top-6 grid (~+150 to +400)
    - Top-10 grid (-200 to +250)

Output: data/f1_qualifying_predictor.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "f1_qualifying_predictor.json")

# 2025 season qualifying skill ratings (z-scores, lower=better)
DRIVER_QUALI_Z = {
    "max verstappen":     -1.85,
    "charles leclerc":    -1.60,
    "lando norris":       -1.55,
    "carlos sainz":       -1.40,
    "oscar piastri":      -1.35,
    "george russell":     -1.30,
    "lewis hamilton":     -0.90,
    "fernando alonso":    -0.85,
    "lance stroll":       0.20,
    "yuki tsunoda":       -0.15,
    "alex albon":         -0.30,
    "logan sargeant":     0.85,
    "nico hulkenberg":    -0.10,
    "kevin magnussen":    0.05,
    "valtteri bottas":    0.10,
    "guanyu zhou":        0.40,
    "pierre gasly":       -0.20,
    "esteban ocon":       -0.05,
    "daniel ricciardo":   0.15,
    "oliver bearman":     0.55,
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _norm_cdf(x):
    if x is None: return None
    if x > 8: return 1.0
    if x < -8: return 0.0
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    a1, a2, a3, a4, a5 = 0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429
    poly = a1*t + a2*t**2 + a3*t**3 + a4*t**4 + a5*t**5
    pdf = math.exp(-x*x / 2) / math.sqrt(2 * math.pi)
    cdf = 1 - pdf * poly
    return cdf if x >= 0 else 1 - cdf


def _norm_inv(p):
    """Inverse normal CDF (Beasley-Springer-Moro)."""
    if p <= 0 or p >= 1: return 0
    a = [-39.6968302866538, 220.946098424521, -275.928510446969,
         138.357751867269, -30.6647980661472, 2.50662827745924]
    b = [-54.4760987982241, 161.585836858041, -155.698979859887,
         66.8013118877197, -13.2806815528857]
    c = [-7.78489400243029e-3, -0.322396458041136, -2.40075827716184,
         -2.54973253934373, 4.37466414146497, 2.93816398269878]
    d = [7.78469570904146e-3, 0.32246712907004, 2.445134137143,
         3.75440866190742]
    p_low, p_high = 0.02425, 1 - 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return ((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5] / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) * q / \
                (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
            ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def run() -> Dict[str, Any]:
    f1_state = _load(os.path.join(DATA_DIR, "f1_state.json"))
    next_race = f1_state.get("next_race") or f1_state.get("upcoming")
    circuit = (next_race or {}).get("circuit") or (next_race or {}).get("name") or "Unknown"

    # Field size for F1 is 20 drivers
    field_size = 20
    # Z thresholds (more drivers = more negative cutoff for "top N")
    def z_thresh(top_n: int) -> float:
        return _norm_inv(top_n / field_size)

    z_pole   = z_thresh(1)   # ~ -1.96 (top 5%)
    z_top3   = z_thresh(3)   # ~ -1.04 (top 15%)
    z_top6   = z_thresh(6)   # ~ -0.52 (top 30%)
    z_top10  = z_thresh(10)  # ~ 0.0 (top 50%)

    rows: List[Dict[str, Any]] = []
    for driver, quali_z in DRIVER_QUALI_Z.items():
        # P(rank<=N) = P(quali_pace < z_thresh) = Phi(z_thresh - quali_z)
        p_pole  = _norm_cdf(z_pole - quali_z)
        p_top3  = _norm_cdf(z_top3 - quali_z)
        p_top6  = _norm_cdf(z_top6 - quali_z)
        p_top10 = _norm_cdf(z_top10 - quali_z)

        # Edge classification
        edge_class = "NONE"
        best_market = None
        if 0.30 <= p_pole <= 0.50:
            edge_class = "STRONG_POLE"
            best_market = {"market": "POLE", "p": round(p_pole, 3), "fair_odds": _american(p_pole)}
        elif 0.55 <= p_top3 <= 0.72:
            edge_class = "STRONG_TOP_3"
            best_market = {"market": "TOP_3", "p": round(p_top3, 3), "fair_odds": _american(p_top3)}
        elif 0.55 <= p_top6 <= 0.72:
            edge_class = "STRONG_TOP_6"
            best_market = {"market": "TOP_6", "p": round(p_top6, 3), "fair_odds": _american(p_top6)}

        rows.append({
            "driver": driver,
            "quali_z": quali_z,
            "p_pole":   round(p_pole, 3),
            "p_top_3":  round(p_top3, 3),
            "p_top_6":  round(p_top6, 3),
            "p_top_10": round(p_top10, 3),
            "fair_pole":   _american(p_pole),
            "fair_top_3":  _american(p_top3),
            "fair_top_6":  _american(p_top6),
            "fair_top_10": _american(p_top10),
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: r["quali_z"])
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "next_race": next_race,
        "circuit": circuit,
        "n_drivers": len(rows),
        "n_strong": len(strong),
        "z_thresholds": {
            "pole":   round(z_pole, 3),
            "top_3":  round(z_top3, 3),
            "top_6":  round(z_top6, 3),
            "top_10": round(z_top10, 3),
        },
        "method_note": "Driver one-lap pace z-scores -> P(rank<=N) = Phi(z_thresh - quali_z). "
                       "Field size 20 drivers. STRONG flagged in narrow edge windows where "
                       "model differs materially from typical book lines.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[f1-quali] {o['n_drivers']} drivers, {o['n_strong']} strong -> {OUT}")
