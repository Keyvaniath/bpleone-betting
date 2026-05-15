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

    date = (today.get("generated_at") or "")[:10] or dt.date.today().isoformat()
    lines = []
    lines.append(f"# EdgeStat Daily Brief - {date}")
    lines.append("")
    lines.append(f"_Generated at {today.get('generated_at') or 'unknown'} UTC. "
                 f"All game-line prices are from DraftKings. Pick-em opportunities from PrizePicks._")
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
