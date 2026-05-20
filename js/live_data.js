/**
 * EdgeStat live data layer.
 *
 * Unified fetch with automatic fallback:
 *   1. Try Cloudflare Worker KV (sub-minute live data) if WORKER_URL set
 *   2. Fall back to GitHub Pages repo JSON (10-min cron data)
 *
 * Any page can call:
 *   EdgeStatLive.fetch("mlb")   -> live MLB games
 *   EdgeStatLive.fetch("nhl")   -> NHL scoreboard
 *   EdgeStatLive.fetch("bovada") -> Bovada odds
 *
 * If the Worker isn't deployed yet, we silently fall back to the repo
 * JSON files. Once Brandon runs `wrangler deploy`, set WORKER_URL on
 * window and the dashboard automatically goes sub-minute.
 */
(function () {
  if (window.EdgeStatLive) return;

  // Set this once the Cloudflare Worker is deployed:
  //   window.EDGESTAT_WORKER_URL = "https://edgestat-live.<your-sub>.workers.dev"
  // Else stays as null and we fall back to repo JSON.
  const WORKER_URL = window.EDGESTAT_WORKER_URL || null;

  const FALLBACK_MAP = {
    mlb: "data/live_games.json",
    nhl: "data/nhl_state.json",
    nba: "data/nba_state.json",
    wnba: "data/wnba_state.json",
    mls: "data/mls_state.json",
    epl: "data/epl_state.json",
    bovada: "data/live_clv.json",
    health: "data/pipeline_health.json",
  };

  // Light in-memory cache so duplicate fetches in the same tick share
  const cache = {};
  const CACHE_MS = 25 * 1000;   // 25s -- worker edge cache is 30s

  async function fetchKey(key) {
    const now = Date.now();
    const cached = cache[key];
    if (cached && (now - cached.ts) < CACHE_MS) return cached.data;

    let data = null;
    if (WORKER_URL) {
      try {
        const r = await fetch(`${WORKER_URL}/live/${key}`, { cache: "no-store" });
        if (r.ok) data = await r.json();
      } catch (e) { /* fall through */ }
    }
    if (data == null) {
      const fallback = FALLBACK_MAP[key];
      if (fallback) {
        try {
          const r = await fetch(`${fallback}?t=${now}`, { cache: "no-cache" });
          if (r.ok) data = await r.json();
        } catch (e) { /* shrug */ }
      }
    }
    if (data) cache[key] = { ts: now, data };
    return data;
  }

  // Pulsing dot indicator for "live data" badge
  function attachLiveIndicator(elementId, key) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const refresh = async () => {
      const d = await fetchKey(key);
      if (d && d.ts) {
        const age = (Date.now() - new Date(d.ts).getTime()) / 1000;
        const fresh = age < 90;   // <90s -> green pulsing
        el.innerHTML = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${fresh ? '#58c878' : '#d4a04a'};animation:pulse 2s infinite;margin-right:6px;"></span>${fresh ? 'LIVE' : 'STALE'} <span style="font-size:10px;opacity:0.6;">${Math.round(age)}s ago</span>`;
      } else {
        el.innerHTML = `<span style="color:#888;font-size:11px;">no live feed</span>`;
      }
    };
    refresh();
    setInterval(refresh, 30 * 1000);   // refresh badge every 30s
  }

  window.EdgeStatLive = {
    fetch: fetchKey,
    attachLiveIndicator,
    isWorkerConfigured: () => !!WORKER_URL,
    workerUrl: () => WORKER_URL,
  };
})();
