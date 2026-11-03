"""
EdgeStat -- Tennis singles match-win prop (ATP/WTA).

First tennis module. Uses ELO ratings (updated continuously based on results)
to compute P(player_A wins). Surfaces edges vs book moneyline.

Method:
  P(A wins) = 1 / (1 + 10 ** ((elo_B - elo_A) / 400))
  Surface STRONG when our model probability differs from book ML by >= 5%.

Player ELO ratings: a HARD-CODED 2025 snapshot of ~50 ATP/WTA players (not
live, not updated by this module). Surface-specific adjustments: clay/grass/hard.

(2026-11-03) NO EDGE WITHOUT A BOOK PRICE. The old rule called a match
"STRONG" whenever the model favourite sat at 60-78%, measured against an
ASSUMED -120 book (54.5% breakeven) -- book_p_p1/p2 were always null, so every
"edge" was the model against a constant. Edge is now model p minus the real
book-implied p (de-vigged when both sides are present) and is None when there
is no book price; STRONG requires a real price and >= 5pp edge. In-progress
matches are excluded from the upcoming board.

Output: data/tennis_match_win_props.json
"""
from __future__ import annotations

import os
import json
import math
import datetime as dt
from typing import Any, Dict, List, Optional


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "tennis_match_win_props.json")

# 2025 ATP / WTA top ranked + ELO -- HARD-CODED snapshot (2026-11-03 label)
# ELO baseline 1500. Top players ~2000+. Lower ranked ~1600-1700.
ELO_SOURCE_LABEL = "hard-coded 2025 snapshot (~50 players), not live ratings"
MODEL_STATUS = "unvalidated model projection -- not a recommendation"
STRONG_EDGE_PP = 0.05   # vs a REAL book-implied probability only
PLAYER_ELO = {
    # ATP top 25
    "jannik sinner":         {"tour": "ATP", "elo": 2240, "clay_adj": -40, "grass_adj": -10, "hard_adj": 30},
    "carlos alcaraz":        {"tour": "ATP", "elo": 2230, "clay_adj": 30, "grass_adj": 40, "hard_adj": 0},
    "alexander zverev":      {"tour": "ATP", "elo": 2130, "clay_adj": 10, "grass_adj": -10, "hard_adj": 0},
    "daniil medvedev":       {"tour": "ATP", "elo": 2080, "clay_adj": -30, "grass_adj": 0, "hard_adj": 20},
    "novak djokovic":        {"tour": "ATP", "elo": 2180, "clay_adj": 0, "grass_adj": 10, "hard_adj": 20},
    "taylor fritz":          {"tour": "ATP", "elo": 2030, "clay_adj": -20, "grass_adj": 20, "hard_adj": 10},
    "casper ruud":           {"tour": "ATP", "elo": 2010, "clay_adj": 40, "grass_adj": -20, "hard_adj": -10},
    "andrey rublev":         {"tour": "ATP", "elo": 2020, "clay_adj": 10, "grass_adj": -10, "hard_adj": 0},
    "stefanos tsitsipas":    {"tour": "ATP", "elo": 1990, "clay_adj": 30, "grass_adj": -20, "hard_adj": 0},
    "alex de minaur":        {"tour": "ATP", "elo": 2000, "clay_adj": -10, "grass_adj": 10, "hard_adj": 10},
    "grigor dimitrov":       {"tour": "ATP", "elo": 1970, "clay_adj": 0, "grass_adj": 10, "hard_adj": 10},
    "hubert hurkacz":        {"tour": "ATP", "elo": 1970, "clay_adj": -20, "grass_adj": 30, "hard_adj": 10},
    "tommy paul":            {"tour": "ATP", "elo": 1960, "clay_adj": -10, "grass_adj": 10, "hard_adj": 10},
    "ben shelton":           {"tour": "ATP", "elo": 1950, "clay_adj": -20, "grass_adj": 0, "hard_adj": 10},
    "frances tiafoe":        {"tour": "ATP", "elo": 1940, "clay_adj": -10, "grass_adj": 0, "hard_adj": 0},
    "jack draper":           {"tour": "ATP", "elo": 1960, "clay_adj": 0, "grass_adj": 20, "hard_adj": 0},
    "ugo humbert":           {"tour": "ATP", "elo": 1930, "clay_adj": -10, "grass_adj": 10, "hard_adj": 0},
    "lorenzo musetti":       {"tour": "ATP", "elo": 1940, "clay_adj": 40, "grass_adj": -10, "hard_adj": -10},
    "holger rune":           {"tour": "ATP", "elo": 1950, "clay_adj": 20, "grass_adj": 0, "hard_adj": 0},
    "karen khachanov":       {"tour": "ATP", "elo": 1900, "clay_adj": 0, "grass_adj": 0, "hard_adj": 0},
    "alejandro davidovich fokina": {"tour": "ATP", "elo": 1870, "clay_adj": 10, "grass_adj": -10, "hard_adj": 0},
    "alexei popyrin":        {"tour": "ATP", "elo": 1880, "clay_adj": -10, "grass_adj": 0, "hard_adj": 10},
    "felix auger-aliassime": {"tour": "ATP", "elo": 1890, "clay_adj": 0, "grass_adj": 0, "hard_adj": 10},
    "sebastian baez":        {"tour": "ATP", "elo": 1860, "clay_adj": 30, "grass_adj": -20, "hard_adj": -10},
    "arthur fils":           {"tour": "ATP", "elo": 1890, "clay_adj": 10, "grass_adj": 0, "hard_adj": 0},
    # WTA top 25
    "aryna sabalenka":       {"tour": "WTA", "elo": 2160, "clay_adj": -10, "grass_adj": 20, "hard_adj": 20},
    "iga swiatek":           {"tour": "WTA", "elo": 2180, "clay_adj": 50, "grass_adj": -20, "hard_adj": 0},
    "coco gauff":            {"tour": "WTA", "elo": 2080, "clay_adj": 10, "grass_adj": -10, "hard_adj": 10},
    "elena rybakina":        {"tour": "WTA", "elo": 2070, "clay_adj": 0, "grass_adj": 30, "hard_adj": 10},
    "jasmine paolini":       {"tour": "WTA", "elo": 2020, "clay_adj": 20, "grass_adj": 10, "hard_adj": -10},
    "qinwen zheng":          {"tour": "WTA", "elo": 2050, "clay_adj": -10, "grass_adj": 0, "hard_adj": 20},
    "jessica pegula":        {"tour": "WTA", "elo": 2020, "clay_adj": -20, "grass_adj": 0, "hard_adj": 10},
    "barbora krejcikova":    {"tour": "WTA", "elo": 1990, "clay_adj": 20, "grass_adj": 30, "hard_adj": -10},
    "emma navarro":          {"tour": "WTA", "elo": 1990, "clay_adj": 0, "grass_adj": 0, "hard_adj": 10},
    "danielle collins":      {"tour": "WTA", "elo": 1980, "clay_adj": 0, "grass_adj": 0, "hard_adj": 0},
    "daria kasatkina":       {"tour": "WTA", "elo": 1960, "clay_adj": 30, "grass_adj": -10, "hard_adj": -10},
    "paula badosa":          {"tour": "WTA", "elo": 1970, "clay_adj": 10, "grass_adj": 0, "hard_adj": 10},
    "mirra andreeva":        {"tour": "WTA", "elo": 1990, "clay_adj": 30, "grass_adj": -10, "hard_adj": 0},
    "marketa vondrousova":   {"tour": "WTA", "elo": 1950, "clay_adj": 20, "grass_adj": 30, "hard_adj": -10},
    "diana shnaider":        {"tour": "WTA", "elo": 1960, "clay_adj": 10, "grass_adj": 0, "hard_adj": 0},
    "madison keys":          {"tour": "WTA", "elo": 1940, "clay_adj": -10, "grass_adj": 10, "hard_adj": 10},
    "elina svitolina":       {"tour": "WTA", "elo": 1950, "clay_adj": 20, "grass_adj": 10, "hard_adj": -10},
    "ons jabeur":            {"tour": "WTA", "elo": 1930, "clay_adj": 0, "grass_adj": 30, "hard_adj": -10},
    "amanda anisimova":      {"tour": "WTA", "elo": 1920, "clay_adj": 0, "grass_adj": 10, "hard_adj": 0},
    "anna kalinskaya":       {"tour": "WTA", "elo": 1910, "clay_adj": 10, "grass_adj": 0, "hard_adj": 0},
    "donna vekic":           {"tour": "WTA", "elo": 1880, "clay_adj": 0, "grass_adj": 10, "hard_adj": 0},
    "victoria azarenka":     {"tour": "WTA", "elo": 1880, "clay_adj": -10, "grass_adj": 0, "hard_adj": 10},
    "karolina muchova":      {"tour": "WTA", "elo": 1930, "clay_adj": 10, "grass_adj": 20, "hard_adj": 0},
    "yulia putintseva":      {"tour": "WTA", "elo": 1860, "clay_adj": 10, "grass_adj": 0, "hard_adj": -10},
    "elise mertens":         {"tour": "WTA", "elo": 1870, "clay_adj": 10, "grass_adj": -10, "hard_adj": 0},
}


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _american(p: float) -> Optional[int]:
    if p is None or p <= 0.005 or p >= 0.995: return None
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _player_elo(name: str, surface: str) -> Optional[int]:
    key = (name or "").lower().strip()
    info = PLAYER_ELO.get(key)
    if not info: return None
    base = info["elo"]
    adj = (info.get(f"{surface}_adj") or 0)
    return base + adj


