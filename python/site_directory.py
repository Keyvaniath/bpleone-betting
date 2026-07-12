"""
EdgeStat -- site directory + live-status map.

Brandon's ask: "clean the UI ... links to everything that work for LIVE data."
The nav was slimmed to 64 canonical links (2026-07-12 IA pass), which left ~60
pages reachable only by URL, and sports links don't tell you what's actually in
season -- clicking NFL in July lands on an empty hub.

This module emits data/site_directory.json:
  - sports: per-sport live status normalized from the *_state feeds (each feed
    has its own shape, so adapters live HERE, server-side, not in every page):
      { key, label, href, live (games today), n_today, next_date, status }
  - groups: every page on the site, grouped + labeled, with sport_key stamped
    where a live badge applies. directory.html renders it (the "Everything"
    page); nav.js decorates the Sports dropdown with live dots from it.

Redirect shims and the age-gated login are listed so the catalog is complete --
"everything" means everything -- but flagged so the directory can de-emphasize.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT = os.path.join(DATA_DIR, "site_directory.json")


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _count(d: Dict[str, Any], *keys: str) -> Optional[int]:
    """First present count field, else the length of the first list field."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, int):
            return v
    for k in ("games", "matches", "events", "races", "fights", "cards"):
        v = d.get(k)
        if isinstance(v, list):
            return len(v)
    return None


# Per-sport liveness adapters: feed file + how to read "today" from it.
# The espn_generic-powered feeds carry the honest today-only n_games_today +
# next_game_date (2026-07-12 fix); others are best-effort counts.
SPORTS: List[Dict[str, Any]] = [
    {"key": "mlb",    "label": "MLB",           "href": "mlb.html",      "feed": "mlb_game_cards.json", "count": ("n_games",)},
    {"key": "wnba",   "label": "WNBA",          "href": "wnba.html",     "feed": "wnba_state.json",     "count": ("n_games_today",)},
    {"key": "mls",    "label": "MLS",           "href": "mls.html",      "feed": "mls_state.json",      "count": ("n_games_today",)},
    {"key": "epl",    "label": "EPL",           "href": "epl.html",      "feed": "epl_state.json",      "count": ("n_games_today",)},
    {"key": "ucl",    "label": "UCL",           "href": "ucl.html",      "feed": "ucl_state.json",      "count": ("n_games_today",)},
    {"key": "kbo",    "label": "KBO",           "href": "kbo.html",      "feed": "kbo_state.json",      "count": ("n_games_today", "n_games")},
    {"key": "lol",    "label": "LoL",           "href": "lol.html",      "feed": "lol_state.json",      "count": ("n_matches_today", "n_matches")},
    {"key": "cs",     "label": "CS2",           "href": "cs.html",       "feed": "cs_state.json",       "count": ("n_games_today", "n_matches")},
    {"key": "tennis", "label": "Tennis",        "href": "tennis.html",   "feed": "tennis_state.json",   "count": ("n_games_today", "n_matches")},
    {"key": "golf",   "label": "Golf",          "href": "golf.html",     "feed": "golf_state.json",     "count": ("n_events", "n_players")},
    {"key": "ufc",    "label": "UFC",           "href": "ufc.html",      "feed": "ufc_state.json",      "count": ("n_fights_today", "n_fights")},
    {"key": "f1",     "label": "F1",            "href": "f1.html",       "feed": "f1_state.json",       "count": ("n_races_today", "n_races")},
    {"key": "worldcup","label": "World Cup 2026","href": "worldcup.html","feed": "worldcup_cards.json", "count": ("n_games_today", "n_matches")},
    {"key": "nba",    "label": "NBA",           "href": "nba.html",      "feed": "nba_state.json",      "count": ("n_games_today",)},
    {"key": "nhl",    "label": "NHL",           "href": "nhl.html",      "feed": "nhl_state.json",      "count": ("n_games_today",)},
    {"key": "nfl",    "label": "NFL",           "href": "nfl.html",      "feed": "nfl_state.json",      "count": ("n_games_today",)},
    {"key": "ncaaf",  "label": "NCAAF",         "href": "ncaaf.html",    "feed": "ncaaf_state.json",    "count": ("n_games_today",)},
    {"key": "ncaab",  "label": "NCAAB",         "href": "ncaab.html",    "feed": "ncaab_state.json",    "count": ("n_games_today",)},
    {"key": "cws",    "label": "NCAA Baseball", "href": "cws.html",      "feed": "cws_state.json",      "count": ("n_games_today",)},
]


def _sport_status(cfg: Dict[str, Any]) -> Dict[str, Any]:
    d = _load(cfg["feed"])
    n = _count(d, *cfg["count"])
    status = d.get("season_status") or d.get("status")
    next_date = d.get("next_game_date")
    live = bool(n and n > 0)
    return {
        "key": cfg["key"], "label": cfg["label"], "href": cfg["href"],
        "live": live, "n_today": n if n is not None else 0,
        "next_date": next_date, "status": status,
    }


