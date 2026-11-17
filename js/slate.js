/* (2026-11-16) TODAY'S SLATE: every NFL / NBA / NHL game on today's Eastern date, straight from ESPN's
   public scoreboard (the same source the pipelines use), with the start time, the live score or the final,
   and our bet on the game if The Board has one: the price it was logged at and where it stands now.

   Why: the curated boards and The Board's open bets only list games that have not started, so on a
   night like Monday (MNF + 8 NBA + NHL) the page read "All sports, 0 picks" once the games tipped off.

   Usage: <div id="slate" data-sports="NFL,NBA,NHL"></div> then EdgeSlate.mount(el, {board, onSports}).
   Read-only: nothing here is logged or graded; grading stays in the ledger (all_picks_tracker.py). */
(function () {
  const PATH = { NFL: "football/nfl", NBA: "basketball/nba", NHL: "hockey/nhl", NCAAF: "football/college-football", NCAAB: "basketball/mens-college-basketball" };
  const PAGE = { NFL: "nfl.html", NBA: "nba.html", NHL: "nhl.html", NCAAF: "ncaaf.html", NCAAB: "ncaab.html" };
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const am = (a) => a == null || a === "" ? "—" : (Number(a) >= 0 ? "+" + a : "" + a);
  const etYmd = (d) => (d || new Date()).toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  const etTime = (iso) => new Date(iso).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" }) + " ET";

  // our bets on today's games: the locked Alpha list, the open board picks, and the ledger's rows for today
  function betsFor(board, day) {
    const out = [];
    const add = (p, src) => {
      if (!p || !p.team) return;
      const key = `${p.sport}|${p.matchup}`;
      if (out.some((x) => x.key === key && x.team === p.team)) return;
      out.push({ key, day, sport: p.sport, matchup: p.matchup, team: p.team, price: p.book_american, grade: p.grade,
                 alpha: src === "alpha" ? p.rank || (board.alpha.picks.indexOf(p) + 1) : (p.is_alpha ? "✓" : null),
                 result: p.result || null, final: p.final || null });
    };
    const A = (board && board.alpha) || {};
    // the locked list belongs to the board's own date only (after midnight it is yesterday's or not yet set)
    if (A.status === "locked" && board.date_et === day) (A.picks || []).forEach((p) => add(p, "alpha"));
    ((board && board.picks) || []).filter((p) => p.game_date === day).forEach((p) => add(p, "board"));
    (((board && board.results) || {}).recent || []).filter((r) => r.date === day).forEach((r) => {
      const hit = out.find((x) => x.key === `${r.sport}|${r.matchup}` && x.team === r.team);
      if (hit) { hit.result = r.result; hit.final = r.final; if (r.is_alpha && !hit.alpha) hit.alpha = "✓"; }
      else add(r, "ledger");
    });
    return out;
  }

  // a bet belongs to a game by sport, matchup AND ET date: the same pairing can meet on back-to-back
  // nights (POR @ MIN 11/16 and 11/17), and yesterday's bet must never show on tonight's game
  const same = (b, g) => b.sport === g.sport && b.matchup === g.matchup && (!b.day || !g.day || b.day === g.day);

  async function fetchSport(sport, day) {
    const u = `https://site.api.espn.com/apis/site/v2/sports/${PATH[sport]}/scoreboard?dates=${day.replace(/-/g, "")}`;
    const j = await fetch(u, { cache: "no-cache" }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });
    return (j.events || []).filter((e) => etYmd(new Date(e.date)) === day).map((e) => {
      const c = (e.competitions || [])[0] || {};
      const side = (h) => (c.competitors || []).find((t) => t.homeAway === h) || {};
      const H = side("home"), Aw = side("away");
      const st = (e.status || {}).type || {};
      return { sport, id: e.id, start: e.date, day: etYmd(new Date(e.date)), matchup: `${(Aw.team || {}).abbreviation} @ ${(H.team || {}).abbreviation}`,
               away: (Aw.team || {}).abbreviation, home: (H.team || {}).abbreviation,
               as: Aw.score, hs: H.score, state: st.state, detail: st.shortDetail, done: !!st.completed };
    });
  }

  function betLine(g, b) {
    if (!b) return "";
    const mine = b.team === g.home ? Number(g.hs) : Number(g.as), theirs = b.team === g.home ? Number(g.as) : Number(g.hs);
    let stat, col;
    // the ledger writes won / lost / push (the audit caught a check for win / loss that never matched)
    const res = { win: "won", loss: "lost" }[b.result] || b.result;
    if (res === "won" || res === "lost" || res === "push") {
      stat = { won: "WON", lost: "LOST", push: "PUSH" }[res]; col = { won: "#4ade80", lost: "#e35a5a", push: "#9fb0c8" }[res];
    } else if (g.state === "in" || g.done) {
      const lead = mine - theirs;
      stat = g.done ? (lead > 0 ? "won · grading" : lead < 0 ? "lost · grading" : "tied · grading") : (lead > 0 ? `leading by ${lead}` : lead < 0 ? `trailing by ${-lead}` : "tied");
      col = lead > 0 ? "#4ade80" : lead < 0 ? "#e35a5a" : "#9fb0c8";
    } else { stat = "pending"; col = "#9fb0c8"; }
    const tag = b.alpha ? `<span style="background:#58c878;color:#0a0a0a;border-radius:4px;padding:0 5px;font-size:10px;font-weight:700;margin-right:6px;">ALPHA${b.alpha === "✓" ? "" : " #" + esc(b.alpha)}</span>` : "";
    return `<div style="font-size:12px;margin-top:3px;">${tag}<b>${esc(b.team)}</b> ML <span style="font-family:JetBrains Mono,monospace;color:#fbbf24;">${am(b.price)}</span>
      <span class="muted">grade ${esc(b.grade || "—")}</span> · <span style="color:${col};font-weight:600;">${esc(stat)}</span></div>`;
  }

  function card(g, bets) {
    const live = g.state === "in", pre = g.state === "pre";
    const score = pre ? "" : `<span style="font-family:JetBrains Mono,monospace;">${esc(g.away)} ${esc(g.as)} · ${esc(g.home)} ${esc(g.hs)}</span>`;
    const st = pre ? `<span class="muted">${esc(etTime(g.start))}</span>`
      : live ? `<span style="color:#f87171;font-weight:700;">● LIVE</span> <span class="muted">${esc(g.detail)}</span>`
      : `<span class="muted">${esc(g.detail || "Final")}</span>`;
    const mine = bets.filter((b) => same(b, g));
    return `<div style="padding:8px 10px;border-top:1px solid rgba(255,255,255,.06);">
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;font-size:13px;">
        <span style="font-family:JetBrains Mono,monospace;font-size:11px;color:#9fb0c8;min-width:34px;">${esc(g.sport)}</span>
        <a href="${PAGE[g.sport]}" style="color:inherit;font-weight:600;text-decoration:none;">${esc(g.matchup)}</a>
        ${score}<span style="margin-left:auto;">${st}</span>
      </div>${mine.map((b) => betLine(g, b)).join("") || (pre ? "" : "")}</div>`;
  }

  async function mount(el, opts) {
    opts = opts || {};
    const sports = String(el.dataset.sports || "NFL,NBA,NHL").split(",").map((s) => s.trim()).filter((s) => PATH[s]);
    // data-bets-only="1": only today's games we have a bet on, and hide the whole element when there are
    // none (the homepage uses this so game night shows our live bets and quiet days show nothing)
    const betsOnly = el.dataset.betsOnly === "1";
    // (2026-11-16 audit) the date is re-read on every refresh (a page left open rolls over at midnight), and
    // until 4 AM ET the previous day's games still in progress stay listed, with our bets on them: a West
    // Coast puck drop or an overtime Monday night must not vanish from the slate at 12:00 AM
    let day = etYmd(), yday = null;
    const roll = () => {
      day = etYmd();
      const h = Number(new Date().toLocaleString("en-US", { timeZone: "America/New_York", hour: "numeric", hour12: false })) % 24;
      yday = h < 4 ? etYmd(new Date(Date.now() - 864e5)) : null;
    };
    roll();
    let board = opts.board || null;
    let filter = "all";
    let games = [], failed = [];
    const draw = () => {
      const bets = betsFor(board || {}, day).concat(yday ? betsFor(board || {}, yday) : []);
      const hasBet = (g) => bets.some((b) => same(b, g));
      const show = games.filter((g) => (filter === "all" || g.sport === filter) && (!betsOnly || (hasBet(g) && g.state !== "pre")));   // pre-game bets are in the Alpha strip
      if (betsOnly) {
        el.hidden = !show.length && !failed.length;
        if (el.hidden) return;
      }
      // (2026-11-16 audit) a scoreboard that did not answer is NOT "no games": say so, and still list
      // today's bets for that sport (without a score) so the page never hides a live bet
      const down = failed.filter((s) => filter === "all" || s === filter);
      const orphan = bets.filter((b) => down.includes(b.sport) && !games.some((g) => same(b, g)));
      const note = down.length ? `<div style="padding:8px 10px;font-size:12px;color:#fbbf24;">Live scores for ${esc(down.join(", "))} are unavailable right now (ESPN's scoreboard did not answer); retrying every 60s.</div>` +
        orphan.map((b) => `<div style="padding:8px 10px;border-top:1px solid rgba(255,255,255,.06);font-size:13px;"><span style="font-family:JetBrains Mono,monospace;font-size:11px;color:#9fb0c8;margin-right:10px;">${esc(b.sport)}</span><b>${esc(b.matchup)}</b>${betLine({ state: "pre" }, b)}</div>`).join("") : "";
      const counts = sports.map((s) => [s, games.filter((g) => g.sport === s).length]).filter(([, n]) => n);
      const live = games.filter((g) => g.state === "in").length;
      el.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;margin:0 0 4px;">
          <h3 style="font-size:15px;margin:0;">${betsOnly ? "Tonight's bets, live" : "Today's slate"}</h3>
          <span class="muted" style="font-size:12px;">${esc(new Date(day + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric", timeZone: "UTC" }))}
          · ${betsOnly ? `${show.length} bet${show.length === 1 ? "" : "s"} · ${show.filter((g) => g.state === "in").length} live · ${show.filter((g) => g.state === "post").length} final`
              : (counts.map(([s, n]) => `${n} ${s}`).join(" · ") || (failed.length ? "live scores unavailable" : "no games")) + (live ? ` · <span style="color:#f87171;">${live} live</span>` : "")}</span>
          <span class="muted" style="font-size:11px;margin-left:auto;">ESPN scoreboard · refreshes every 60s</span></div>
        <p class="muted" style="font-size:12px;margin:0 0 6px;">${betsOnly ? `Every game today that we have a bet on, with the live score. <a href="board.html" style="color:#7fb0e8;">All games on The Board →</a>` : "Every game today, with our bet on it where The Board has one."} Bets are graded on the final at the DraftKings price shown; the live line here is a score, not a result.</p>
        ${note}${show.length ? show.map((g) => card(g, bets)).join("") : down.length ? "" : `<div class="muted" style="padding:10px;font-size:13px;">No ${filter === "all" ? "" : esc(filter) + " "}games today.</div>`}`;
    };
    const load = async () => {
      roll();
      const late = yday ? await Promise.all(sports.map((s) => fetchSport(s, yday).then((gs) => gs.filter((g) => g.state === "in")).catch(() => []))) : [];
      const res = (await Promise.all(sports.map((s) => fetchSport(s, day).catch(() => null))))
        .map((r, i) => (r === null ? null : (late[i] || []).concat(r)));
      // keep the last good games for a sport whose refresh failed, rather than dropping them
      failed = sports.filter((s, i) => res[i] === null && !games.some((g) => g.sport === s));
      const order = { in: 0, pre: 1, post: 2 };
      games = sports.flatMap((s, i) => res[i] === null ? games.filter((g) => g.sport === s) : res[i]).sort((a, b) => (order[a.state] ?? 1) - (order[b.state] ?? 1) || (a.start > b.start ? 1 : -1));
      if (opts.onSports) opts.onSports(sports.filter((s) => games.some((g) => g.sport === s)));
      draw();
    };
    if (!board) board = await fetch("data/board.json?t=" + Date.now(), { cache: "no-cache" }).then((r) => r.json()).catch(() => ({}));
    await load();
    setInterval(() => { if (!document.hidden) load(); }, 60000);
    return { setFilter(s) { filter = s || "all"; draw(); } };
  }

  window.EdgeSlate = { mount, betsFor, same };
})();
