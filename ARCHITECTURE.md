# EdgeStat — Architecture

How the platform runs itself, end-to-end. Read once, then forget about it — everything below is automatic.

---

## TL;DR

- **Site (static)**: GitHub Pages (or Cloudflare Pages) at `betting.bpleone.com`
- **Heavy ML / slate refresh**: GitHub Actions cron (3 schedules)
- **Self-learning loop**: feeds settled outcomes back into shrinkage weights
- **Live data layer**: optional Cloudflare Worker (free) for sub-minute polling
- **Watchdog**: auto-retriggers daily pipeline if it goes >6 hours stale
- **Alerts**: Discord webhook on lock transitions + steam moves + critical staleness

Cost: **$0** (everything is free tier). No infrastructure to maintain.

---

## Data flow

```
                              ┌─────────────────────────────┐
                              │   PUBLIC APIs               │
                              │   - MLB Stats API           │
                              │   - ESPN scoreboards        │
                              │   - Bovada lines            │
                              └─────────────────────────────┘
                                  │                    │
                  ┌───────────────┘                    └─────────────┐
                  ▼                                                   ▼
   ┌──────────────────────────────┐               ┌───────────────────────────────┐
   │  CLOUDFLARE WORKER (opt)     │               │  GITHUB ACTIONS               │
   │  Cron: every 1 min in-game   │               │  3 cron workflows             │
   │  Writes to KV                │               │  Heavy ML, calibration        │
   │  Free tier                   │               │  Writes JSON back to repo     │
   └──────────────────────────────┘               └───────────────────────────────┘
                  │                                                   │
                  └──────────────────┬────────────────────────────────┘
                                     ▼
                       ┌──────────────────────────────┐
                       │  DASHBOARD (static site)     │
                       │  - reads worker KV (if set)  │
                       │  - reads repo data/*.json    │
                       │  - bpleone.com              │
                       └──────────────────────────────┘
```

---

## GitHub Actions workflows (already running)

### `daily-pipeline.yml`
- **Schedule**: 10:00, 17:00, 22:00 UTC (3x daily)
- **Auto-retrigger**: if no successful run in >6h, watchdog fires it
- **What it does**: 200+ steps — fetches data, builds the slate model, runs every deep-analysis module, writes ~80 JSON artifacts. Takes ~15 min.

### `live-games.yml`
- **Schedule**: every 10 minutes during game hours (`*/10 16-23 * * *` + `*/10 0-6 * * *`)
- **What it does**: polls MLB gumbo for live game state, refreshes ESPN states, updates locks/whales/sharp action, fires Discord alerts. Takes ~50 sec.

### `training-loop.yml`
- **Schedule**: every 20 min during game hours, hourly off-peak
- **What it does**: settles yesterday's outcomes, recomputes calibration shifts, updates `learned_weights.json` (the self-learning feedback loop). Takes ~55 sec.

### `pipeline-auto-retrigger.yml` (NEW — watchdog)
- **Schedule**: every 30 min
- **What it does**: checks last successful `daily-pipeline` run. If >6h stale, fires `workflow_dispatch` automatically. Prevents the kind of 13-hour silent outage that hit on 2026-05-20.

---

## Self-learning feedback loop

Every cycle of every pick made by the model goes into a unified ledger. After games settle, the ledger updates per-source W-L. The model then adjusts how much it trusts each source for next cycle.

```
   1. todays_top_plays.py + locks_of_day.py + whale_picks.py
      surface picks from various deep modules

   2. all_picks_tracker.py records every surfaced pick with
      permanent ID (source|sport|player|market|date)

   3. Games complete. outcomes.py + player_gamelogs settle them.

   4. self_learn_weights.py reads all_picks_ledger.by_source:
        hit_rate 60% -> learned weight 0.75
        hit_rate 50% -> learned weight 0.55
        hit_rate 40% -> learned weight 0.35

   5. todays_top_plays.py reads learned_weights.json on next run.
      Per-source SOURCE_SHRINKAGE_W is overridden if sample > 0.

   6. Better-performing sources get more influence on the top board.
      The model improves itself.
```

After ~30 settled picks per source, the learning has enough data to materially shift weights.

---

## What gets surfaced and tracked

| Source | Surfaces | Settled by |
|---|---|---|
| `top_25_board` | Today's Top Plays board | game + player gamelog |
| `pod` | Single highest-edge play per day | historical_mlb |
| `lock_of_day` | Top 5 daily curated picks | both |
| `whale_whale` / `whale_strong` | Multi-signal confluence | both |
| `consensus_hit_elite` / `consensus_hr_strong` | 3+ modules agree | player gamelog |
| `mlb_under_alert` | Multi-signal UNDER picks | historical_mlb |
| `sharp_strong` / `sharp_elite` | Line moved 5+pp toward our side | game |
| `pp_over` / `pp_under` | PrizePicks player props | player gamelog |
| `nhl_goalie` / `nhl_skater` | NHL game/team markets | future |
| `f1_driver` | F1 podium / win / points | future |
| `today` / `today_reco` | MLB game ML + totals | historical_mlb |

