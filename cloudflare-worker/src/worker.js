/**
 * EdgeStat Live Worker -- runs on Cloudflare Workers free tier.
 *
 * Triggered by cron every minute during game hours (16-23 UTC + 0-6 UTC).
 * Fetches MLB Stats API + ESPN scoreboards + Bovada odds, writes to KV.
 * The static dashboard reads from KV via the /live endpoint for sub-minute
 * updates without waiting for the 10-min GitHub Actions cron.
 *
 * Cloudflare Workers free tier:
 *   - 100,000 requests/day (~1.1 req/sec sustained)
 *   - 10ms CPU per request (we use ~5ms)
 *   - Cron triggers every 1 minute minimum
 *   - 1GB KV storage free
 *
 * Setup:
 *   1. wrangler login
 *   2. wrangler kv:namespace create EDGESTAT_KV
 *      (paste the returned ID into wrangler.toml)
 *   3. wrangler deploy
 *
 * Endpoints (after deploy):
 *   GET /live/games          -> live MLB game states
 *   GET /live/clv             -> live Bovada line snapshots
 *   GET /live/nhl             -> NHL scoreboard
 *   GET /live/health          -> worker health + last-update timestamps
 *   GET /                     -> redirect to bpleone.com
 */

const MLB_GUMBO = (gamePk) => `https://statsapi.mlb.com/api/v1.1/game/${gamePk}/feed/live`;
const MLB_SCHEDULE_TODAY = (date) => `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=${date}`;
const ESPN_SCOREBOARDS = {
  nhl:  "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
  nba:  "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
  wnba: "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard",
  mls:  "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard",
  epl:  "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard",
};
const BOVADA_MLB = "https://www.bovada.lv/services/sports/event/coupon/events/A/description/baseball/mlb";

// ---------- Helpers ----------
async function fetchJSON(url, { timeout = 6000 } = {}) {
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), timeout);
  try {
    const r = await fetch(url, { signal: c.signal, headers: { "User-Agent": "EdgeStat-Worker/1.0" }});
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    return null;
  } finally {
    clearTimeout(t);
  }
}

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

