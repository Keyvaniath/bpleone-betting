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
  const sched = await fetchJSON(MLB_SCHEDULE_TODAY(todayDate()));
  if (sched && sched.dates && sched.dates[0]) {
    const games = sched.dates[0].games || [];
    const liveGames = games.filter(g => {
      const state = (g.status && g.status.abstractGameState) || "";
      return state === "Live" || state === "In Progress";
    });
    const out = [];
    for (const g of liveGames.slice(0, 15)) {  // cap at 15 to stay under CPU
      const gumbo = await fetchJSON(MLB_GUMBO(g.gamePk));
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
  }

  // 4. Health metadata
  await env.EDGESTAT_KV.put("worker_health", JSON.stringify({
    last_run: now,
    ok: results.ok,
    fail: results.fail,
  }));

  return results;
}

// ---------- HTTP handler ----------
async function handleHTTP(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  const cors = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=30",   // 30s edge cache
  };
  if (request.method === "OPTIONS") return new Response(null, { headers: cors });

  if (path === "/" || path === "") {
    return Response.redirect("https://betting.bpleone.com", 302);
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

// ---------- Cloudflare Worker entry ----------
export default {
  async fetch(request, env) {
    return handleHTTP(request, env);
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(poll(env));
  },
};
