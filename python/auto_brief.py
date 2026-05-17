"""
EdgeStat -- auto-narrative slate brief generator.

Produces a tight, plain-English summary of tonight's slate that Brandon
can skim in 30 seconds. Pulls from every model + slate-confidence + best_bets
+ alerts. Includes specific play recommendations with rationale.

Output: data/auto_brief.md  (Markdown, also rendered on /brief)
"""
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "auto_brief.md")


def _load(p):
    if not os.path.exists(p): return {}
    try:
        with open(p) as f: return json.load(f)
    except Exception: return {}


def run() -> Dict[str, Any]:
    today = _load(os.path.join(DATA_DIR, "today.json"))
    bb = _load(os.path.join(DATA_DIR, "best_bets.json"))
    slate = _load(os.path.join(DATA_DIR, "slate_confidence.json"))
    fatigue = _load(os.path.join(DATA_DIR, "pitcher_fatigue.json"))
    wx = _load(os.path.join(DATA_DIR, "weather_conditional.json"))
    sgps = _load(os.path.join(DATA_DIR, "sgps.json"))
    bullpen = _load(os.path.join(DATA_DIR, "bullpen_alert.json"))
    nrfi = _load(os.path.join(DATA_DIR, "nrfi.json"))
    hot = _load(os.path.join(DATA_DIR, "hot_streaks.json"))
    arb = _load(os.path.join(DATA_DIR, "cross_book_arb.json"))
    traps = _load(os.path.join(DATA_DIR, "trap_alerts.json"))
    portfolio = _load(os.path.join(DATA_DIR, "portfolio.json"))
    bankroll_sim = _load(os.path.join(DATA_DIR, "bankroll_sim.json"))

    date = (today.get("generated_at") or "")[:10] or dt.date.today().isoformat()
    games = today.get("games") or []
    bets = bb.get("bets") or []

    lines = []
    lines.append(f"# Tonight's Slate Brief — {date}")
    lines.append("")

    # Headline: slate confidence
    if slate:
        tier = (slate.get("tier") or "?").upper()
        score = slate.get("score")
        rec = slate.get("recommendation", "")
        lines.append(f"## Slate Quality: {score}/100 ({tier})")
        lines.append(f"_{slate.get('summary', '')}_")
        lines.append(f"**Recommendation:** {rec}")
        lines.append("")

    # Slate at a glance
    lines.append(f"## Slate")
    lines.append(f"- **{len(games)} games** scheduled")
    if bb.get("by_source"):
        bs = bb["by_source"]
        lines.append(f"- **{len(bets)} best bets** scored: {bs.get('DK',0)} DK · {bs.get('PP',0)} PP · {bs.get('NRFI',0)} NRFI · {bs.get('SGP',0)} SGP")
    if portfolio.get("n_picked"):
        lines.append(f"- **Auto-portfolio:** {portfolio['n_picked']} picks, ${portfolio['total_stake']} stake ({portfolio['stake_pct_of_bankroll']}%), expected +${portfolio['expected_pl']}")
    if bankroll_sim.get("expected_pl") is not None:
        bs = bankroll_sim
        p = bs.get("percentiles") or {}
        lines.append(f"- **MC simulation:** EV +${bs.get('expected_pl')}, {(bs.get('p_profit',0)*100):.0f}% P(profit), p05 ${p.get('p05')} / p95 ${p.get('p95')}")
    lines.append("")

    # Top 5 best bets
    if bets:
        lines.append("## Top 5 Best Bets")
        for b in bets[:5]:
            stars = "*" * (b.get("stars") or 0)
            edge = b.get("edge_pct")
            edge_str = f"+{edge:.1f}%" if isinstance(edge, (int, float)) else "—"
            lines.append(f"{b.get('rank')}. **{b.get('label')}**  ({b.get('quality_score')}/100 {stars}, edge {edge_str})")
            for f in (b.get("factors") or [])[:2]:
                lines.append(f"   - {f}")
        lines.append("")

    # Trap warnings
    trap_list = traps.get("traps") or []
    if trap_list:
        lines.append(f"## ⚠️ Trap Warnings — {len(trap_list)} flagged")
        for t in trap_list[:5]:
            lines.append(f"- **{t['label']}** ({t['severity']}):")
            for fl in t["flags"][:2]:
                lines.append(f"   - {fl}")
        lines.append("")

    # Pitcher fatigue
    if fatigue.get("high_risk"):
        lines.append(f"## SP early-hook risk")
        lines.append(f"HIGH risk: {', '.join(fatigue['high_risk'][:6])}")
        lines.append(f"_Fade their K OVERs; lean OPP team total OVER and F5._")
        lines.append("")

    # Weather notable
    over_wx = (wx.get("over_lean_games") or [])
    under_wx = (wx.get("under_lean_games") or [])
    if over_wx or under_wx:
        lines.append(f"## Weather leans")
        if over_wx:
            lines.append(f"- **OVER lean** (wind out + warm): {', '.join(over_wx[:5])}")
        if under_wx:
            lines.append(f"- **UNDER lean** (wind in + cold): {', '.join(under_wx[:5])}")
        lines.append("")

    # Hot streaks
    if hot.get("hot_batters"):
        lines.append("## Hot streaks")
        hot_b = hot["hot_batters"][:3]
        b_parts = []
        for b in hot_b:
            b_parts.append("{name} (heat {heat:+.2f})".format(name=b['name'], heat=b['heat']))
        lines.append("**Batters heating up:** " + ", ".join(b_parts))
        if hot.get("hot_pitchers"):
            hot_p = hot["hot_pitchers"][:3]
            p_parts = []
            for pp in hot_p:
                p_parts.append("{name} (heat {heat:+.2f})".format(name=pp['name'], heat=pp['heat']))
            lines.append("**Pitchers on a run:** " + ", ".join(p_parts))
        lines.append("")

    # SGP suggestions
    sgp_games = sgps.get("by_game") or []
    if sgp_games:
        lines.append(f"## Top correlation-aware SGPs")
        for g in sgp_games[:3]:
            top = (g.get("suggestions") or [None])[0]
            if not top: continue
            lines.append(f"- **{g['matchup']}** {top['n_legs']}-leg @ {top['fair_american']:+d} fair (joint {top['joint_prob']:.2f}, EV +{top['ev_pct']}%)")
            for l in (top.get("legs") or [])[:3]:
                lines.append(f"   - {l['label']}")
        lines.append("")

    # Bullpen state
    if bullpen.get("gassed_teams"):
        gassed = [t for t in bullpen["gassed_teams"] if len(t) > 3]   # filter abbrevs
        if gassed:
            lines.append(f"## Bullpens GASSED tonight")
            lines.append(f"{', '.join(gassed[:8])}")
            lines.append(f"_Lean late-inning OVER on these games; fade their save situations._")
            lines.append("")

    # NRFI leans
    nrfi_games = nrfi.get("games") or []
    baseline = nrfi.get("league_nrfi_baseline") or 0.58
    strong_nrfi = []
    strong_yrfi = []
    for g in nrfi_games:
        if (g.get("p_yrfi", 0) - (1 - baseline)) > 0.10:
            strong_yrfi.append(g.get("matchup"))
        elif (g.get("p_nrfi", 0) - baseline) > 0.10:
            strong_nrfi.append(g.get("matchup"))
    if strong_yrfi or strong_nrfi:
        lines.append("## NRFI/YRFI strong leans")
        if strong_yrfi:
            lines.append(f"- **YRFI** (1st-inning OVER): {', '.join(strong_yrfi[:5])}")
        if strong_nrfi:
            lines.append(f"- **NRFI** (1st-inning UNDER): {', '.join(strong_nrfi[:5])}")
        lines.append("")

    # Arb opps
    arb_alerts = arb.get("alerts") or []
    if arb_alerts:
        lines.append(f"## Cross-book pricing")
        lines.append(f"{len(arb_alerts)} props softer on one book — see /props for details.")
        lines.append("")

    # Golf (active PGA tournament + Play of the Tournament)
    golf_state = _load(os.path.join(DATA_DIR, "golf_state.json"))
    golf_bb = _load(os.path.join(DATA_DIR, "golf_bestbet.json"))
    golf_t = golf_state.get("active_tournament") or {}
    if golf_t.get("name") and not golf_t.get("is_complete"):
        lines.append(f"## Golf -- {golf_t.get('name')}")
        leader = golf_state.get("current_leader") or {}
        lines.append(f"- **Leader:** {leader.get('name','?')} ({leader.get('total_to_par','?')}) at #{leader.get('order','?')}")
        lines.append(f"- **Field:** {golf_state.get('n_players',0)} players  |  Status: {golf_t.get('status','?')}")
        pot = golf_bb.get("top_bet")
        if pot:
            opp = f" vs {pot.get('opponent')}" if pot.get("opponent") else ""
            lines.append(f"- **Play of the Tournament:** {pot.get('player')}{opp} {pot.get('type')} @ "
                         f"{pot.get('fair_american','?'):+d} (model {(pot.get('model_prob') or 0)*100:.1f}%, {pot.get('confidence','MED')})")
            lines.append(f"   - {pot.get('reasoning','')}")
        lines.append("")

    # NBA scoreboard
    nba = _load(os.path.join(DATA_DIR, "nba_state.json"))
    nba_games = nba.get("games") or []
    if nba_games:
        lines.append(f"## NBA -- {(nba.get('season_status') or 'season').upper()}")
        for g in nba_games[:5]:
            score = f"{g.get('away_score',0)}-{g.get('home_score',0)}" if g.get("state") != "pre" else ""
            ph = (g.get("p_home_win") if g.get("p_home_win") is not None else 0.5) * 100
            lines.append(f"- {g.get('matchup')} ({g.get('away_record','?')} vs {g.get('home_record','?')}) "
                         f"{score} | P(home) {ph:.1f}% fair {g.get('fair_home_american','?'):+d} | {g.get('status','?')}")
        lines.append("")

    # NHL scoreboard
    nhl = _load(os.path.join(DATA_DIR, "nhl_state.json"))
    nhl_games = nhl.get("games") or []
    if nhl_games:
        lines.append(f"## NHL -- {(nhl.get('season_status') or 'season').upper()}")
        for g in nhl_games[:5]:
            score = f"{g.get('away_score',0)}-{g.get('home_score',0)}" if g.get("state") != "pre" else ""
            ph = (g.get("p_home_win") if g.get("p_home_win") is not None else 0.5) * 100
            lines.append(f"- {g.get('matchup')} ({g.get('away_record','?')} vs {g.get('home_record','?')}) "
                         f"{score} | P(home) {ph:.1f}% fair {g.get('fair_home_american','?'):+d} | {g.get('status','?')}")
        lines.append("")

    # KBO scoreboard
    kbo = _load(os.path.join(DATA_DIR, "kbo_state.json"))
    kbo_props = _load(os.path.join(DATA_DIR, "kbo_props.json"))
    kbo_pot = _load(os.path.join(DATA_DIR, "kbo_bestbet.json")).get("top_bet")
    kbo_preds = kbo_props.get("predictions") or []
    if kbo_preds:
        lines.append(f"## KBO -- {kbo.get('season',2026)} Korean Baseball")
        for g in kbo_preds[:5]:
            ph = (g.get('p_home_win') if g.get('p_home_win') is not None else 0.5) * 100
            lines.append(f"- {g.get('away_team')} @ {g.get('home_team')} | "
                         f"P(home) {ph:.1f}% fair {g.get('fair_home_american','?'):+d} "
                         f"| total {g.get('model_total','?')} R")
        if kbo_pot:
            lines.append(f"- **KBO POD:** {kbo_pot.get('label')} ({kbo_pot.get('confidence','MED')})")
        lines.append("")

    # LoL esports
    lol_state = _load(os.path.join(DATA_DIR, "lol_state.json"))
    lol_props = _load(os.path.join(DATA_DIR, "lol_props.json"))
    lol_pot = _load(os.path.join(DATA_DIR, "lol_bestbet.json")).get("top_bet")
    lol_preds = lol_props.get("predictions") or []
    if lol_preds:
        lines.append(f"## LoL Esports -- {lol_state.get('n_live',0)} live, {lol_state.get('n_upcoming',0)} upcoming")
        for m in lol_preds[:5]:
            pa = (m.get('p_series_a') if m.get('p_series_a') is not None else 0.5) * 100
            lines.append(f"- [{m.get('league')}] {m.get('team_a')} vs {m.get('team_b')} BO{m.get('best_of',1)} | "
                         f"P(A) {pa:.1f}% fair {m.get('fair_a_american','?'):+d}/{m.get('fair_b_american','?'):+d}")
        if lol_pot:
            lines.append(f"- **LoL POT:** {lol_pot.get('label')} ({lol_pot.get('confidence','MED')})")
        lines.append("")

    # CS esports
    cs_state = _load(os.path.join(DATA_DIR, "cs_state.json"))
    cs_props = _load(os.path.join(DATA_DIR, "cs_props.json"))
    cs_pot = _load(os.path.join(DATA_DIR, "cs_bestbet.json")).get("top_bet")
    cs_preds = cs_props.get("predictions") or []
    if cs_preds:
        lines.append(f"## CS Esports -- {cs_state.get('n_matches',0)} matches ({cs_state.get('data_source','?')})")
        for m in cs_preds[:5]:
            pa = (m.get('p_series_a') if m.get('p_series_a') is not None else 0.5) * 100
            lines.append(f"- {m.get('team_a')} vs {m.get('team_b')} BO{m.get('best_of',3)} | "
                         f"P(A) {pa:.1f}% fair {m.get('fair_a_american','?'):+d}/{m.get('fair_b_american','?'):+d}")
        if cs_pot:
            lines.append(f"- **CS POD:** {cs_pot.get('label')} ({cs_pot.get('confidence','MED')})")
        lines.append("")

    # Cross-sport Player POT
    ppot = _load(os.path.join(DATA_DIR, "player_pot.json"))
    if ppot.get("top_5"):
        lines.append(f"## Player Play of the Day -- across all sports ({ppot.get('n_candidates',0)} candidates scanned)")
        for c in ppot["top_5"]:
            elite = " (ELITE)" if c.get("is_elite") else ""
            fa = c.get('fair_american')
            fa_str = f"{fa:+d}" if isinstance(fa, int) else str(fa)
            lines.append(f"- **[{c.get('sport')}]** {c.get('label','')} | model {(c.get('prob') or 0)*100:.1f}% fair {fa_str}{elite}")
        lines.append("")

    # Self-learning calibration block (new sports)
    cal = _load(os.path.join(DATA_DIR, "esports_calibration.json"))
    cal_sports = cal.get("sports") or {}
    settled_total = sum(s.get("n_settled", 0) for s in cal_sports.values())
    if settled_total > 0:
        lines.append("## Self-learning calibration (esports + KBO)")
        for sport in ("lol", "cs", "kbo"):
            s = cal_sports.get(sport, {})
            if s.get("n_settled", 0) > 0:
                lines.append(f"- **{sport.upper()}:** {s['n_settled']} settled | brier {s.get('brier','?')} | ECE {s.get('ece','?')}")
                reco = s.get("calibration_recommendation", {})
                if reco.get("applied"):
                    lines.append(f"   - {reco.get('note','')}")
        lines.append("")

    text = "\n".join(lines)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    return {"path": OUT_PATH, "bytes": len(text), "sections": text.count("\n## ")}


if __name__ == "__main__":
    r = run()
    print(f"Wrote {r['path']}: {r['bytes']} bytes, {r['sections']} sections")