// ---------- Cron handler ----------
async function poll(env) {
  const now = new Date().toISOString();
  const results = { ts: now, ok: [], fail: [] };

  // 1. MLB live games -- schedule -> per-game gumbo for in-progress games
  //
  // 2026-05-21 perf: parallelized the gumbo fetch loop. Previously 15
  // sequential fetches at 6s timeout each = up to 90s CPU on the worker
  // (worker hard-limit on Pro is 30s/req). Sequential also slowed the
  // whole tick — the rest of the work waited for the slowest gumbo.
  // Promise.all-ing them cuts wall-clock to the slowest single call
  // (~1-2s typical, max 6s) and frees CPU budget for the ESPN + Bovada
  // sections to run before timeout.
  const sched = await fetchJSON(MLB_SCHEDULE_TODAY(todayDate()));
  if (sched && sched.dates && sched.dates[0]) {
    const games = sched.dates[0].games || [];
    const liveGames = games.filter(g => {
      const state = (g.status && g.status.abstractGameState) || "";
      return state === "Live" || state === "In Progress";
    }).slice(0, 15);  // cap at 15 to stay under CPU + KV value size
    const gumbos = await Promise.all(liveGames.map(g => fetchJSON(MLB_GUMBO(g.gamePk))));
    const out = [];
    for (let i = 0; i < liveGames.length; i++) {
      const g = liveGames[i];
      const gumbo = gumbos[i];
      if (!gumbo) continue;
      const ls = gumbo.liveData && gumbo.liveData.linescore;
      if (!ls) continue;
      out.push({
        gamePk: g.gamePk,
        matchup: `${g.teams.away.team.abbreviation || ''} @ ${g.teams.home.team.abbreviation || ''}`.trim(),
        inning: ls.currentInning,
        inning_half: ls.inningHalf,
        home_score: (ls.teams && ls.teams.home && ls.teams.home.runs) || 0,
        away_score: (ls.teams && ls.teams.away && ls.teams.away.runs) || 0,
        outs: ls.outs,
        balls: ls.balls,
        strikes: ls.strikes,
        state: g.status.abstractGameState,
      });
    }
    await env.EDGESTAT_KV.put("live_mlb", JSON.stringify({ ts: now, games: out }));
    results.ok.push(`mlb_live (${out.length} games)`);
  } else {
    results.fail.push("mlb_schedule");
  }

  // 2. ESPN scoreboards in parallel
  const espnResults = await Promise.all(
    Object.entries(ESPN_SCOREBOARDS).map(async ([sport, url]) => {
      const d = await fetchJSON(url);
      return [sport, d];
    })
  );
  for (const [sport, d] of espnResults) {
    if (!d) { results.fail.push(`espn_${sport}`); continue; }
    const events = (d.events || []).map(e => {
      const comp = (e.competitions || [])[0] || {};
      const competitors = comp.competitors || [];
      const home = competitors.find(c => c.homeAway === "home") || {};
      const away = competitors.find(c => c.homeAway === "away") || {};
      return {
        id: e.id,
        name: e.shortName,
        state: (e.status || {}).type ? (e.status.type.state || "") : "",
        home_team: (home.team || {}).abbreviation,
        away_team: (away.team || {}).abbreviation,
        home_score: home.score,
        away_score: away.score,
        period: (e.status || {}).period,
        clock: (e.status || {}).displayClock,
      };
    });
    await env.EDGESTAT_KV.put(`live_${sport}`, JSON.stringify({ ts: now, events }));
    results.ok.push(`${sport} (${events.length} events)`);
  }

  // 3. Bovada MLB odds (optional -- skip if rate-limited)
  const bovada = await fetchJSON(BOVADA_MLB);
  if (bovada && Array.isArray(bovada) && bovada[0] && bovada[0].events) {
    const snaps = [];
    for (const ev of bovada[0].events.slice(0, 30)) {
      const desc = ev.description || "?";
      const markets = ev.displayGroups && ev.displayGroups[0] && ev.displayGroups[0].markets;
      if (!markets) continue;
      const ml = markets.find(m => m.description === "Moneyline");
      const total = markets.find(m => m.description === "Total");
      let snap = { matchup: desc, t: now };
      if (ml && ml.outcomes && ml.outcomes.length >= 2) {
        const home = ml.outcomes.find(o => o.type === "H") || ml.outcomes[1];
        const away = ml.outcomes.find(o => o.type === "A") || ml.outcomes[0];
        snap.home_ml = parseFloat((home.price && home.price.american) || NaN);
        snap.away_ml = parseFloat((away.price && away.price.american) || NaN);
      }
      if (total && total.outcomes && total.outcomes.length >= 2) {
        const o = total.outcomes[0];
        snap.total = parseFloat((o.price && o.price.handicap) || NaN);
      }
      snaps.push(snap);
    }
    await env.EDGESTAT_KV.put("live_bovada", JSON.stringify({ ts: now, snaps }));
    results.ok.push(`bovada (${snaps.length} games)`);

    // PRO PLAN: also append to rolling 24h history per game (key per matchup).
    // This was throttled on free tier (1k KV writes/day). On Pro (1M/day) we
    // can afford a write per game per cron tick = ~30 games * 216 ticks/day = 6.5k/day.
    //
    // 2026-05-21 perf: parallelized the read+write pair for each matchup.
    // Was 30 sequential KV reads followed by 30 sequential KV writes —
    // ~3-5ms each = up to 300ms CPU just for the per-game history loop.
    // Promise.all-ing reads, then Promise.all-ing writes, cuts that to
    // ~50ms total (limited by the slowest single KV op).
    const histKeys = snaps.map(s => ({
      snap: s,
      key: `history_${s.matchup.replace(/\s+/g, '_')}`
    }));
    const existings = await Promise.all(histKeys.map(h => env.EDGESTAT_KV.get(h.key)));
    const writes = histKeys.map((h, i) => {
      const existing = existings[i];
      const buf = existing ? JSON.parse(existing) : { matchup: h.snap.matchup, snaps: [] };
      buf.snaps.push({
        t: now,
        home_ml: h.snap.home_ml, away_ml: h.snap.away_ml, total: h.snap.total,
      });
      // Cap at 1440 snaps (24h at 1/min). Even at the new */5 cadence we
      // never approach this — leaving the cap for safety.
      if (buf.snaps.length > 1440) buf.snaps = buf.snaps.slice(-1440);
      return env.EDGESTAT_KV.put(h.key, JSON.stringify(buf), { expirationTtl: 86400 });
    });
    await Promise.all(writes);
    results.ok.push(`history (${snaps.length} game buffers updated)`);
  }

  // 4. Health metadata + per-tick run timing (PRO: enables tail logging)
  await env.EDGESTAT_KV.put("worker_health", JSON.stringify({
    last_run: now,
    ok: results.ok,
    fail: results.fail,
    plan: "pro",
    kv_history_buffers: true,
  }));

  return results;
}

