"""
EdgeStat -- daily summary generator.

Renders a markdown brief of today's slate + plays + pick-em opportunities.
Useful for:
  - Posting to social (Discord / Twitter / Substack)
  - Quick read on phone before games start
  - Audit trail (commits to git, so each day's recommendation is provable)

Writes data/daily_summary.md.
"""
from __future__ import annotations

import os
import json
import datetime as dt
from typing import Any, Dict, List


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_PATH = os.path.join(DATA_DIR, "daily_summary.md")


def _load(name: str) -> Dict[str, Any]:
    p = os.path.join(DATA_DIR, name)
    if not os.path.exists(p):
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def _fmt_price(x):
    if x is None:
        return "--"
    return f"+{x}" if x >= 0 else str(x)


def build_summary() -> str:
    today = _load("today.json")
    matchups = _load("matchups.json")
    props = _load("props.json")
    pickem = _load("pickem.json")
    parlays = _load("parlays.json")
    cal = _load("calibration_live.json")
    tr = _load("track_record.json")
    inj = _load("injuries_live.json")
    form = _load("team_form.json")
    bp = _load("bullpen_workload.json")
    nrfi = _load("nrfi.json")
    f5 = _load("first_five.json")
    rl = _load("run_line.json")
    travel = _load("travel.json")
    confidence = _load("model_confidence.json")
    anom = _load("anomalies.json")
    health = _load("pipeline_health.json")
    feedback = _load("training_feedback.json")
    param_recs = _load("param_recommendations.json")

    date = (today.get("generated_at") or "")[:10] or dt.date.today().isoformat()
    lines = []
    lines.append(f"# EdgeStat Daily Brief - {date}")
    lines.append("")

    # --- Model state header: confidence + pipeline health ---
    if confidence.get("score") is not None:
        tier = (confidence.get("tier") or "?").upper()
        lines.append(f"**Model Confidence: {confidence['score']}/100 [{tier}]** -- {confidence.get('message', '')}")
        lines.append("")
    if health.get("overall_status") and health["overall_status"] != "ok":
        lines.append(f"_Pipeline health: **{health['overall_status'].upper()}** "
                     f"({health.get('n_ok', '?')}/{health.get('total_artifacts', '?')} artifacts ok; "
                     f"{health.get('n_empty', 0)} empty, {health.get('n_stale', 0)} stale)._ ")
        lines.append("")

    # Pick the source label for game lines.
    src_books = set((g.get("market") or {}).get("book") for g in (today.get("games") or []))
    src_books.discard(None)
    src_label = ("DraftKings" if "draftkings" in src_books else
                 "Bovada (fallback -- DK primary unavailable)" if "bovada" in src_books else
                 "placeholder -110 (no real book today)")
    lines.append(f"_Generated at {today.get('generated_at') or 'unknown'} UTC. "
                 f"Game lines source: **{src_label}**. Pick-em opportunities from PrizePicks._")
    lines.append("")

    # --- Play of the Day ---
    pod = today.get("play_of_day")
    if pod:
        is_precal = (pod.get("edge_pct") or 0) >= 15
        kelly = "<= 0.5u (model calibrating)" if is_precal else f"{pod['kelly_units']}u Kelly"
        lines.append("## Play of the Day")
        lines.append("")
        lines.append(f"**{pod['matchup']} - {pod['label']}**")
        lines.append(f"- Market: {_fmt_price(pod['market_price'])}")
        lines.append(f"- Model probability: {pod['model_prob']*100:.1f}%")
        lines.append(f"- Raw edge: +{pod['edge_pct']}%")
        lines.append(f"- Recommended stake: {kelly}")
        if is_precal:
            lines.append("")
            lines.append("> _Edge >= 15% is well above what a properly-calibrated baseball model produces. "
                         "Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._")
        lines.append("")

    # --- Full slate ---
    games = today.get("games") or []
    if games:
        lines.append(f"## Full Slate ({len(games)} games)")
        lines.append("")
        lines.append("| Time | Matchup | Park | Weather | Top edge |")
        lines.append("|---|---|---|---|---|")
        for g in games:
            m = g.get("market", {})
            mod = g.get("model", {})
            wx = g.get("weather", {})
            recs = sorted(g.get("recommendations") or [], key=lambda r: -(r.get("edge_pct") or 0))
            top = recs[0] if recs else None
            wx_str = "indoor" if wx.get("is_indoor") else f"{wx.get('temp_f','?')}F {wx.get('wind_mph','?')}mph"
            top_str = f"{top['label']} +{top['edge_pct']}%" if top else "--"
            lines.append(f"| {g.get('time','--')} | {g['matchup']} | {g.get('park','--')} | {wx_str} | {top_str} |")
        lines.append("")

    # --- PrizePicks soft lines ---
    pp_props = pickem.get("props") or []
    softer = [p for p in pp_props if p.get("pp_advantage")]
    if softer:
        lines.append(f"## PrizePicks - {len(softer)} lines softer than DraftKings")
        lines.append("")
        lines.append("| Player | Market | PP line | DK line | Δ | Favor | Model % |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in softer[:15]:
            best = max(p["model_prob_over"], p["model_prob_under"]) * 100
            lines.append(f"| {p['player']} | {p['stat_type']} | {p['pp_line']} | "
                         f"{p['dk_line']} | {('+' if p['delta'] >= 0 else '')}{p['delta']} | "
                         f"{p['pp_softer_for']} | {best:.1f}% |")
        lines.append("")

    # --- Parlays ---
    parlay_list = parlays.get("parlays") or []
    if parlay_list:
        lines.append(f"## Parlays - top {min(5, len(parlay_list))}")
        lines.append("")
        for c in parlay_list[:5]:
            sgp_tag = " (SGP)" if c.get("sgp") else ""
            lines.append(f"- **{c['n_legs']}-leg{sgp_tag} @ {_fmt_price(c['parlay_price'])} "
                         f"(prob {c['parlay_prob']*100:.1f}%, EV +{c['edge_pct']}%)**")
            for leg in c["legs"]:
                lines.append(f"  - {leg['label']} ({_fmt_price(leg['price'])}, "
                             f"model {leg['model_prob']*100:.1f}%)")
        lines.append("")

    # --- Calibration ---
    market_metrics = cal.get("markets", {})
    if market_metrics:
        lines.append("## Self-Learning Loop")
        lines.append("")
        lines.append("| Market | n settled | Hit rate | Model implied | Bias | Correction |")
        lines.append("|---|---|---|---|---|---|")
        for k, m in market_metrics.items():
            if not m.get("n"):
                continue
            lines.append(f"| {k.replace('_', ' ')} | {m['n']} | "
                         f"{m.get('actual_over_rate', 0)*100:.1f}% | "
                         f"{m.get('implied_over_rate', 0)*100:.1f}% | "
                         f"{m.get('bias', 1):.3f} | "
                         f"{m.get('correction_factor', 1):.3f} |")
        lines.append("")
        graded = sum(1 for p in (tr.get('props') or []) if p.get('play_hit') is not None)
        wins = sum(1 for p in (tr.get('props') or []) if p.get('play_hit') is True)
        if graded:
            lines.append(f"Cumulative graded plays: {graded}. Wins: {wins}. "
                         f"Hit rate: {wins/graded*100:.1f}%.")
            lines.append("")

    # --- Auxiliary markets: NRFI / F5 / RL ---
    nrfi_games = nrfi.get("games") or []
    f5_games = f5.get("games") or []
    rl_games = rl.get("games") or []
    if nrfi_games or f5_games or rl_games:
        lines.append("## Auxiliary Markets (Model Fair Prices)")
        lines.append("")
        lines.append("| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |")
        lines.append("|---|---|---|---|---|---|")
        nrfi_by_m = {g["matchup"]: g for g in nrfi_games}
        f5_by_m = {g["matchup"]: g for g in f5_games}
        rl_by_m = {g["matchup"]: g for g in rl_games}
        matchups = set(nrfi_by_m) | set(f5_by_m) | set(rl_by_m)
        for matchup in sorted(matchups):
            n = nrfi_by_m.get(matchup) or {}
            f = f5_by_m.get(matchup) or {}
            r = rl_by_m.get(matchup) or {}
            nrfi_str = f"{n.get('p_nrfi', 0) * 100:.1f}%" if n else "--"
            nrfi_fair = (f"+{n['fair_nrfi_price']}" if n.get('fair_nrfi_price', 0) >= 0
                         else str(n.get('fair_nrfi_price', '--'))) if n else "--"
            f5_str = f.get('fair_total', '--')
            rl_h = ((f"+{r['fair_home_minus_15']}" if r.get('fair_home_minus_15', 0) >= 0
                     else str(r.get('fair_home_minus_15')))) if r else "--"
            rl_a = ((f"+{r['fair_away_plus_15']}" if r.get('fair_away_plus_15', 0) >= 0
                     else str(r.get('fair_away_plus_15')))) if r else "--"
            lines.append(f"| {matchup} | {nrfi_str} | {nrfi_fair} | {f5_str} | {rl_h} | {rl_a} |")
        lines.append("")

    # --- Travel / Rest ---
    travel_games = travel.get("games") or []
    flagged = []
    for g in travel_games:
        h = g.get("home") or {}
        a = g.get("away") or {}
        for side, info in (("home", h), ("away", a)):
            tz = abs(info.get("tz_change_hours") or 0)
            if tz >= 2 or (info.get("rest_days") == 0 and tz >= 1):
                flagged.append((g.get("matchup"), side, info.get("travel_note", "?")))
    if flagged:
        lines.append("## Travel / Rest Flags")
        lines.append("")
        for matchup, side, note in flagged[:8]:
            lines.append(f"- **{matchup}** ({side}): {note}")
        lines.append("")

    # --- Hot / cold teams ---
    teams_form = form.get("teams") or {}
    if teams_form:
        sorted_by_diff = sorted(teams_form.items(), key=lambda kv: -(kv[1].get("run_diff") or 0))
        hot = sorted_by_diff[:5]
        cold = sorted_by_diff[-5:][::-1]
        lines.append("## Team Form (last 10)")
        lines.append("")
        lines.append("**Hot:** " + ", ".join(
            f"{t['abbr'] or n} {t['wins']}-{t['losses']} ({t['streak']}, {('+' if t['run_diff'] > 0 else '')}{t['run_diff']})"
            for n, t in hot))
        lines.append("")
        lines.append("**Cold:** " + ", ".join(
            f"{t['abbr'] or n} {t['wins']}-{t['losses']} ({t['streak']}, {t['run_diff']})"
            for n, t in cold))
        lines.append("")

    # --- Gassed bullpens ---
    gassed = bp.get("gassed_teams") or []
    if gassed:
        lines.append(f"## Gassed Bullpens (> {bp.get('gassed_threshold_ip', 8)} IP in 2 days)")
        lines.append("")
        for name in gassed[:8]:
            t = (bp.get("teams") or {}).get(name) or {}
            lines.append(f"- {t.get('abbr') or name}: {t.get('total_relief_ip')} IP "
                         f"across {t.get('games_inspected')} games")
        lines.append("")

    # --- Loop activity since last refresh ---
    fb_entries = feedback.get("entries") or []
    if fb_entries:
        latest = fb_entries[-1]
        lines.append("## Loop Activity (since last refresh)")
        lines.append("")
        cd = latest.get("confidence_delta")
        cd_str = f"{'+' if (cd is not None and cd >= 0) else ''}{cd}" if cd is not None else "n/a"
        lines.append(f"- Confidence delta: **{cd_str}**")
        cm = latest.get("calibration_moves") or []
        if cm:
            top = sorted(cm, key=lambda m: abs(m.get("cf_delta") or 0), reverse=True)[:5]
            for m in top:
                d = m.get("cf_delta")
                d_str = f"{'+' if (d is not None and d >= 0) else ''}{d}" if d is not None else "--"
                n_add = m.get("n_added", 0)
                lines.append(f"- {m['market'].replace('_', ' ')}: cf {d_str}"
                             + (f" ({n_add} new settled)" if n_add else ""))
        new_pb = latest.get("new_player_overrides") or []
        if new_pb:
            lines.append(f"- New player overrides: {', '.join(new_pb[:5])}")
        new_anom = latest.get("new_anomalies") or []
        if new_anom:
            lines.append(f"- New anomalies flagged: {len(new_anom)}")
        lines.append("")

    # --- Model recommendations (operator review) ---
    rec_list = param_recs.get("recommendations") or []
    if rec_list:
        lines.append("## Model Recommendations (operator review)")
        lines.append("")
        lines.append(f"_The model is suggesting {len(rec_list)} parameter tweak"
                     f"{'s' if len(rec_list) != 1 else ''} based on its own performance. "
                     f"Apply via `data/runtime_config.json` on `/config`._")
        lines.append("")
        for r in rec_list[:5]:
            sev = (r.get("severity") or "").upper()
            arrow = "↑" if r.get("direction") == "increase" else "↓" if r.get("direction") == "decrease" else "→"
            lines.append(f"- **[{sev}] `{r['key']}`** {arrow} {r['current']} -> **{r['suggested']}**")
            lines.append(f"  - _{r.get('rationale', '')}_")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append(f"_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._")
    lines.append(f"_Source: github.com/Keyvaniath/bpleone-betting - "
                 f"{tr.get('last_settled_date') and ('last settled ' + tr['last_settled_date']) or 'no settled data yet'}._")
    return "\n".join(lines)


def write_summary(md: str, path: str = OUT_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote daily summary -> {path}")
    print(f"  {len(md)} bytes, {md.count(chr(10))} lines")


if __name__ == "__main__":
    write_summary(build_summary())