def run() -> Dict[str, Any]:
    state = _load(os.path.join(DATA_DIR, "tennis_state.json"))
    matches = state.get("matches") or state.get("events") or []

    rows: List[Dict[str, Any]] = []

    for m in matches:
        status = (m.get("status") or m.get("state") or "").lower()
        if "final" in status or "complete" in status: continue
        # (2026-11-03) "upcoming" means not started: drop in-progress matches
        if status in ("in", "live", "in_progress", "in progress", "post") or \
           str(m.get("state") or "").lower() in ("in", "post"):
            continue
        p1_name = m.get("player1") or m.get("p1") or ""
        p2_name = m.get("player2") or m.get("p2") or ""
        if not p1_name or not p2_name: continue

        surface = (m.get("surface") or "hard").lower()
        if surface not in ("clay", "grass", "hard"): surface = "hard"

        elo_a = _player_elo(p1_name, surface)
        elo_b = _player_elo(p2_name, surface)
        if elo_a is None or elo_b is None: continue

        p_a_wins = 1.0 / (1 + 10 ** ((elo_b - elo_a) / 400))
        p_b_wins = 1 - p_a_wins

        # Book ML if provided (implied probabilities from a real sportsbook)
        book_p_a = m.get("book_p_player1") or m.get("book_p_p1")
        book_p_b = m.get("book_p_player2") or m.get("book_p_p2")

        # (2026-11-03) the assumed -120 book is gone from the edge math.
        # De-vig when both sides are priced; edge is None without a price.
        if book_p_a and book_p_b:
            tot = book_p_a + book_p_b
            fair_book_a, fair_book_b = book_p_a / tot, book_p_b / tot
        else:
            fair_book_a = book_p_a if book_p_a else None
            fair_book_b = book_p_b if book_p_b else None
        edge_p1 = round(p_a_wins - fair_book_a, 3) if fair_book_a else None
        edge_p2 = round(p_b_wins - fair_book_b, 3) if fair_book_b else None

        edge_class = "NO_BOOK_PRICE" if (edge_p1 is None and edge_p2 is None) else "NONE"
        best_market = None
        if edge_p1 is not None and edge_p1 >= STRONG_EDGE_PP:
            edge_class = "STRONG_A"
            best_market = {"market": "ML_PLAYER1", "p": round(p_a_wins, 3),
                           "book_p": round(fair_book_a, 3), "edge": edge_p1}
        elif edge_p2 is not None and edge_p2 >= STRONG_EDGE_PP:
            edge_class = "STRONG_B"
            best_market = {"market": "ML_PLAYER2", "p": round(p_b_wins, 3),
                           "book_p": round(fair_book_b, 3), "edge": edge_p2}

        rows.append({
            "matchup": f"{p1_name} vs {p2_name}",
            "surface": surface,
            "p1": p1_name,
            "p2": p2_name,
            "p1_elo": elo_a,
            "p2_elo": elo_b,
            "elo_diff": elo_a - elo_b,
            "p_p1_wins": round(p_a_wins, 3),
            "p_p2_wins": round(p_b_wins, 3),
            "fair_p1_odds": _american(p_a_wins),
            "fair_p2_odds": _american(p_b_wins),
            "book_p_p1": book_p_a,
            "book_p_p2": book_p_b,
            "edge_p1": edge_p1,
            "edge_p2": edge_p2,
            "edge_class": edge_class,
            "best_market": best_market,
        })

    rows.sort(key=lambda r: -max(r["p_p1_wins"], r["p_p2_wins"]))
    strong = [r for r in rows if r["edge_class"].startswith("STRONG")]

    out = {
        "generated_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "n_matches": len(rows),
        "n_strong_edges": len(strong),
        "n_players_in_db": len(PLAYER_ELO),
        "elo_source": ELO_SOURCE_LABEL,
        "model_status": MODEL_STATUS,
        "n_with_book_price": sum(1 for r in rows if r["edge_class"] != "NO_BOOK_PRICE"),
        "method_note": "P(win) = 1 / (1 + 10^((elo_opp - elo_player) / 400)) with surface adj, "
                       "ELO from a hard-coded 2025 snapshot. Edge = model p - real book-implied p "
                       "(de-vigged); None without a book price. STRONG only with a real price "
                       "and >= 5pp edge. In-progress matches excluded.",
        "rows": rows,
        "strong_edges": strong,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f: json.dump(out, f, indent=2)
    return out


if __name__ == "__main__":
    o = run()
    print(f"[tennis-ml] {o['n_matches']} upcoming matches, {o['n_with_book_price']} with a book price, "
          f"{o['n_strong_edges']} strong edges -> {OUT}")
