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
    const qm = s.qb_model;
    if (qm) {
      const eo = qm.backtest_elo_only || {};
      return `<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        Model ladder (log loss, lower = better): Elo only ${eo.logloss_elo ?? "—"} → + starting QB ${bt.logloss_elo ?? "—"} · DraftKings close ${bt.logloss_market ?? "—"}
      </div>`;
    }
    const am = s.avail_model;
    if (am) {
      // NBA (2026-11-11): Elo -> + availability and rest, against the DK close
      const eo = am.backtest_elo_only || {}, fl = am.fit_logloss_last_season || {};
      return '<div class="muted" style="margin-top:6px; font-family:\'JetBrains Mono\',monospace; font-size:11px;">' +
        'Model ladder (log loss, lower = better): Elo only ' + (eo.logloss_elo ?? "—") + ' → + availability and rest ' + (bt.logloss_elo ?? "—") +
        ' · DraftKings close ' + (bt.logloss_market ?? "—") +
        (fl.model != null ? ' · last season (fit): Elo ' + fl.elo + ' → ' + fl.model : '') +
        '</div><div class="muted" style="margin-top:4px; font-size:11px;">' + esc(am.finding_2026_11_11 || "") + '</div>';
    }
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
    // (2026-11-13) the CLV figures are over games already played; open picks are a separate line
    const op = f.open || {};
    const fin = op.n ? `<br>Open picks (not played yet) vs today&#39;s line: ${op.n}, avg ${sg(op.avg_pts_vs_current)} pts (${op.ahead} ahead, ${op.behind} behind) — the market can still move back` : "";
    const bm = Object.entries(f.by_model || {}).map(([k, v]) => `${esc(k)}: ${v.n} picks, ${sg(v.avg_clv_pts)} pts`).join(" · ");
    // (2026-11-03) avg_clv_ev = EV of the logged picks at the NO-VIG DK close --
    // the plain answer to "were these good bets?". Shown first and in words;
    // the implied-prob points line stays below it as the detail.
    const ev = f.avg_clv_ev;
    const evLine = ev == null ? "" : `<div style="margin-top:6px; font-size:12px; font-weight:700; color:${ev > 0 ? "#58c878" : "#e35a5a"};">
        Played games, logged price vs the no-vig DraftKings close: average EV ${ev > 0 ? "+" : ev < 0 ? "−" : ""}${Math.abs(ev * 100).toFixed(2)}% per bet over ${f.n_clv} picks —
        ${ev > 0 ? "the close says these were +EV bets." : "the close says these were −EV bets (worse than a fair price), whatever the W-L shows."}
      </div>`;
    return `${evLine}<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        ${bm && Object.keys(f.by_model).length > 1 ? "By model version — " + bm + "<br>" : ""}Forward test: ${f.n_logged} picks logged · settled ${f.settled_w}-${f.settled_l} (${sg(f.units)}u, small sample) ·
        played games vs the DK close (${f.n_clv}): avg ${sg(f.avg_clv_pts)} implied-prob pts, beat ${f.beat_close_pct ?? "—"}%, flat ${f.flat_close_pct ?? "—"}%${fin}
      </div>`;
  };
  // NFL (2026-10-29): projected starting QB + his edge over the team's usual
  // starter (yards/game, from ANY/A); status from ESPN's injury report.
  const qbl = (q) => q ? `${esc(q.qb || "?")}${q.status && q.status !== "active" ? " (" + esc(q.status) + ")" : ""}${Math.round((q.edge || 0) * 10) ? " " + (q.edge > 0 ? "+" : "") + Math.round(q.edge * 10) + " yds" : ""}` : "";
  const gl = (g) => {
    if (!g) return "";
    const tag = g.status === "confirmed" ? " ✓ confirmed"
      : g.status === "expected" ? " (expected)"
      : (g.p_start != null ? " " + Math.round(g.p_start * 100) + "% (model)" : "");
    return `${esc(g.projected || "?")}${tag}${g.back_to_back ? " · B2B" : ""}`;
  };
  // NBA (2026-11-11): who is listed out, and how much value that is vs the team's usual
  const av = (x) => {
    if (!x) return "";
    const names = (x.listed || []).filter((i) => Math.abs(i.value) >= 1).slice(0, 3)
      .map((i) => esc(i.name) + (/day/i.test(i.status || "") ? " (DTD)" : " (out)")).join(", ");
    return (names || "no rotation player listed") + " · " + (x.abnormal > 0 ? "+" : "") + x.abnormal + " vs usual" + (x.b2b ? " · B2B" : "");
  };
  // (2026-11-03) every DK price carries when it was observed + its snapshot id.
  const qt = (q) => q && q.observed_at
    ? `DK price observed ${esc(String(q.observed_at).replace("T", " "))} UTC · snapshot ${esc(q.snapshot_id || "—")}`
    : "DK price: observation time not recorded";
  // (2026-11-11) the lean rule's walk-forward record: what the per-sport play
  // is on a day the desk has no pick. Stated as what it is: not an edge.
  const leanLine = (s) => {
    const b = (s.lean || {}).backtest;
    if (!b || !b.n) return "";
    const u = Number(b.units || 0);
    return `<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        Model lean (shown when there is no desk pick; the favourite the model and DraftKings agree on): ${b.wins}-${b.losses}, ${u >= 0 ? "+" : "−"}${Math.abs(u).toFixed(2)}u at the DK close over ${b.n} game days ·
        expected ${b.expected_roi_pct_at_no_vig}% per bet at the no-vig price — a lean is not an edge
      </div>`;
  };
  // (2026-11-13) line-move signals: a forward test of whether the model points at the side
  // the market moves toward. Not picks.
  const msl = (s) => {
    const m = s.move_signals;
    if (!m || !m.n_seen) return "";
    const sg = (v) => v == null ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v);
    return `<div class="muted" style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:11px;">
        Line-move signals (forward test, not picks; model ≥ ${Math.round(m.gap * 100)} pts off DraftKings when a game first appears): ${m.n_scored} scored${m.n_scored ? `, CLV ${sg(m.avg_clv_pts)} pts, beat the close ${m.beat_close_pct}%, EV at the close ${sg(m.avg_clv_ev_pct)}%` : ""} · ${m.n_signals_open} open · ${m.n_seen} games seen since ${String(m.since || "").slice(0, 10)}
      </div>`;
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
            </div>${ladder(s, bt)}${fwd(s)}${leanLine(s)}${msl(s)}</div>`;
        const rows = (s.board || []).map((r) => {
          const pk = r.pick;
          // (2026-11-11) no desk pick: show the lean, if the game has one, labelled as a lean
          const ln = r.lean;
          const pickTxt = pk ? `<strong style="color:#58c878;">${esc(pk.team)} ML ${amer(pk.book_american)}</strong> <span class="muted">EV ${(pk.ev * 100).toFixed(1)}%</span>`
            : ln ? `<span style="color:#7fb0e8;">lean ${esc(ln.team)} ${amer(ln.book_american)}</span> <span class="muted">no edge</span>`
            : `<span class="muted">no pick</span>`;
          return `<div style="display:grid; grid-template-columns: 90px 1.2fr 1fr 1fr 1fr 1.6fr; gap:10px; padding:7px 16px; border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono',monospace; font-size:11.5px;">
            <span class="muted">${esc(r.game_date || "")}</span><span><strong>${esc(r.matchup)}</strong></span>
            <span>DK ${amer(r.ml_home)} / ${amer(r.ml_away)}</span>
            <span class="muted">home DK ${pct(r.p_home_dk)}</span><span class="muted">model ${pct(r.p_home_elo)}</span><span>${pickTxt}</span>
            ${r.qbs ? `<span></span><span class="muted" style="grid-column: span 5; font-size:10.5px;">QBs: ${qbl(r.qbs.away)} (away) vs ${qbl(r.qbs.home)} (home)${r.pick_blocked ? " · " + esc(r.pick_blocked) : ""}</span>` : ""}
            ${r.avail ? `<span></span><span class="muted" style="grid-column: span 5; font-size:10.5px;">missing: ${av(r.avail.away)} (away) vs ${av(r.avail.home)} (home)${r.pick_blocked ? " · " + esc(r.pick_blocked.split(" -- ")[0]) : ""}</span>` : ""}
            ${r.goalies ? `<span></span><span class="muted" style="grid-column: span 5; font-size:10.5px;">in net: ${gl(r.goalies.away)} (away) vs ${gl(r.goalies.home)} (home)${r.pick_blocked ? " · no pick until both are confirmed" : ""}</span>` : ""}
            <span></span><span class="muted" style="grid-column: span 5; font-size:10px;">${qt(r.quote)}</span></div>`;
        }).join("");
        el.innerHTML = head + (rows || `<p class="muted" style="padding:12px 16px;">No games on the DraftKings board.</p>`) +
          `<p class="muted" style="font-size:10.5px; padding:8px 16px 12px; margin:0;">Picks are recorded at the DraftKings price when made and graded on the final score. Not part of the curated record unless the backtest proves out and Brandon promotes it.${s.goalie_model ? " NHL: a game is priced and picked only once ESPN lists both starting goalies as Confirmed; before that the row shows ESPN's expected goalie or the model's projection (% = chance he starts). B2B = second night of a back-to-back." : ""}${s.avail_model ? " NBA: 'missing' lists rotation players on ESPN's injury report (out, or DTD = day-to-day at half weight) and the Game Score points of value that is above or below what the team has usually been missing; a game with a material day-to-day player is not picked." : ""}</p>`;
      });
    })
    .catch(() => els.forEach((el) => { el.innerHTML = `<p class="muted" style="padding:14px;">Game-lines desk unavailable.</p>`; }));
})();
