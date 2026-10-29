// Game Lines vs DraftKings card (2026-10-28) -- renders data/game_lines_desk.json
// into every <div class="game-lines-card" data-sport="nfl|nhl">. Shows the
// desk's verdict FIRST (does the model beat the DK price at all?), the
// walk-forward backtest behind it, then today's board with any picks.
(function () {
  const els = document.querySelectorAll(".game-lines-card[data-sport]");
  if (!els.length) return;
  const amer = (a) => a == null ? "—" : (a >= 0 ? "+" + a : String(a));
  const pct = (p) => p == null ? "—" : (p * 100).toFixed(1) + "%";
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // NHL (2026-10-28): what each layer of the model buys, in log loss on this
  // season's DK-priced games (lower is better; DK's close is the bar).
  const ladder = (s, bt) => {
    const gm = s.goalie_model;
    if (!gm) return "";
    const eo = gm.backtest_elo_only || {}, pj = gm.backtest_projected || {};
    const acc = gm.espn_starter_accuracy || {}, ac = acc.confirmed || {};
    return `<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        Model ladder (log loss, lower = better): Elo only ${eo.logloss_elo ?? "—"} →
        + shots, projected goalie, rest ${pj.logloss_elo ?? "—"} →
        with confirmed starters ${bt.logloss_elo ?? "—"} · DraftKings close ${bt.logloss_market ?? "—"}
        ${ac.n ? `· ESPN "Confirmed" starter right ${ac.correct}/${ac.n}` : ""}
      </div>`;
  };
  // Forward test (2026-10-29): the picks actually logged, scored at the logged
  // DK price and against the DK close (implied-probability points; + = we got a
  // better number than the close). CLV says more, sooner, than a W-L record.
  const fwd = (s) => {
    const f = s.forward_test;
    if (!f || !f.n_logged) return "";
    const sg = (v) => v == null ? "—" : (v > 0 ? "+" : "") + v;
    const fin = f.n_close_final === f.n_clv ? "" : ` (${f.n_clv - f.n_close_final} not kicked off yet: close = latest line)`;
    return `<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        Forward test: ${f.n_logged} picks logged · settled ${f.settled_w}-${f.settled_l} (${sg(f.units)}u) ·
        vs the DK close: avg ${sg(f.avg_clv_pts)} pts, beat ${f.beat_close_pct ?? "—"}%, flat ${f.flat_close_pct ?? "—"}%${fin}
      </div>`;
  };
  const gl = (g) => {
    if (!g) return "";
    const tag = g.status === "confirmed" ? " ✓ confirmed"
      : g.status === "expected" ? " (expected)"
      : (g.p_start != null ? " " + Math.round(g.p_start * 100) + "% (model)" : "");
    return `${esc(g.projected || "?")}${tag}${g.back_to_back ? " · B2B" : ""}`;
  };
  fetch("data/game_lines_desk.json?t=" + Date.now(), { cache: "no-cache" })
    .then((r) => r.json())
    .then((d) => {
      els.forEach((el) => {
        const s = (d.sports || {})[el.dataset.sport];
        if (!s || s.error) {
          el.innerHTML = `<p class="muted" style="padding:14px;">Game-lines desk unavailable${s && s.error ? " (" + esc(s.error) + ")" : ""}.</p>`;
          return;
        }
        const bt = s.backtest || {};
        const oos = bt.sim_out_of_sample || {};
        const ci = bt.logloss_gain_ci90 || [];
        const tone = s.proven ? "#58c878" : (s.beats_market ? "#d4a04a" : "#e35a5a");
        const head = `<div style="padding:12px 16px; border-bottom:1px solid rgba(255,255,255,0.05); font-size:12.5px; line-height:1.6;">
            <div style="color:${tone}; font-weight:700; margin-bottom:4px;">${esc((s.verdict || "").split(":")[0])}</div>
            <div class="muted">${esc((s.verdict || "").split(":").slice(1).join(":").trim())}</div>
            <div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
              Backtest: ${bt.n || 0} games ${esc(bt.first_date || "")} → ${esc(bt.last_date || "")} vs the DK close ·
              log loss DK ${bt.logloss_market ?? "—"} / model ${bt.logloss_elo ?? "—"} / blend ${bt.logloss_blend ?? "—"} (w=${bt.w_fitted ?? "—"}) ·
              gain 90% CI [${ci[0] ?? "—"}, ${ci[1] ?? "—"}] ·
              out-of-sample half: ${oos.bets || 0} bets, ${oos.roi_pct == null ? "—" : (oos.roi_pct >= 0 ? "+" : "") + oos.roi_pct + "%"}
            </div>${ladder(s, bt)}${fwd(s)}</div>`;
        const rows = (s.board || []).map((r) => {
          const pk = r.pick;
          const pickTxt = pk ? `<strong style="color:#58c878;">${esc(pk.team)} ML ${amer(pk.book_american)}</strong> <span class="muted">EV ${(pk.ev * 100).toFixed(1)}%</span>` : `<span class="muted">no pick</span>`;
          return `<div style="display:grid; grid-template-columns: 90px 1.2fr 1fr 1fr 1fr 1.6fr; gap:10px; padding:7px 16px; border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono',monospace; font-size:11.5px;">
            <span class="muted">${esc(r.game_date || "")}</span><span><strong>${esc(r.matchup)}</strong></span>
            <span>DK ${amer(r.ml_home)} / ${amer(r.ml_away)}</span>
            <span class="muted">home DK ${pct(r.p_home_dk)}</span><span class="muted">model ${pct(r.p_home_elo)}</span><span>${pickTxt}</span>
            ${r.goalies ? `<span></span><span class="muted" style="grid-column: span 5; font-size:10.5px;">in net: ${gl(r.goalies.away)} (away) vs ${gl(r.goalies.home)} (home)${r.pick_blocked ? " · no pick until both are confirmed" : ""}</span>` : ""}</div>`;
        }).join("");
        el.innerHTML = head + (rows || `<p class="muted" style="padding:12px 16px;">No games on the DraftKings board.</p>`) +
          `<p class="muted" style="font-size:10.5px; padding:8px 16px 12px; margin:0;">Picks are recorded at the DraftKings price when made and graded on the final score. Not part of the curated record unless the backtest proves out and Brandon promotes it.${s.goalie_model ? " NHL: a game is priced and picked only once ESPN lists both starting goalies as Confirmed; before that the row shows ESPN's expected goalie or the model's projection (% = chance he starts). B2B = second night of a back-to-back." : ""}</p>`;
      });
    })
    .catch(() => els.forEach((el) => { el.innerHTML = `<p class="muted" style="padding:14px;">Game-lines desk unavailable.</p>`; }));
})();
