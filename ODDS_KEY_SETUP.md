# Odds key setup — the one structural unlock

The whole edge engine already runs on free data (ESPN game lines, the public PrizePicks
menu, the model boards, calibration, the held-out validation). **One paid feed is the
remaining unlock:** The Odds API, which lights up player-prop *book* lines and the edges
+ CLV that depend on them. The code is already wired and gated — you don't touch code.
Set one secret and it activates on the next run.

## What it lights up (currently dormant)
- **Player-prop BOOK lines** (DraftKings / 8-book aggregate) — the paid cross-check the free menu can't give.
- **`pp_advantage`** — book-vs-PrizePicks +EV edges (the dormant prop edge path).
- **Prop CLV vs a real sharp close** — confirms the prop edge the whole track record rests on, against the book's closing line, not just PrizePicks open→close.
- **`book_vs_model` on the full paid multi-book feed** — instead of only the free ESPN game lines.

Game-line CLV ([clv.html](clv.html)) and everything model-side already run **without** the key — they're unaffected.

## Steps (≈5 minutes — all owner actions; I can't buy a key or set a secret for you)
1. **Get a key** at <https://the-odds-api.com> — free tier is 500 requests/month; paid tiers (~$30+/mo) raise the cap. The props pull is the only quota-hungry step.
2. **Add the GitHub secret:** repo **Settings → Secrets and variables → Actions → New repository secret** → name it **exactly** `ODDS_API_KEY`, paste the key. (The workflows already reference `${{ secrets.ODDS_API_KEY }}`.)
3. *(Optional)* add a repo **variable** `EDGESTAT_PROPS_MAX_GAMES` to cap quota use: `8` on the free tier, `16`+ on a paid tier.
4. **Trigger a run** so you don't wait for the 14:00 UTC cron: `gh workflow run daily-pipeline.yml` (or the Actions tab → Daily MLB Pipeline → Run workflow).

## Confirm it worked
- Open **[status.html](status.html)** → the **"Odds feed"** card flips:
  - 🟢 **ACTIVE** — key validated, book feed live (shows requests remaining).
  - 🔴 **INVALID** — secret is set but the API rejected it (typo / expired plan) — fix the key.
  - 🟡 **DORMANT** — no key set yet.
- This is driven by `python/odds_key_preflight.py`, which runs first in the daily pipeline and makes one **free** `/v4/sports` validation call (it does not spend your monthly quota). So a bad key surfaces immediately instead of failing silently.

## After it's live — the payoff
Once props have an open→close book history (a few days), the prop-CLV path confirms whether
the **+4.8% robust held-out edge** (and the durable `mlb_hrr_3.5_under` family, +38% EV) is
actually **beating the market**, not just winning. CLV is the metric that proves edge in
weeks instead of the months a win-rate sample needs — it's the honest finish line for the
whole rigor layer.