// ---------- HTTP handler ----------
async function handleHTTP(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=30",   // 30s edge cache
  };
  if (request.method === "OPTIONS") return new Response(null, { headers: cors });

  // ============================================================
  // D1 DATABASE ENDPOINTS (Pro plan -- pick history + backtest)
  // ============================================================

  // POST /db/log-picks  body: { picks: [...] }  -- bulk insert picks
  // Idempotent: ON CONFLICT (pick_id) DO NOTHING
  if (path === "/db/log-picks" && request.method === "POST") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    try {
      const body = await request.json();
      const picks = body.picks || [];
      let inserted = 0, skipped = 0;
      const stmt = env.EDGESTAT_DB.prepare(
        `INSERT INTO picks (pick_id, source, sport, player_or_matchup, market,
                            p_predicted, entry_odds, fair_odds, edge_pct, tier,
                            outcome, date, created_at, metadata, model_version)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(pick_id) DO NOTHING`
      );
      for (const p of picks) {
        const r = await stmt.bind(
          p.pick_id, p.source || "unknown", p.sport || "MLB",
          p.player_or_matchup || null, p.market || null,
          p.p_predicted || null,
          p.entry_odds || p.fair_american || null,
          p.fair_odds || p.fair_american || null,
          p.edge_pct || null, p.tier || null,
          p.outcome || "PENDING",
          p.date, p.created_at || new Date().toISOString(),
          p.metadata ? JSON.stringify(p.metadata) : null,
          p.model_version || null
        ).run();
        if (r.meta && r.meta.changes > 0) inserted++;
        else skipped++;
      }
      return new Response(JSON.stringify({ ok: true, inserted, skipped, total: picks.length }), { headers: cors });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors });
    }
  }

  // POST /db/settle-picks  body: { settlements: [{pick_id, outcome, payout_units, settled_at, closing_odds?}] }
  if (path === "/db/settle-picks" && request.method === "POST") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    try {
      const body = await request.json();
      const sets = body.settlements || [];
      let updated = 0;
      const stmt = env.EDGESTAT_DB.prepare(
        `UPDATE picks
            SET outcome=?, payout_units=?, closing_odds=COALESCE(?, closing_odds),
                settled_at=COALESCE(settled_at, ?)
          WHERE pick_id=? AND outcome='PENDING'`
      );
      for (const s of sets) {
        const r = await stmt.bind(
          s.outcome, s.payout_units || null,
          s.closing_odds || null,
          s.settled_at || new Date().toISOString(),
          s.pick_id
        ).run();
        if (r.meta && r.meta.changes > 0) updated++;
      }
      return new Response(JSON.stringify({ ok: true, updated, total: sets.length }), { headers: cors });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors });
    }
  }

  // GET /db/picks?source=X&date_from=Y&date_to=Z&limit=N
  if (path === "/db/picks") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const source = url.searchParams.get("source");
    const sport = url.searchParams.get("sport");
    const dateFrom = url.searchParams.get("date_from");
    const dateTo = url.searchParams.get("date_to");
    const outcome = url.searchParams.get("outcome");
    const limit = Math.min(parseInt(url.searchParams.get("limit") || "200"), 1000);

    let sql = "SELECT * FROM picks WHERE 1=1";
    const args = [];
    if (source)   { sql += " AND source = ?";   args.push(source); }
    if (sport)    { sql += " AND sport = ?";    args.push(sport); }
    if (dateFrom) { sql += " AND date >= ?";    args.push(dateFrom); }
    if (dateTo)   { sql += " AND date <= ?";    args.push(dateTo); }
    if (outcome)  { sql += " AND outcome = ?";  args.push(outcome); }
    sql += " ORDER BY date DESC, id DESC LIMIT ?";
    args.push(limit);

    const r = await env.EDGESTAT_DB.prepare(sql).bind(...args).all();
    return new Response(JSON.stringify({ results: r.results || [], n: (r.results || []).length }), { headers: cors });
  }

  // GET /db/backtest?source=X&date_from=Y&date_to=Z -- aggregate stats
  if (path === "/db/backtest") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const source = url.searchParams.get("source");
    const sport = url.searchParams.get("sport");
    const dateFrom = url.searchParams.get("date_from");
    const dateTo = url.searchParams.get("date_to");

    let sql = `SELECT
      COUNT(*) as n_picks,
      SUM(CASE WHEN outcome != 'PENDING' THEN 1 ELSE 0 END) as n_settled,
      SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as n_wins,
      SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as n_losses,
      SUM(CASE WHEN outcome = 'PUSH' THEN 1 ELSE 0 END) as n_pushes,
      SUM(COALESCE(payout_units, 0)) as net_units,
      AVG(p_predicted) as avg_p_predicted,
      AVG(edge_pct) as avg_edge_pct
      FROM picks WHERE 1=1`;
    const args = [];
    if (source)   { sql += " AND source = ?";   args.push(source); }
    if (sport)    { sql += " AND sport = ?";    args.push(sport); }
    if (dateFrom) { sql += " AND date >= ?";    args.push(dateFrom); }
    if (dateTo)   { sql += " AND date <= ?";    args.push(dateTo); }

    const r = await env.EDGESTAT_DB.prepare(sql).bind(...args).first();
    const settled = r.n_settled || 0;
    const hit_rate = settled > 0 ? (r.n_wins || 0) / settled : null;
    const roi_pct = settled > 0 ? ((r.net_units || 0) / settled) * 100 : null;

    // Per-source breakdown if no source filter
    let by_source = [];
    if (!source) {
      const bs = await env.EDGESTAT_DB.prepare(
        `SELECT source,
                COUNT(*) as n,
                SUM(CASE WHEN outcome != 'PENDING' THEN 1 ELSE 0 END) as n_settled,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as n_wins,
                SUM(COALESCE(payout_units, 0)) as net
         FROM picks GROUP BY source ORDER BY n_settled DESC`
      ).all();
      by_source = bs.results || [];
    }

    return new Response(JSON.stringify({
      filters: { source, sport, date_from: dateFrom, date_to: dateTo },
      n_picks: r.n_picks || 0,
      n_settled: settled,
      n_wins: r.n_wins || 0,
      n_losses: r.n_losses || 0,
      n_pushes: r.n_pushes || 0,
      hit_rate,
      net_units: r.net_units || 0,
      roi_pct,
      avg_p_predicted: r.avg_p_predicted,
      avg_edge_pct: r.avg_edge_pct,
      by_source,
    }), { headers: cors });
  }

  // GET /db/lifecycle -- per-source lifecycle: first seen, n=20 crossing, grades
  if (path === "/db/lifecycle") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    // Derive live lifecycle from picks table
    const r = await env.EDGESTAT_DB.prepare(`
      SELECT source,
             MIN(date) as first_pick_date,
             MIN(created_at) as first_pick_at,
             COUNT(*) as picks_total,
             SUM(CASE WHEN outcome != 'PENDING' THEN 1 ELSE 0 END) as settled_total,
             SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins
        FROM picks GROUP BY source ORDER BY first_pick_at ASC
    `).all();
    return new Response(JSON.stringify({ rows: r.results || [] }), { headers: cors });
  }

  // GET /db/by-version -- group performance by model_version (multi-year audit)
  if (path === "/db/by-version") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const r = await env.EDGESTAT_DB.prepare(`
      SELECT COALESCE(model_version, 'unknown') as model_version,
             COUNT(*) as picks_total,
             SUM(CASE WHEN outcome != 'PENDING' THEN 1 ELSE 0 END) as settled,
             SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
             SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
             SUM(COALESCE(payout_units, 0)) as net_units,
             MIN(date) as first_date,
             MAX(date) as last_date
        FROM picks GROUP BY model_version ORDER BY first_date DESC
    `).all();
    return new Response(JSON.stringify({ rows: r.results || [] }), { headers: cors });
  }

  // GET /db/daily -- per-day pick volume + hit rate (calendar heatmap source)
  if (path === "/db/daily") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const r = await env.EDGESTAT_DB.prepare(`
      SELECT date,
             COUNT(*) as picks_total,
             SUM(CASE WHEN outcome != 'PENDING' THEN 1 ELSE 0 END) as settled,
             SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
             SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
             SUM(COALESCE(payout_units, 0)) as net_units
        FROM picks GROUP BY date ORDER BY date DESC LIMIT 400
    `).all();
    return new Response(JSON.stringify({ rows: r.results || [] }), { headers: cors });
  }

  // POST /db/log-audit  body: { audit: [{source, old, new, reason, n, hr, version, at}] }
  if (path === "/db/log-audit" && request.method === "POST") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    try {
      const body = await request.json();
      const rows = body.audit || [];
      const stmt = env.EDGESTAT_DB.prepare(
        `INSERT INTO weight_audit (source, old_weight, new_weight, delta, reason,
                                    n_settled, hit_rate, model_version, changed_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
      );
      let inserted = 0;
      for (const a of rows) {
        const delta = (a.new_weight != null && a.old_weight != null) ? (a.new_weight - a.old_weight) : null;
        const r = await stmt.bind(
          a.source, a.old_weight ?? null, a.new_weight ?? null, delta,
          a.reason || null, a.n_settled ?? null, a.hit_rate ?? null,
          a.model_version || null, a.changed_at || new Date().toISOString()
        ).run();
        if (r.meta && r.meta.changes > 0) inserted++;
      }
      return new Response(JSON.stringify({ ok: true, inserted }), { headers: cors });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors });
    }
  }

  // GET /db/audit?source=X&limit=N -- weight change history
  if (path === "/db/audit") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const source = url.searchParams.get("source");
    const limit = Math.min(parseInt(url.searchParams.get("limit") || "100"), 500);
    let sql = "SELECT * FROM weight_audit WHERE 1=1";
    const args = [];
    if (source) { sql += " AND source = ?"; args.push(source); }
    sql += " ORDER BY changed_at DESC LIMIT ?";
    args.push(limit);
    const r = await env.EDGESTAT_DB.prepare(sql).bind(...args).all();
    return new Response(JSON.stringify({ rows: r.results || [] }), { headers: cors });
  }

  // ============================================================
  // R2 SNAPSHOT ENDPOINTS (Pro plan -- monthly D1 archives)
  // ============================================================

  // POST /admin/snapshot -- dump current D1 picks to R2 with month-stamped key
  if (path === "/admin/snapshot" && request.method === "POST") {
    if (!env.EDGESTAT_DB || !env.EDGESTAT_R2) {
      return new Response(JSON.stringify({ error: "D1 or R2 not bound" }), { status: 503, headers: cors });
    }
    try {
      const now = new Date();
      const month = now.toISOString().slice(0, 7);  // YYYY-MM
      const r2_key = `picks-${month}.json`;
      // Dump everything from picks table
      const r = await env.EDGESTAT_DB.prepare(
        `SELECT * FROM picks ORDER BY id ASC`
      ).all();
      const picks = r.results || [];
      const snapshot = {
        snapshot_at: now.toISOString(),
        month: month,
        n_picks: picks.length,
        picks: picks,
      };
      const body = JSON.stringify(snapshot);
      await env.EDGESTAT_R2.put(r2_key, body, {
        httpMetadata: { contentType: "application/json" },
      });

      // Record metadata in monthly_snapshots table
      const settled = picks.filter(p => p.outcome !== "PENDING").length;
      const wins = picks.filter(p => p.outcome === "WIN").length;
      const hit_rate = settled > 0 ? wins / settled : null;
      const total_units = picks.reduce((s, p) => s + (p.payout_units || 0), 0);
      await env.EDGESTAT_DB.prepare(
        `INSERT INTO monthly_snapshots (month, r2_key, n_picks_snapshot, n_settled,
                                         hit_rate, total_units, snapshot_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(month) DO UPDATE SET
           r2_key=excluded.r2_key,
           n_picks_snapshot=excluded.n_picks_snapshot,
           n_settled=excluded.n_settled,
           hit_rate=excluded.hit_rate,
           total_units=excluded.total_units,
           snapshot_at=excluded.snapshot_at`
      ).bind(month, r2_key, picks.length, settled, hit_rate, total_units, now.toISOString()).run();

      return new Response(JSON.stringify({
        ok: true, month, r2_key, n_picks: picks.length, size_bytes: body.length
      }), { headers: cors });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: cors });
    }
  }

  // GET /admin/snapshots -- list all R2 snapshots with metadata
  if (path === "/admin/snapshots") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const r = await env.EDGESTAT_DB.prepare(
      `SELECT * FROM monthly_snapshots ORDER BY month DESC`
    ).all();
    return new Response(JSON.stringify({ rows: r.results || [] }), { headers: cors });
  }

  // GET /admin/snapshot/<month> -- fetch a specific month's snapshot from R2
  const sm = path.match(/^\/admin\/snapshot\/(\d{4}-\d{2})\/?$/);
  if (sm) {
    if (!env.EDGESTAT_R2) {
      return new Response(JSON.stringify({ error: "R2 not bound" }), { status: 503, headers: cors });
    }
    const obj = await env.EDGESTAT_R2.get(`picks-${sm[1]}.json`);
    if (!obj) {
      return new Response(JSON.stringify({ error: "no snapshot for that month" }), { status: 404, headers: cors });
    }
    return new Response(obj.body, { headers: cors });
  }

  // GET /db/health -- count of rows in each table
  if (path === "/db/health") {
    if (!env.EDGESTAT_DB) {
      return new Response(JSON.stringify({ error: "D1 not bound" }), { status: 503, headers: cors });
    }
    const picks = await env.EDGESTAT_DB.prepare("SELECT COUNT(*) as n FROM picks").first();
    const snaps = await env.EDGESTAT_DB.prepare("SELECT COUNT(*) as n FROM line_snapshots").first();
    const runs = await env.EDGESTAT_DB.prepare("SELECT COUNT(*) as n FROM backtest_runs").first();
    return new Response(JSON.stringify({
      picks: picks.n, line_snapshots: snaps.n, backtest_runs: runs.n
    }), { headers: cors });
  }

  // /admin/save-overrides -- POST a model_overrides JSON, stored in KV.
  // The next pipeline cron syncs KV -> data/model_overrides.json via git commit.
  if (path === "/admin/save-overrides" && request.method === "POST") {
    try {
      const body = await request.text();
      const parsed = JSON.parse(body);  // validate
      const payload = JSON.stringify({ ...parsed, saved_at: new Date().toISOString() });
      await env.EDGESTAT_KV.put("model_overrides", payload);
      return new Response(JSON.stringify({ ok: true, size_bytes: payload.length }), { headers: cors });
    } catch (e) {
      return new Response(JSON.stringify({ error: String(e) }), { status: 400, headers: cors });
    }
  }
  if (path === "/admin/get-overrides") {
    const val = await env.EDGESTAT_KV.get("model_overrides");
    if (!val) return new Response("{}", { headers: cors });
    return new Response(val, { headers: cors });
  }

  if (path === "/" || path === "") {
    return Response.redirect("https://betting.bpleone.com", 302);
  }

  // /history/<matchup> -- PRO PLAN: rolling 24h line buffer per game
  // Example: /history/PHI_@_CIN
  const hm = path.match(/^\/history\/(.+?)\/?$/);
  if (hm) {
    const key = `history_${decodeURIComponent(hm[1])}`;
    const val = await env.EDGESTAT_KV.get(key);
    if (!val) return new Response(JSON.stringify({ error: "no history", key }), { status: 204, headers: cors });
    return new Response(val, { headers: cors });
  }

  // /history -- list all matchups with active buffers
  if (path === "/history" || path === "/history/") {
    const list = await env.EDGESTAT_KV.list({ prefix: "history_" });
    return new Response(JSON.stringify({
      n_buffers: list.keys.length,
      matchups: list.keys.map(k => k.name.replace(/^history_/, "").replace(/_/g, " ")),
    }), { headers: cors });
  }

  // /live/<key>
  const m = path.match(/^\/live\/([a-zA-Z_]+)\/?$/);
  if (m) {
    const key = m[1];
    const validKeys = ["mlb", "nhl", "nba", "wnba", "mls", "epl", "bovada", "health"];
    if (!validKeys.includes(key)) {
      return new Response(JSON.stringify({ error: "unknown key", valid: validKeys }), { status: 404, headers: cors });
    }
    const kvKey = key === "health" ? "worker_health" : `live_${key}`;
    const val = await env.EDGESTAT_KV.get(kvKey);
    if (!val) return new Response(JSON.stringify({ error: "no data yet", key }), { status: 204, headers: cors });
    return new Response(val, { headers: cors });
  }

  if (path === "/poll" && url.searchParams.get("key") === env.MANUAL_TRIGGER_KEY) {
    const r = await poll(env);
    return new Response(JSON.stringify(r), { headers: cors });
  }

  return new Response(JSON.stringify({
    name: "EdgeStat Live Worker",
    endpoints: ["/live/mlb", "/live/nhl", "/live/nba", "/live/wnba", "/live/mls", "/live/epl", "/live/bovada", "/live/health"],
  }), { headers: cors });
}

// ---------- Monthly snapshot (D1 -> R2) ----------
async function monthlySnapshot(env) {
  if (!env.EDGESTAT_DB || !env.EDGESTAT_R2) return;
  try {
    const now = new Date();
    const month = now.toISOString().slice(0, 7);
    const r2_key = `picks-${month}.json`;
    const r = await env.EDGESTAT_DB.prepare("SELECT * FROM picks ORDER BY id ASC").all();
    const picks = r.results || [];
    const snapshot = {
      snapshot_at: now.toISOString(),
      month, n_picks: picks.length, picks,
    };
    const body = JSON.stringify(snapshot);
    await env.EDGESTAT_R2.put(r2_key, body, {
      httpMetadata: { contentType: "application/json" },
    });
    const settled = picks.filter(p => p.outcome !== "PENDING").length;
    const wins = picks.filter(p => p.outcome === "WIN").length;
    const hit_rate = settled > 0 ? wins / settled : null;
    const total_units = picks.reduce((s, p) => s + (p.payout_units || 0), 0);
    await env.EDGESTAT_DB.prepare(
      `INSERT INTO monthly_snapshots (month, r2_key, n_picks_snapshot, n_settled,
                                       hit_rate, total_units, snapshot_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(month) DO UPDATE SET
         r2_key=excluded.r2_key,
         n_picks_snapshot=excluded.n_picks_snapshot,
         n_settled=excluded.n_settled,
         hit_rate=excluded.hit_rate,
         total_units=excluded.total_units,
         snapshot_at=excluded.snapshot_at`
    ).bind(month, r2_key, picks.length, settled, hit_rate, total_units, now.toISOString()).run();
  } catch (e) {
    // swallow -- monthly cron should never break the system
  }
}

// ---------- Cloudflare Worker entry ----------
export default {
  async fetch(request, env) {
    return handleHTTP(request, env);
  },

  async scheduled(event, env, ctx) {
    // Monthly snapshot trigger: cron "0 6 1 * *" runs on 1st of month at 06:00 UTC
    if (event.cron === "0 6 1 * *") {
      ctx.waitUntil(monthlySnapshot(env));
      return;
    }
    // All other cron triggers (every-minute, every-5-min) run the live poll
    ctx.waitUntil(poll(env));
  },
};