Each settled pick adds to per-source W-L → feeds back into learning.

---

## Live data layer (Cloudflare Worker — optional but recommended)

GitHub Actions has a hard 10-min cron floor. For sub-minute updates:

1. **Cloudflare Worker** (`cloudflare-worker/`) — runs every 60s during games
2. Polls MLB gumbo, ESPN, Bovada, writes to Cloudflare KV
3. Dashboard's `js/live_data.js` automatically tries the Worker first, falls back to repo JSON if not deployed

**To enable** (5 minutes one-time):
```bash
npm install -g wrangler
cd cloudflare-worker
wrangler login
wrangler kv:namespace create EDGESTAT_KV
# paste returned ID into wrangler.toml
wrangler deploy
```

Then add `<script>window.EDGESTAT_WORKER_URL = "https://edgestat-live.<your-sub>.workers.dev";</script>` near the top of `index.html`.

That's it. Sub-minute live updates for free.

---

## Cloudflare Pages deploy (optional — faster CDN)

The site currently lives on GitHub Pages. To move to Cloudflare Pages:

1. Cloudflare dashboard → Workers & Pages → Create → Pages → Connect to Git
2. Pick `Keyvaniath/bpleone-betting`
3. Build settings: no build command, output dir = root
4. Deploy

Cloudflare picks up `_headers` (security + cache) and `_redirects` (clean URLs).

You keep GitHub Pages as a backup (`CNAME` already points to `betting.bpleone.com`).

---

## Pages on the site

| Path | What it shows | Source |
|---|---|---|
| `/` | Dashboard with POD P&L + WHALE picks + Locks + slate | pod_pl.json, whale_picks.json, locks_history.json, today.json |
| `/tonight` | Consolidated slate view (WHALE → Locks → Sharp → Consensus → Unders → Pitch Count → Parlays) | all sources |
| `/play-of-day` | POD deep dive (factor decomp, confidence gauge, run dist) | pod_factor_decomp.json + today.json |
| `/locks-of-day` | Lock history with rationales + auto-refresh | locks_history.json + live_locks_status.json |
| `/accuracy` | Per-source W-L ledger (training signal) | all_picks_ledger.json |
| `/self-learning` | Health, learned weights, alerts, in-game locks | learned_weights.json, pipeline_health.json, live_alerts.json, in_game_locks.json |
| `/cross-sport-parlays` | 2-leg + 3-leg parlay builder | cross_sport_parlays.json |
| `/consensus-picks` | Multi-module agreement picks | consensus_picks.json |
| `/track-record` | POD P&L history with charts | pod_pl.json |
| `/brief` | Daily summary markdown | daily_summary_v2.md |

---

## Discord alerts (optional)

Add a GitHub repo secret named `DISCORD_WEBHOOK_URL` with your Discord webhook URL. The `live_alerter.py` (runs every 10 min) will push:
- ✅ Lock just clinched (LOCKED_WON)
- ❌ Lock just failed (LOCKED_LOST)
- ⚠️ Lock at risk
- 📡 Sharp steam (3+pp move toward our pick)
- ⚡ Live model-vs-book edge (8+pp divergence)
- 🚨 Pipeline stale (once/day if data >8h old)

---

## What you don't need to do

- Don't manually trigger the pipeline — auto-retrigger handles it
- Don't worry about stale data — watchdog catches it within 30 min
- Don't tune calibration weights — self-learning does it
- Don't settle picks manually — locks_of_day + pod_pl_tracker do it
- Don't track outcomes — all_picks_tracker does it

The system is designed to run unattended. The only manual thing is the one-time 5-minute Cloudflare Worker deploy for sub-minute live data (optional).

---

## Maintenance recipes

**Check overall health:**
- Visit `/self-learning` — green/yellow/red health card shows freshness of all key files
- Visit `/accuracy` — per-source W-L over time

**Trigger a manual refresh:**
```bash
gh workflow run daily-pipeline.yml
```

**See last 5 runs of each workflow:**
```bash
gh run list --workflow=daily-pipeline.yml --limit=5
gh run list --workflow=live-games.yml --limit=5
gh run list --workflow=training-loop.yml --limit=5
```

**Add a new sport / data source:**
1. Add a Python module in `python/`
2. Wire it into `slate_player_pot.py` or `slate_team_pot.py`
3. Add a step in `daily-pipeline.yml`
4. Add to `all_picks_tracker._collect_picks_from_sources()` if it surfaces picks
5. (Optional) Add a tab to `/accuracy` if you want per-source W-L

Audit catches breakage: `python python/_audit_imports.py` + `python python/_audit_html.py`.
