# Odds key setup — the one structural unlock

The whole edge engine already runs on free data (ESPN game lines, the public PrizePicks
menu, the model boards, calibration, the held-out validation). **One paid feed is the
remaining unlock:** The Odds API, which lights up player-prop *book* lines and the edges
+ CLV that depend on them. The code is already wired and gated — you don't touch code.
Set one secret and it activates on the next run.

> **Current state (checked 2026-06-23):** a key IS already set as the secret and it's
> **valid** (the preflight gets 40 sports back) — but its monthly quota is **exhausted**
> (≈1 request left; the free tier got burned down). So the lever right now is **raising the
> plan tier** (more requests/month), **not** setting a key from scratch. [status.html](status.html)
> shows the live state.

## What it lights up (currently dormant)
- **Player-prop BOOK lines** (DraftKings / 8-book aggregate) — the paid cross-check the free menu can't give.
- **`pp_advantage`** — book-vs-PrizePicks +EV edges (the dormant prop edge path).
- **Prop CLV vs a real sharp close** — confirms the prop edge the whole track record rests on, against the book's closing line, not just PrizePicks open→close.
- **`book_vs_model` on the full paid multi-book feed** — instead of only the free ESPN game lines.

Game-line CLV ([clv.html](clv.html)) and everything model-side already run **without** the key — they're unaffected.

## Recommended tier (the actual decision)
**The Odds API "20K" plan — $30/mo, 20,000 requests/month.** The desk's MLB-prop-CLV
pull runs ≈5K requests/month, so 20K gives ~4× headroom and room for a second prop
sport. The next tier up (100K, $59/mo) is overkill until you scale props across many
sports. Free 500/mo is what's currently exhausted. This is the single highest-ROI add —
but it's a **purchase only you can make**; I can't buy a key or set the secret.

## Steps (≈5 minutes — all owner actions; I can't buy a key or set a secret for you)
1. **Raise the plan** at <https://the-odds-api.com> to the **20K / $30-mo tier** (the key is already valid — you're upgrading its quota, not creating a new key). The props pull is the only quota-hungry step.
2. **Add the GitHub secret:** repo **Settings → Secrets and variables → Actions → New repository secret** → name it **exactly** `ODDS_API_KEY`, paste the key. (The workflows already reference `${{ secrets.ODDS_API_KEY }}`.)
3. *(Optional)* add a repo **variable** `EDGESTAT_PROPS_MAX_GAMES` to cap quota use: `8` on the free tier, `16`+ on a paid tier.
4. **Trigger a run** so you don't wait for the 14:00 UTC cron: `gh workflow run daily-pipeline.yml` (or the Actions tab → Daily MLB Pipeline → Run workflow).

## Confirm it worked
- Open **[status.html](status.html)** → the **"Odds feed"** card flips:
  - 🟢 **ACTIVE** — key validated, healthy quota, book feed live (shows requests remaining).
  - 🔴 **EXHAUSTED** — key valid but ≈0 requests left this month → raise the plan tier (you do **not** need a new key). *This is the current state.*
  - 🟡 **LOW QUOTA** — key valid but the monthly quota is running low.
  - 🔴 **INVALID** — secret is set but the API rejected it (typo / expired plan) — fix the key.
  - 🟡 **DORMANT** — no key set yet.
- This is driven by `python/odds_key_preflight.py`, which runs first in the daily pipeline and makes one **free** `/v4/sports` validation call (it does not spend your monthly quota). So a bad key — or an exhausted quota — surfaces immediately instead of failing silently.

## Request budget — so a paid tier isn't burned in days
Every paid Odds API call is now gated through `python/odds_budget.py`:
- it never spends below a **10-request monthly reserve** (the quota can't be driven to zero), and
- it caps **paid requests per day** at `ODDS_DAILY_CAP` (repo variable / env, default `40`).

When the quota is low, paid fetches are **skipped** and the desk falls back to the free ESPN
game lines (the same graceful path as no key) — so an exhausted key never error-spams. **When
you upgrade the tier, set `ODDS_DAILY_CAP`** to roughly `monthly_quota ÷ 30 × 0.8` —
**~200 for the recommended 20k/mo plan** (the desk needs only ~167/day, so 200 covers it with
headroom while still protecting the monthly pool), or ~2,600 for a 100k/mo plan. The default
`40` is deliberately low so an un-upgraded key can't burn out — bump it the same day you raise
the tier. Per-day spend is logged to `data/odds_spend_log.json`.

## After it's live — the payoff
Once props have an open→close book history (a few days), the prop-CLV path confirms whether
the **+4.8% robust held-out edge** (and the durable `mlb_hrr_3.5_under` family, +38% EV) is
actually **beating the market**, not just winning. CLV is the metric that proves edge in
weeks instead of the months a win-rate sample needs — it's the honest finish line for the
whole rigor layer.
