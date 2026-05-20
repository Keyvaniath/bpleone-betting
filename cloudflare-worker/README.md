# EdgeStat Live Worker — Cloudflare Workers deployment

**What this does:** runs a tiny JS function on Cloudflare's global edge network every 1 minute during game hours. Polls MLB Stats API, ESPN scoreboards, Bovada odds → writes to Cloudflare KV. The dashboard reads from this for sub-minute live updates without waiting for GitHub Actions (which has a 10-min minimum cron).

**Cost:** $0 — fits easily within the free tier:
- 100,000 requests/day (we use ~3,000/day at 1-min polling × 24h × 8 endpoints)
- 1 GB KV storage (we use <1 MB)
- Unlimited cron triggers

---

## 5-minute deployment

You already have a Cloudflare account (the screenshot you sent had "Workers & Pages" tab open). Steps:

```bash
# 1. Install wrangler (Cloudflare's CLI) once, globally
npm install -g wrangler

# 2. From this folder, log in
cd cloudflare-worker
wrangler login

# 3. Create the KV namespace (one time)
wrangler kv:namespace create EDGESTAT_KV
# Copy the returned `id = "..."` into wrangler.toml under [[kv_namespaces]]

# 4. Deploy
wrangler deploy
```

That's it. The worker is live at `https://edgestat-live.<your-subdomain>.workers.dev`.

---

## Endpoints (CORS open so your dashboard can fetch directly)

```
GET /live/mlb       -> live MLB games (inning, score, count, state)
GET /live/nhl       -> NHL scoreboard
GET /live/nba       -> NBA scoreboard
GET /live/wnba      -> WNBA scoreboard
GET /live/mls       -> MLS soccer
GET /live/epl       -> Premier League soccer
GET /live/bovada    -> Bovada MLB odds snapshots
GET /live/health    -> worker last-run + success/fail per source
```

Each response is JSON with `{ ts, ... }`. Cached at the edge for 30 seconds so repeated reads are instant.

---

## Wire to the EdgeStat dashboard

After deploy, point the dashboard at the worker URL. In `index.html` (or wherever), replace the static GitHub-served `data/live_games.json` fetch with:

```js
fetch("https://edgestat-live.<your-subdomain>.workers.dev/live/mlb")
  .then(r => r.json())
  .then(d => { /* sub-minute live updates */ });
```

---

## How this fits the bigger picture

```
                            CLOUDFLARE WORKER (this)
                            polls every 1 min during games
                            writes to KV
                                    |
                                    v
                              CLOUDFLARE KV
                            (live game state, odds)
                                    |
                                    v
                          DASHBOARD (Cloudflare Pages or
                            GitHub Pages) -- fetches from
                            worker URL for sub-minute updates

GITHUB ACTIONS (already running):
   daily-pipeline 3x/day -> full slate model, ML, calibration
   training-loop every 20 min -> self-learning weights, calibration shifts
   live-games every 10 min -> backup live polling, locks tracker
```

The worker handles "every-minute live updates", GitHub Actions handles "heavy ML + slate refresh". They don't compete — they complement.

---

## Cron schedule (in wrangler.toml)

```toml
"* 16-23 * * *"   # every 1 min, 12pm-7pm ET
"* 0-6 * * *"     # every 1 min, 8pm-2am ET (west coast)
"*/5 7-15 * * *"  # every 5 min off-peak
```

Total: ~1,500 cron runs/day. Each makes ~6 outbound fetches. Well under the free-tier 100k req/day limit.

---

## Adjusting which sports / which sources

Edit `src/worker.js`:
- `ESPN_SCOREBOARDS` map -> add/remove sports
- The `poll()` function -> add more outbound fetches
- KV writes use `await env.EDGESTAT_KV.put(key, value)` -- add more keys as needed

Then `wrangler deploy` again — takes 5 seconds.

---

## Manual trigger (testing)

```bash
# Set a secret manual-trigger key
wrangler secret put MANUAL_TRIGGER_KEY
# (enter a random string when prompted)

# Then fire a manual poll:
curl "https://edgestat-live.<sub>.workers.dev/poll?key=<your-key>"
```

---

## Cost monitoring

Cloudflare dashboard shows:
- Workers > edgestat-live > Analytics: requests/day, errors, CPU time
- KV > EDGESTAT_KV: storage used, reads/writes

If you ever approach free tier limits (you won't at this scale), the next paid tier is $5/month for 10M requests.
