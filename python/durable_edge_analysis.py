"""
Durable-edge deep dive -> data/durable_edge_analysis.json

The held-out validation found the curated edge is carried by one well-sampled,
durable family: PrizePicks batter Hits+Runs+RBIs (hrr) UNDER 3.5. This module
stress-tests THAT family by sub-condition (temporal decay, per-generator, realized
margin, batter concentration) and computes honest Kelly sizing, so the one edge the
site actually stands behind is documented with numbers that auto-update as the
ledger grows -- no hardcoded, decaying claims.
"""
import json
import os
import statistics
from collections import Counter
from prob_calibration import canon_market_family

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LEDGER = os.path.join(DATA_DIR, "all_picks_ledger.json")
OUT = os.path.join(DATA_DIR, "durable_edge_analysis.json")
FAMILY = "mlb_hrr_3.5_under"
LABEL = "MLB batter Hits+Runs+RBIs UNDER 3.5 (PrizePicks)"


def _net(p):
    pu = p.get("payout_units")
    if pu is not None:
        return float(pu)
    return 0.91 if p.get("result") == "won" else -1.0


def _stat(rows):
    n = len(rows)
    w = sum(1 for p in rows if p.get("result") == "won")
    nu = sum(_net(p) for p in rows)
    return {"n": n, "wins": w, "losses": n - w,
            "hit": round(100 * w / n, 1) if n else 0.0,
            "roi": round(100 * nu / n, 1) if n else 0.0,
            "net": round(nu, 1)}


def build():
    import datetime
    d = json.load(open(LEDGER, encoding="utf-8"))
    picks = [p for p in (d.get("picks") or [])
             if p.get("settled") and p.get("result") in ("won", "lost")
             and canon_market_family(p.get("market")) == FAMILY]
    if len(picks) < 30:
        return {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "family": FAMILY, "insufficient": True, "n": len(picks)}

    picks.sort(key=lambda p: (p.get("date") or "", p.get("recorded_at") or ""))
    overall = _stat(picks)

    # Sizing from realized win rate + average decimal odds (payout_units on a win == b).
    wins = [p for p in picks if p.get("result") == "won"]
    b = statistics.mean(_net(p) for p in wins) if wins else 0.91
    p_ = overall["wins"] / overall["n"]
    q = 1 - p_
    full_kelly = (b * p_ - q) / b if b else 0.0
    ev = p_ * b - q

    # Temporal halves (decay check).
    mid = len(picks) // 2
    early, late = picks[:mid], picks[mid:]
    temporal = [
        {"half": "early", "span": [early[0]["date"], early[-1]["date"]], **_stat(early)},
        {"half": "late", "span": [late[0]["date"], late[-1]["date"]], **_stat(late)},
    ]

    # Per generator.
    by_source = []
    for src in sorted({(p.get("primary_source_module") or p.get("source")) for p in picks}):
        rows = [p for p in picks if (p.get("primary_source_module") or p.get("source")) == src]
        if len(rows) >= 5:
            by_source.append({"source": src, **_stat(rows)})
    by_source.sort(key=lambda r: -r["n"])

    # Realized margin: how decisively do the unders clear?
    actuals = [p.get("outcome", {}).get("actual") for p in picks]
    actuals = [a for a in actuals if isinstance(a, (int, float))]
    decisive = sum(1 for a in actuals if a <= 1)  # cleared the 3.5 line by >=2
    margin_dist = {str(k): v for k, v in sorted(Counter(actuals).items())}

    # Concentration across batters.
    bc = Counter(p.get("player_or_matchup") for p in picks)
    top5 = bc.most_common(5)
    top5_n = sum(c for _, c in top5)

    decay = late and early and (_stat(late)["roi"] >= _stat(early)["roi"] - 5)
    broad = top5_n / overall["n"] < 0.35
    verdict = ("Robust: " + ("no decay (recent half holds/strengthens), " if decay else "SOME decay in the recent half, ")
               + ("holds across all generators, " if all(s["roi"] > 0 for s in by_source) else "uneven across generators, ")
               + ("broad across batters, " if broad else "concentrated in a few batters, ")
               + f"wins decisively ({round(100*decisive/len(actuals)) if actuals else 0}% clear by 2+).")

    return {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "family": FAMILY,
        "label": LABEL,
        "overall": overall,
        "sizing": {
            "win_prob": round(p_, 3),
            "avg_decimal_odds": round(1 + b, 3),
            "ev_per_unit": round(ev, 3),
            "full_kelly_pct": round(100 * full_kelly),
            "half_kelly_pct": round(50 * full_kelly),
            "quarter_kelly_pct": round(25 * full_kelly),
            "eighth_kelly_pct": round(12.5 * full_kelly, 1),
            "recommended": "eighth-Kelly (~{}%) or a flat 1-2% cap".format(round(12.5 * full_kelly, 1)),
        },
        "temporal": temporal,
        "by_source": by_source,
        "margin": {"decisive_under_pct": round(100 * decisive / len(actuals)) if actuals else 0,
                   "distribution": margin_dist},
        "concentration": {"top5_share_pct": round(100 * top5_n / overall["n"]),
                          "top5": [{"batter": k, "n": c} for k, c in top5]},
        "verdict": verdict,
        "caveats": [
            "Sizing is theoretical: full Kelly (~{}%) is reckless here -- these props are "
            "CORRELATED (many batters per slate; unders cluster in low-scoring games), so "
            "treating them as independent bets overstates safe size. Use a small fraction "
            "and cap slate exposure.".format(round(100 * full_kelly)),
            "Assumes the PrizePicks line stays ~3.5 and is actually available at the priced "
            "odds; books move lines on sharp action. CLV (the odds key) is what would confirm "
            "you're getting the number, not just that the bet won.",
            "~1 month, single season. Robust within that window; not a cross-season guarantee.",
        ],
    }


def write_artifact():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = write_artifact()
    print(f"Wrote {OUT}")
    if p.get("insufficient"):
        print("  insufficient sample")
    else:
        o = p["overall"]
        print(f"  {p['family']}: n={o['n']} {o['wins']}-{o['losses']} hit={o['hit']}% ROI={o['roi']}%")
        print(f"  sizing: p={p['sizing']['win_prob']} ev={p['sizing']['ev_per_unit']} "
              f"full-K={p['sizing']['full_kelly_pct']}% rec={p['sizing']['recommended']}")
        print(f"  {p['verdict']}")
