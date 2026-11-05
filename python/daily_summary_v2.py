"""
EdgeStat -- daily summary digest v2.

Markdown brief that includes EVERYTHING actionable:
  - Today's slate count per sport
  - Top 5 picks (across all sources)
  - Player POT (cross-sport)
  - Pre-game alerts (HIGH conviction only)
  - Heat/cold flags
  - Anomaly detector flags
  - Multi-sport regime (HOME_FAV / ROAD_DOG day)
  - Portfolio recommendation
  - Self-training summary

Output: data/daily_summary_v2.md + data/daily_summary_v2.json
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


def _fmtv(v, spec, dflt="?"):
    """Display-safe format (2026-10-26): `{x.get(k, d):spec}` crashes when the
    key exists with None -- .get's default only applies to a MISSING key --
    and a display print must never fail the module (the 30-day cascade
    started exactly this way)."""
    if v is None:
        return str(dflt)
    try:
        return format(v, spec)
    except (TypeError, ValueError):
        return str(v)


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MD_OUT = os.path.join(DATA_DIR, "daily_summary_v2.md")
JSON_OUT = os.path.join(DATA_DIR, "daily_summary_v2.json")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def _mlb_offseason() -> bool:
    """(2026-11-03) today.json is the MLB board; no_games / no games = offseason."""
    t = _load(os.path.join(DATA_DIR, "today.json"))
    return bool(t.get("no_games")) or not (t.get("games") or [])


def _golf_live_or_done() -> bool:
    """(2026-11-03) Golf finish positions are real only once the event has
    started or finished -- a Scheduled event has no leaderboard."""
    t = (_load(os.path.join(DATA_DIR, "golf_state.json")).get("active_tournament") or {})
    return bool(t.get("is_in_progress") or t.get("is_complete"))


PROJ = "model projection — unvalidated, no sportsbook price, not a recommendation"


def run() -> Dict[str, Any]:
    now = dt.datetime.now()
    date = now.date().isoformat()
    lines = [f"# EdgeStat Daily Summary — {date}", ""]

    # Model health score (one-glance)
    mh = _load(os.path.join(DATA_DIR, "model_health.json"))
    if mh:
        lines.append(f"## 🏥 Model Health: {mh.get('total_score',0)}/100 [{mh.get('tier','?')}]")
        lines.append(f"- {mh.get('interpretation','?')}")
        comps = mh.get("components") or {}
        for name, c in comps.items():
            score = (c.get("score") or 0)
            indicator = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
            lines.append(f"  - {indicator} {name.replace('_',' ').title()}: {score}/100")
        lines.append("")

    # Multi-sport regime
    msc = _load(os.path.join(DATA_DIR, "multi_sport_correlation.json"))
    if msc:
        lines.append(f"## 🌐 Slate Overview")
        lines.append(f"- **Regime today:** {msc.get('regime_label', 'BALANCED')} (avg P(home)={msc.get('regime_avg_phome', 0.5)})")
        lines.append(f"- **Total games on board:** {msc.get('n_games_today_total', 0)}")
        lines.append(f"- **Strong home favorites:** {msc.get('n_strong_home_favs', 0)} | **Strong road dogs:** {msc.get('n_strong_road_dogs', 0)}")
        lines.append("")

    # Top 5 best bets
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    bets = bb.get("bets") or []
    # (2026-11-03) best_bets.json is fail-closed upstream: only DK-priced rows.
    lines.append("## 🎯 Best Bets (sportsbook-priced only)")
    if bets:
        for b in bets[:5]:
            stars = "★" * (b.get("stars") or 0)
            lines.append(f"{b.get('rank',0)}. **{b.get('label','')}** ({b.get('quality_score',0)}/100 {stars})")
    else:
        exc = bb.get("excluded_unpriced") or {}
        n_exc = sum(exc.values())
        by = ", ".join(f"{k} {v}" for k, v in sorted(exc.items(), key=lambda kv: -kv[1]))
        lines.append(f"- No best bet today: a best bet needs a real sportsbook price"
                     + (f" — {n_exc} model-only projections excluded ({by})." if n_exc else "."))
    lines.append("")

    # Whale picks (max-confluence signal)
    whales = _load(os.path.join(DATA_DIR, "whale_picks.json"))
    top_whales = [w for w in (whales.get("whales") or [])
                    if w.get("tier") in ("WHALE", "STRONG")][:6]
    if top_whales:
        # (2026-11-03) model-only: no edge vs an assumed/own price, no tier-as-pick.
        lines.append(f"## 🐋 Signal Confluence — {PROJ}")
        for w in top_whales:
            lines.append(f"- **[{w.get('sport')}]** {w.get('player_or_matchup')} "
                          f"{w.get('market')} -- model {(w.get('prob') or 0)*100:.0f}% "
                          f"(confluence score {_fmtv(w.get('confluence_score'), '.1f', 0)})")
        lines.append("")

    # Sharp action signals
    sharp = _load(os.path.join(DATA_DIR, "sharp_action_radar.json"))
    pos = (sharp.get("positive_signals") or [])[:5]
    if pos:
        lines.append("## 📡 Line Moved (opening vs latest; not a read on who bet)")  # (2026-11-03)
        for s in pos:
            lines.append(f"- [{s.get('intensity')}] **{s.get('matchup')}** {s.get('market')}: "
                          f"{s.get('opening_implied_pct')}% → {s.get('latest_implied_pct')}% (+{_fmtv(s.get('shift_pp'), '.1f', 0)}pp)")
        lines.append("")

    # Strong unders
    unders = _load(os.path.join(DATA_DIR, "mlb_unders_alerts.json"))
    strong_u = (unders.get("strong_unders") or [])[:5]
    if strong_u:
        lines.append(f"## 📉 Model total below market — {PROJ}")  # (2026-11-03)
        for u in strong_u:
            lines.append(f"- [{u.get('tier')} {_fmtv(u.get('under_signal_score'), '.1f', 0)}] **{u.get('matchup')}** "
                          f"model {u.get('model_fair_total')} vs market {u.get('market_total')}")
        lines.append("")

    # Locks of the Day -- Brandon's track record + today's locks
    locks = _load(os.path.join(DATA_DIR, "locks_history.json"))
    if locks:
        total = (locks.get("total_locks") or 0)
        wins = (locks.get("wins") or 0)
        losses = (locks.get("losses") or 0)
        hit_rate = locks.get("hit_rate")
        net = (locks.get("net_units") or 0)
        roi = locks.get("roi_pct")
        l7 = locks.get("last_7_days") or {}
        # (2026-11-03) Lead with SPORTSBOOK-priced locks. 307 of the all-time
        # wins are PrizePicks props graded at the venue break-even (unverified).
        bp = locks.get("by_price") or {}
        sb = bp.get("sportsbook") or {}
        pp = bp.get("prizepicks_unverified") or {}
        lines.append("## 🔒 Locks of the Day -- Track Record")
        if sb.get("n_settled"):
            lines.append(f"- Sportsbook-priced: **{sb.get('wins',0)}-{sb.get('losses',0)}** "
                          f"(n={sb['n_settled']}; net {_fmtv(sb.get('net_units'), '+.2f', 0)}u, "
                          f"ROI {_fmtv(sb.get('roi_pct'), '+.1f', 0)}%)"
                          + (" -- too few to judge" if sb["n_settled"] < 30 else ""))
        else:
            lines.append("- Sportsbook-priced: no settled locks yet")
        if pp.get("n_settled"):
            lines.append(f"- PrizePicks (unverified, venue break-even, feed dark since 2026-07-09): "
                          f"{pp.get('wins',0)}-{pp.get('losses',0)} -- not a sportsbook record")
        if not bp and hit_rate is not None:
            lines.append(f"- All-time (mixed sportsbook + PrizePicks): {wins}-{losses}")
        if l7.get("hit_rate") is not None:
            lines.append(f"- Last 7d: {l7.get('wins',0)}-{l7.get('losses',0)} ({(l7['hit_rate']*100):.1f}%) | net {_fmtv(l7.get('net_units'), '+.2f', 0)}u")
        todays = locks.get("todays_locks") or []
        if todays:
            lines.append(f"\n**Today's {len(todays)} Locks:**")
            for L in todays:
                lines.append(f"- [{L.get('sport','?')}] **{(L.get('player_or_matchup') or '?')[:30]}** {(L.get('market') or '?')[:30]} · p={(L.get('prob') or 0)*100:.0f}%")  # (2026-11-03) no edge/stake
        lines.append("")

    # Cross-sport parlay recommendations
    # (2026-11-03) Parlays are never recommended by default and never carry a
    # stake or EV -- the section is removed from the brief.
    balanced = []
    if balanced:
        lines.append(f"## 🎰 Top Balanced 2-Leg Parlays (40-65% joint)")
        for p in balanced[:3]:
            legs_str = " + ".join([f"[{L['sport']}] {L['player_or_matchup'][:25]} {L['market'][:20]}" for L in p['legs']])
            lines.append(f"- {legs_str}")
            lines.append(f"  Joint: {p['joint_prob']*100:.0f}% | Fair: {p['fair_parlay_american']} | Edge: +{p['edge_pct']:.1f}%")
        lines.append("")

    # Player POT
    ppot = _load(os.path.join(DATA_DIR, "player_pot.json"))
    top5_players = ppot.get("top_5") or []
    if top5_players:
        lines.append(f"## 🎮 Player projections (cross-sport) — {PROJ}")  # (2026-11-03)
        for p in top5_players[:5]:
            lines.append(f"- **[{p.get('sport','?')}]** {p.get('label','')} · model {(p.get('prob') or 0)*100:.1f}%")
        lines.append("")

    # Pre-game alerts (HIGH conviction)
    pre = _load(os.path.join(DATA_DIR, "pregame_alerts.json"))
    # (2026-11-03) pregame_alerts now emits only desk-verdict rows with a DK price.
    high_pre = [a for a in (pre.get("alerts") or []) if a.get("dk_american") is not None]
    if high_pre:
        lines.append(f"## ⚡ Pre-Game (game-lines desk, DK priced) ({len(high_pre)})")
        for a in high_pre[:10]:
            lines.append(f"- [{a['sport']}] **{a['team']}** {a['side']} · model {a['p_pick_side']*100:.1f}% · DK {a['dk_american']:+d} ({a.get('desk_verdict','')})")
        lines.append("")
    elif pre.get("note"):
        lines.append("## ⚡ Pre-Game")
        lines.append(f"- {pre['note']}")
        lines.append("")

    # Heat/cold alerts
    hc = _load(os.path.join(DATA_DIR, "heat_cold_alerts.json"))
    bt = hc.get("by_type") or {}
    if hc.get("alerts"):
        lines.append(f"## 🔥/❄️ Heat / Cold Signals")
        lines.append(f"- Hot teams: **{bt.get('TEAM_HOT', 0)}** | Cold teams: **{bt.get('TEAM_COLD', 0)}** | Over-heavy: {bt.get('TEAM_HIGH_OVER', 0)} | Under-heavy: {bt.get('TEAM_LOW_OVER', 0)}")
        lines.append(f"- Heating-up players: **{bt.get('PLAYER_HEATING_UP', 0)}** | Cooling-down: {bt.get('PLAYER_COOLING_DOWN', 0)}")
        lines.append("")

    # Anomaly alerts
    anom = _load(os.path.join(DATA_DIR, "anomaly_alerts.json"))
    if anom.get("alerts"):
        lines.append(f"## ⚠️ Anomaly Detector ({anom.get('n_alerts', 0)})")
        for t, n in (anom.get("by_type") or {}).items():
            lines.append(f"- {t}: **{n}**")
        # Show top 5 anomalies
        for a in anom["alerts"][:5]:
            lines.append(f"  - {a['team']} ({a['sport']}): {a['detail']}")
        lines.append("")

    # Portfolio
    pf = _load(os.path.join(DATA_DIR, "portfolio_today.json"))
    # (2026-11-03) sized only at actionable DK quotes (multi_sport_portfolio.py)
    if pf.get("picks"):
        lines.append(f"## 💰 Today's Portfolio ({pf.get('n_picks', 0)} DK-priced picks)")
        lines.append(f"- Total stake: **${pf.get('total_stake_dollars', 0)}** ({pf.get('total_stake_pct', 0)}% of $1000 bankroll)")
        lines.append(f"- Expected EV at DK prices: **${pf.get('expected_pl', 0)}**")
        for p in (pf.get("picks") or [])[:5]:
            lines.append(f"  - #{p['rank']} [{p['sport']}] ${p['stake_dollars']:.0f} on {(p.get('label') or '')[:60]} "
                          f"@ DK {p['book_american']:+d} (observed {p.get('observed_at')}; P={p['model_prob']*100:.0f}%)")
        lines.append("")
    elif pf:
        lines.append("## 💰 Today's Portfolio")
        lines.append("- No priced picks: a stake is sized only at an actionable DraftKings quote.")
        lines.append("")

    # Convergence picks (multi-signal stacked)
    conv = _load(os.path.join(DATA_DIR, "convergence_alerts.json"))
    if conv.get("convergence"):
        # (2026-11-03) signal counts, not picks: no tier labels as recommendations
        lines.append(f"## 🎯 Signal stacking ({conv.get('n_games_with_2plus_signals',0)} games with 2+ signals) — research, not picks")
        for c in conv.get("convergence", [])[:5]:
            sigs = ", ".join(s.get("type","?") for s in c.get("signals",[])[:4])
            lines.append(f"  - {c['matchup']} : {c['n_signals']} signals ({sigs})")
        lines.append("")

    # MLB pitcher matchup K plays
    pm = _load(os.path.join(DATA_DIR, "mlb_pitcher_matchup.json"))
    if pm.get("matchups") and not _mlb_offseason():  # (2026-11-03) offseason: suppressed
        plays = [m["best_k_play"] for m in pm["matchups"] if m.get("best_k_play")]
        plays.sort(key=lambda p: -(p.get("p_over") or 0))
        if plays:
            lines.append(f"## ⚾ MLB Pitcher K projections ({len(plays)}) — {PROJ}")
            for p in plays[:5]:
                lines.append(f"- **{p['pitcher']}** OVER {p['line']} K (model {p['p_over']*100:.0f}%)")
            lines.append("")

    # NBA player heat (L5 vs season splits)
    nh = _load(os.path.join(DATA_DIR, "nba_player_heat.json"))
    if (nh.get("n_hot") or 0) > 0 or (nh.get("n_cold") or 0) > 0:
        lines.append(f"## 🏀 NBA Player Heat ({nh.get('n_hot',0)} HOT / {nh.get('n_cold',0)} COLD)")
        for a in (nh.get("hot_players") or [])[:5]:
            sig = ", ".join(a.get("signals") or [])
            lines.append(f"  - 🔥 **{a['name']}** ({a['team_abbr']}): L5 {a['l5_pts']:.1f}/{a['l5_reb']:.1f}/{a['l5_ast']:.1f} vs season {a['season_pts']:.1f}/{a['season_reb']:.1f}/{a['season_ast']:.1f} [{sig}]")
        for a in (nh.get("cold_players") or [])[:3]:
            sig = ", ".join(a.get("signals") or [])
            lines.append(f"  - ❄️ **{a['name']}** ({a['team_abbr']}): L5 {a['l5_pts']:.1f} vs season {a['season_pts']:.1f} [{sig}]")  # (2026-11-03) no fade advice
        lines.append("")

    # UFC fight matchup
    uf = _load(os.path.join(DATA_DIR, "ufc_matchup.json"))
    if (uf.get("n_fights") or 0) > 0:
        lines.append(f"## 🥊 UFC Fight Matchups ({uf.get('next_event','?')}) — {PROJ}")  # (2026-11-03)
        for f in (uf.get("fights") or [])[:5]:
            lines.append(f"  - model favourite **{f['favorite']}** ({f.get('record_a' if f['favorite']==f['fighter_a'] else 'record_b')}) vs {f['underdog']}")
        lines.append("")

    # Golf player heat
    gh = _load(os.path.join(DATA_DIR, "golf_player_heat.json"))
    if (gh.get("n_hot") or 0) > 0 and _golf_live_or_done():  # (2026-11-03) no "finished T1" for a Scheduled event
        lines.append(f"## ⛳ Golf Player Heat (from {gh.get('source_tournament','last event')})")
        for a in (gh.get("hot_players") or [])[:5]:
            sig = " · ".join(a.get("signals") or [])
            lines.append(f"  - 🔥 T{a['finish_pos']} **{a['name']}** ({a.get('country')}): {a['total_to_par']:+d} total -- {sig}")
        for a in (gh.get("cold_players") or [])[:3]:
            sig = " · ".join(a.get("signals") or [])
            lines.append(f"  - ❄️ **{a['name']}** ({a.get('country')}): {sig}")
        lines.append("")

    # MLB batter heat (L14 vs season splits)
    bh = _load(os.path.join(DATA_DIR, "mlb_batter_heat.json"))
    if ((bh.get("n_hot") or 0) > 0 or (bh.get("n_cold") or 0) > 0) and not _mlb_offseason():  # (2026-11-03)
        lines.append(f"## 🔥 MLB Batter Heat ({bh.get('n_hot',0)} HOT / {bh.get('n_cold',0)} COLD)")
        for a in (bh.get("hot_batters") or [])[:5]:
            lines.append(f"  - 🔥 **{a['name']}** ({a['team']}): L14 .{a['l14_avg']*1000:03.0f} / season .{a['season_avg']*1000:03.0f} (+{a['delta_pp']:.0f}pts)")
        for a in (bh.get("cold_batters") or [])[:5]:
            lines.append(f"  - ❄️ **{a['name']}** ({a['team']}): L14 .{a['l14_avg']*1000:03.0f} / season .{a['season_avg']*1000:03.0f} ({a['delta_pp']:.0f}pts)")
        lines.append("")

    # B2B fatigue alerts
    b2b = _load(os.path.join(DATA_DIR, "b2b_fatigue.json"))
    if (b2b.get("n_fatigued_games_today") or 0) > 0:
        lines.append(f"## 😴 Back-to-back flags ({b2b['n_fatigued_games_today']}) — schedule fact, not a pick")  # (2026-11-03)
        for sport, alerts in (b2b.get("by_sport") or {}).items():
            for a in (alerts or [])[:3]:
                if a.get("fatigue_edge") in ("HOME", "AWAY"):
                    lines.append(f"- [{sport.upper()}] {a.get('matchup','')} ({a.get('game_date','')}): "
                                 f"{(a.get('fatigue_edge') or '').lower()} team on a back-to-back")
        lines.append("")

    # Streak regression
    sr = _load(os.path.join(DATA_DIR, "streak_regression.json"))
    if (sr.get("n_alerts") or 0) > 0:
        lines.append(f"## 📈 Streaks ({sr['n_alerts']}) — record facts, not picks")  # (2026-11-03) no FADE advice
        for a in sr.get("alerts", [])[:5]:
            lines.append(f"- [{a['sport']}] {a['team']} on {a['streak']} L10 {a.get('l10','?')}")
        lines.append("")

    # Walk-forward trajectory (is each market improving over time?)
    wf = _load(os.path.join(DATA_DIR, "walk_forward.json"))
    if wf.get("summary"):
        s = wf["summary"]
        n_imp = len(s.get("improving", []))
        n_deg = len(s.get("degrading", []))
        n_flat = len(s.get("flat", []))
        lines.append(f"## 📉 Walk-Forward Trajectory (n_windows={wf.get('window_days',3)}d × {len(wf.get('by_market',{}))} markets)")
        lines.append(f"- 📈 Improving: **{n_imp}** · ➖ Flat: {n_flat} · 📉 Degrading: **{n_deg}**")
        for m in s.get("improving", [])[:3]:
            lines.append(f"  - ✅ {m['market']} (Brier Δ {_fmtv(m.get('brier_delta'), '+.4f')})")
        for m in s.get("degrading", [])[:3]:
            lines.append(f"  - ⚠️ {m['market']} (Brier Δ {_fmtv(m.get('brier_delta'), '+.4f')})")
        lines.append("")

    # Training convergence (per-market learning trajectory)
    tc = _load(os.path.join(DATA_DIR, "training_convergence.json"))
    if tc.get("markets"):
        ts = tc.get("tier_summary") or {}
        lines.append(f"## 🧠 Training Convergence")
        lines.append(f"- ELITE: **{ts.get('ELITE',0)}** · HEALTHY: {ts.get('HEALTHY',0)} · OK: {ts.get('OK',0)} · DEGRADED: **{ts.get('DEGRADED',0)}**")
        # Surface divergent markets
        divergent = [m for m in tc["markets"] if m.get("directional_bias")]
        if divergent:
            for m in divergent[:3]:
                lines.append(f"  - ⚠️ **{m['market']}**: {m['verdict']} (cf={m.get('latest_correction_factor')})")
        lines.append("")

    # Self-training summary
    st = _load(os.path.join(DATA_DIR, "self_training_summary.json"))
    if st.get("by_sport"):
        lines.append(f"## 🤖 Self-Training Status")
        for sport, info in st["by_sport"].items():
            n = (info.get("n_games") or 0)
            hr = info.get("hit_rate")
            bias = info.get("bias")
            applied = info.get("recommendation_applied")
            applied_tag = " [calibration applied]" if applied else ""
            if hr is not None:
                lines.append(f"- **{sport.upper()}**: n={n} games · hit rate {hr*100:.1f}% · bias {(bias or 0)*100:+.1f}pp{applied_tag}")
        lines.append("")

    text = "\n".join(lines)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MD_OUT, "w", encoding="utf-8") as f:
        f.write(text)

    n_sections = text.count("\n## ")
    payload = {
        "generated_at": now.isoformat(timespec="seconds"),
        "date": date,
        "n_sections": n_sections,
        "n_chars": len(text),
        "md_path": "data/daily_summary_v2.md",
    }
    with open(JSON_OUT, "w") as f: json.dump(payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Daily summary v2: {p['n_sections']} sections, {p['n_chars']} chars")
