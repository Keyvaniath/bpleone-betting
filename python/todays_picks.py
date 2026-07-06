"""
Today's Picks consolidator -> data/todays_picks.json

The Picks hub (picks.html) replaces ~10 separate pick-board pages (locks, alpha,
high-confidence, best-bets, consensus, top-plays, convergence, fades, bet-slate)
with ONE filterable board. This reads each curated category board, normalizes every
pick to a common schema, tags it with its category, de-dups the same pick across
boards (keeping its highest-conviction category), and emits a single array the hub
renders + filters by category / sport. Empty boards (off-hours, between slates) just
contribute nothing -- the hub honestly shows whatever is live.

Runs in the pipeline AFTER the category boards are written (it only reads their JSON).
"""
import json
import os
import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "todays_picks.json")

# (filename, [candidate list keys in priority order], category key, label)
# Ordered by conviction: a pick that appears in several boards is filed under the
# FIRST (highest-conviction) category it shows up in.
BOARDS = [
    ("live_locks_status.json",     ["locks"],                          "locks",       "Locks"),
    ("alpha_pick_of_day.json",     ["top_5_alphas", "props_of_day"],   "alpha",       "Alpha"),
    ("bet_slate.json",             ["slate"],                          "slate",       "Bet Slate"),
    ("high_confidence_board.json", ["board"],                          "highconf",    "High-Conf"),
    ("best_bets.json",             ["bets"],                           "best",        "Best Bets"),
    ("consensus_picks.json",       ["top_15_hit_boost_consensus"],     "consensus",   "Consensus"),
    ("todays_top_plays.json",      ["top_25", "all_plays"],            "topplays",    "Top Plays"),
    ("convergence_alerts.json",    ["convergence"],                    "convergence", "Convergence"),
    ("fade_picks.json",            ["top_5_fades", "all_fades"],       "fade",        "Fades"),
]


def _load(fn):
    p = os.path.join(DATA_DIR, fn)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _first_list(d, keys):
    """First candidate key whose value is a non-empty list of dicts."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v
    return []


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _infer_sport(raw, subject, market):
    """best_bets / consensus entries carry no sport field -- infer it from the
    market/label instead of showing '?' on the public hub."""
    s = raw.get("sport") or raw.get("league")
    if s:
        return s
    blob = f"{subject} {market}".lower()
    if "lol" in blob or "kills" in blob:
        return "LOL"
    if "mls " in blob or blob.startswith("mls"):
        return "MLS"
    if blob.startswith("cs ") or "(bo3)" in blob or "(bo5)" in blob:
        return "CS"
    if any(k in blob for k in ("first inning", "first_inning", "yrfi", "nrfi",
                                "sgp", "1 plus hit", "1_plus_hit", "hit")):
        return "MLB"
    return "?"


def _norm(raw):
    """Map a board's pick (varied schemas) to the hub's common schema."""
    subject = (raw.get("player") or raw.get("batter") or raw.get("player_or_matchup")
               or raw.get("subject") or raw.get("name") or raw.get("matchup")
               or raw.get("title") or raw.get("label") or "?")
    _market = raw.get("market") or raw.get("play") or raw.get("type_label") or ""
    return {
        "sport": _infer_sport(raw, str(subject), str(_market)),
        "subject": str(subject),
        "matchup": raw.get("matchup") or "",
        "market": raw.get("market") or raw.get("play") or raw.get("type_label") or "",
        "prob": _num(raw.get("prob")) if _num(raw.get("prob")) is not None
                else _num(raw.get("p_calibrated")) if _num(raw.get("p_calibrated")) is not None
                else _num(raw.get("model_prob")),
        "fair_american": _num(raw.get("fair_american")) if _num(raw.get("fair_american")) is not None
                         else _num(raw.get("fair_odds")) if _num(raw.get("fair_odds")) is not None
                         else _num(raw.get("fair")),
        "edge_pct": _num(raw.get("edge_pct")),
        "tier": raw.get("tier") or raw.get("stars") or None,
    }


def build():
    picks = []
    seen = set()
    cat_counts = {}
    categories = []
    for fn, keys, cat, label in BOARDS:
        arr = _first_list(_load(fn), keys)
        n_added = 0
        for raw in arr:
            if not isinstance(raw, dict):
                continue
            p = _norm(raw)
            key = (p["sport"], p["subject"].lower(), str(p["market"]).lower())
            if key in seen:
                continue                       # same pick already filed under a higher-conviction board
            seen.add(key)
            p["category"] = cat
            p["category_label"] = label
            picks.append(p)
            n_added += 1
        cat_counts[cat] = n_added
        categories.append({"key": cat, "label": label, "n": n_added})
    # Highest model prob first; picks with no prob fall to the bottom.
    picks.sort(key=lambda p: (p["prob"] is None, -(p["prob"] or 0)))
    return {
        "generated_at": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "n_picks": len(picks),
        "by_category": cat_counts,
        "categories": [c for c in categories if c["n"] > 0],
        "all_categories": categories,
        "picks": picks,
        "method_note": ("Unified view of every curated pick board. Each pick is filed under "
                        "its highest-conviction category and de-duped across boards. Probabilities "
                        "are calibrated where the source provides them. Empty when no slate is live."),
    }


def run():
    payload = build()
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {OUT} | {p['n_picks']} picks across "
          f"{len(p['categories'])} live categories: "
          + ", ".join(f"{c['label']}={c['n']}" for c in p['categories']))