# The complete page catalog. shim=True marks redirect stubs (kept for old links).
GROUPS: List[Dict[str, Any]] = [
    {"group": "Start Here", "pages": [
        {"href": "picks.html",        "label": "🎯 Today's Picks (all boards)"},
        {"href": "alpha-pick.html",   "label": "★ Alpha Pick of the Day"},
        {"href": "play-of-day.html",  "label": "★ Play of the Day"},
        {"href": "track-record.html", "label": "⟁ Track Record (the proof)"},
        {"href": "methodology.html",  "label": "📐 How it works"},
        {"href": "tonight.html",      "label": "🌙 Tonight"},
    ]},
    {"group": "Picks & Boards", "pages": [
        {"href": "high-confidence.html", "label": "💎 High-Confidence Board"},
        {"href": "best-bets.html",       "label": "✓ Best Bets"},
        {"href": "top-edges.html",       "label": "Top Calibrated Edges"},
        {"href": "alerts.html",          "label": "📡 The Tape (live signals)"},
        {"href": "alpha-scanner.html",   "label": "Cross-Sport Alpha Scanner"},
        {"href": "confluence.html",      "label": "Confluence Top-5"},
        {"href": "locks-of-day.html",    "label": "Locks of the Day"},
        {"href": "bet-slate.html",       "label": "Bet Slate"},
        {"href": "fade-picks.html",      "label": "Fade Picks", "shim": True},
        {"href": "todays-top-plays.html","label": "Top Plays", "shim": True},
        {"href": "top-3-picks.html",     "label": "Top 3", "shim": True},
        {"href": "consensus-picks.html", "label": "Consensus Picks"},
        {"href": "convergence.html",     "label": "Convergence", "shim": True},
    ]},
    {"group": "Parlays & DFS", "pages": [
        {"href": "cross-sport-parlays.html", "label": "🎰 Cross-Sport Parlays"},
        {"href": "props-parlay.html",        "label": "Props-Only Parlays"},
        {"href": "prizepicks-value.html",    "label": "🃏 PrizePicks Value"},
        {"href": "parlays.html",             "label": "Parlays"},
        {"href": "pickem.html",              "label": "Pick-Em"},
        {"href": "props.html",               "label": "Player Props"},
    ]},
    {"group": "Sports Hubs", "pages": [
        {"href": s["href"], "label": s["label"], "sport_key": s["key"]} for s in SPORTS
    ]},
    {"group": "Player Props by Sport", "pages": [
        {"href": "player.html",        "label": "MLB Player Search"},
        {"href": "nba-players.html",   "label": "NBA Players",  "sport_key": "nba"},
        {"href": "wnba-players.html",  "label": "WNBA Players", "sport_key": "wnba"},
        {"href": "nhl-players.html",   "label": "NHL Players",  "sport_key": "nhl"},
        {"href": "lol-players.html",   "label": "LoL Players",  "sport_key": "lol"},
        {"href": "cs-players.html",    "label": "CS Players",   "sport_key": "cs"},
        {"href": "kbo-players.html",   "label": "KBO Players",  "sport_key": "kbo"},
    ]},
    {"group": "Edges & Markets", "pages": [
        {"href": "book-edges.html",      "label": "📊 Book Edges"},
        {"href": "deep-edges.html",      "label": "🔬 Deep Edges"},
        {"href": "line-movement.html",   "label": "📈 Line Movement / Steam"},
        {"href": "line-shop.html",       "label": "💰 Line Shop"},
        {"href": "arbitrage.html",       "label": "Arbitrage"},
        {"href": "linemaker.html",       "label": "Linemaker"},
        {"href": "anomalies.html",       "label": "Anomalies"},
        {"href": "heat-map.html",        "label": "Heat Map (hot/cold)"},
        {"href": "hot-streaks.html",     "label": "Hot Streaks"},
        {"href": "ats-dashboard.html",   "label": "ATS Dashboard"},
        {"href": "nrfi.html",            "label": "NRFI"},
        {"href": "slate-player-pot.html","label": "Slate Player Pot"},
        {"href": "batter-sp-edges.html", "label": "Batter vs SP Edges"},
        {"href": "batter-splits.html",   "label": "Batter Splits"},
        {"href": "pitcher-matchup.html", "label": "⚾ Pitcher Matchup"},
        {"href": "b2b-fatigue.html",     "label": "B2B Fatigue"},
        {"href": "matchups.html",        "label": "Best Matchups"},
        {"href": "trends.html",          "label": "Trends"},
    ]},
    {"group": "Live", "pages": [
        {"href": "live-now.html",      "label": "Live Now"},
        {"href": "live.html",          "label": "MLB Live", "sport_key": "mlb"},
        {"href": "live-momentum.html", "label": "Live Momentum"},
        {"href": "golf-live.html",     "label": "Golf Live", "sport_key": "golf"},
    ]},
    {"group": "Proof & Performance", "pages": [
        {"href": "clv.html",             "label": "🎯 Closing Line Value"},
        {"href": "calibration-map.html", "label": "🎯 Model Calibration"},
        {"href": "strategy-sim.html",    "label": "🎛️ Strategy Simulator"},
        {"href": "proof.html",           "label": "The Proof Card"},
        {"href": "backtest.html",        "label": "Performance Analytics (CLV & drawdown)"},
        {"href": "backtest-dashboard.html", "label": "Backtest Dashboard"},
        {"href": "backtest-replayer.html",  "label": "Backtest Replayer"},
        {"href": "pod-history.html",     "label": "POD History"},
        {"href": "accuracy.html",        "label": "Accuracy"},
        {"href": "audit.html",           "label": "Audit"},
        {"href": "module-performance.html", "label": "Module Performance"},
        {"href": "lifecycle.html",       "label": "Lifecycle"},
        {"href": "worldcup.html",        "label": "World Cup Model", "sport_key": "worldcup"},
    ]},
    {"group": "Models & Lab", "pages": [
        {"href": "ml-lab.html",           "label": "ML Lab"},
        {"href": "models.html",           "label": "Models"},
        {"href": "model-cards.html",      "label": "Model Cards"},
        {"href": "model-health.html",     "label": "🏥 Model Health"},
        {"href": "model-control.html",    "label": "Model Control"},
        {"href": "research.html",         "label": "Research"},
        {"href": "residuals.html",        "label": "Residuals"},
        {"href": "simulator.html",        "label": "Simulator"},
        {"href": "reliability.html",      "label": "Esports Calibration"},
        {"href": "live-learning.html",    "label": "📡 Live Learning (hub)"},
        {"href": "learning-integrity.html","label": "Learning Integrity"},
        {"href": "learning.html",         "label": "Learning", "shim": True},
        {"href": "training.html",         "label": "Training", "shim": True},
        {"href": "self-learning.html",    "label": "Self-Learning", "shim": True},
    ]},
    {"group": "Account & Tools", "pages": [
        {"href": "support.html",     "label": "♥ Support / Tip"},
        {"href": "pricing.html",     "label": "⭐ Pricing / Go Pro"},
        {"href": "sportsbooks.html", "label": "🎟 Where to Bet"},
        {"href": "bankroll.html",    "label": "Bankroll"},
        {"href": "my-bets.html",     "label": "My Bets"},
        {"href": "hedge.html",       "label": "Hedge Calculator"},
        {"href": "login.html",       "label": "Sign In (accounts launching)"},
        {"href": "config.html",      "label": "Config (operator)"},
    ]},
    {"group": "System & Data", "pages": [
        {"href": "status.html",         "label": "🟢 System Status"},
        {"href": "data-health.html",    "label": "📡 Data Health"},
        {"href": "data-integrity.html", "label": "🔍 Data Integrity"},
        {"href": "data-sources.html",   "label": "🗂 Data Sources"},
        {"href": "sport-coverage.html", "label": "🌐 Sport Coverage"},
        {"href": "pulse.html",          "label": "Pulse"},
    ]},
    {"group": "Daily Reads & Learn", "pages": [
        {"href": "todays-brief.html",   "label": "📋 Today's Master Brief"},
        {"href": "daily-summary.html",  "label": "Daily Summary"},
        {"href": "brief.html",          "label": "Brief"},
        {"href": "train-your-read.html","label": "🎯 Train Your Read"},
        {"href": "learn.html",          "label": "🎓 EdgeStat Academy"},
        {"href": "about.html",          "label": "About"},
    ]},
    {"group": "Legal & Trust", "pages": [
        {"href": "responsible-gambling.html", "label": "🛟 Responsible Gambling"},
        {"href": "terms.html",                "label": "Terms of Service"},
        {"href": "privacy.html",              "label": "Privacy Policy"},
        {"href": "disclaimer.html",           "label": "Disclaimer"},
        {"href": "affiliate-disclosure.html", "label": "Affiliate Disclosure"},
    ]},
]


def run() -> Dict[str, Any]:
    sports = [_sport_status(cfg) for cfg in SPORTS]
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "sports": sports,
        "n_live_sports": sum(1 for s in sports if s["live"]),
        "groups": GROUPS,
        "n_pages": sum(len(g["pages"]) for g in GROUPS),
        "note": ("Live status is normalized from each sport's state feed (today-only "
                 "counts where the feed supports it). directory.html renders this; "
                 "nav.js uses `sports` to badge the Sports menu."),
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return payload


if __name__ == "__main__":
    p = run()
    live = [s["label"] for s in p["sports"] if s["live"]]
    print(f"[site-directory] {p['n_pages']} pages in {len(p['groups'])} groups; "
          f"{p['n_live_sports']} live sports: {', '.join(live)}")
