# CLAUDE.md — Handoff for any Claude session

You are continuing work on **EdgeStat**, a quantitative sports-betting analytics platform built for Brandon Leone (GitHub: `Keyvaniath`). This document tells you everything you need in 90 seconds. Read it all before doing anything.

---

## What this is

EdgeStat is the **Sports Betting / DFS** desk in Brandon's `bpleone.com` ecosystem — a Squarespace umbrella site that hosts several "desks" on subdomains:

- `bpleone.com` — Squarespace marketing landing page (his branded hub)
- `pokemon.bpleone.com` — already live, his Pokémon TCG trading tool
- **`betting.bpleone.com`** — this repo, EdgeStat sports betting (TO BE DEPLOYED)
- Future: `sports-cards.bpleone.com`, `equity.bpleone.com`, `sports.bpleone.com`

The site itself is a static HTML/CSS/JS front-end backed by Python ML modules that produce JSON artifacts the front-end consumes. Think "Unusual Whales for MLB" — sharp money flow, Play of the Day, deep model probability stacks, live in-game win expectancy.

User background: 29-year-old in SoCal, former IB / equity research analyst. He thinks in finance terms (alpha, edges, portfolio, hedging, Kelly). Match that vocabulary.

---

## Where everything lives

This folder (project root):
```
bpleone-site/
├── index.html .. learn.html        16 HTML pages, one per major view
├── css/style.css                   single dark-mode stylesheet (Bloomberg/Unusual-Whales vibe)
├── js/                             7 JS files (data, ml-models, charts, main, extras, simulator, ml-lab)
├── python/                         25 ML modules — see "ML stack" below
├── data/                           20 JSON artifacts emitted by the Python pipeline
├── .github/workflows/              daily-pipeline cron (3x daily, needs ODDS_API_KEY secret)
├── CNAME                           contains "betting.bpleone.com" — already committed to GitHub
├── deploy.bat / deploy.sh          one-shot git push scripts (Windows / Mac)
├── DEPLOY.md / QUICKSTART.md       deployment guides
├── README.md                       project overview
└── CLAUDE.md                       this file
```

---

## Current deployment state (LIVE)

- **Live in production:** `https://betting.bpleone.com` — GitHub Pages, valid
  Let's Encrypt cert (CN=betting.bpleone.com). Repo `Keyvaniath/bpleone-betting`
  (public). `CNAME` committed; DNS resolves to GitHub Pages IPs.
- **Deploy = `git push origin main`.** Every push triggers a "Smoke Test" CI
  workflow (compiles ~600 python modules + runs critical ones + verify_calibration)
  and a `pages-build-deployment`. The site is static HTML/CSS/JS + JSON artifacts.
- **The daily pipeline** (`.github/workflows/daily-pipeline.yml`, 3× daily cron)
  regenerates all `data/*.json` and commits them. So: **commit CODE + new seed
  JSONs only; revert other data churn with `git checkout -- data/`** and let the
  cron regenerate. The smoke test itself churns ledger/clv data when run locally —
  always `git checkout -- data/` before staging.
- **Known constraint:** `ODDS_API_KEY` secret is lapsed (Brandon's payment), so the
  book-odds feeds are dark — book-vs-model edges, live line movement, CLV, and the
  PrizePicks `pp_advantage` path are dormant until it's restored. Everything
  odds-INDEPENDENT (the model boards, calibration) works regardless.
- Commit-message convention: end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## ML stack (this is the important part)

25 Python modules, all pure-Python (no PyTorch/sklearn/numpy dependencies for the core), all verified to run. Master entry: `python train.py`. End-to-end runtime: ~5 seconds.

| File | What it does |
|---|---|
| `probability.py` | Odds conversion, EV, Kelly, Poisson, Bayesian shrinkage, ELO, Pythag — the math primitives |
| `features.py` | 30-feature engineering pipeline (8 families: team / pitcher / bullpen / park / weather / umpire / schedule / market) |
| `mlb_model.py` | Bayesian + Poisson game projection — fair price per market |
| `simulator.py` | PA-level Monte Carlo (Knuth Poisson, base-out state machine, K/BB/1B/2B/3B/HR/OUT outcomes) |
| `prop_model.py` | Gradient-boosted regression trees from scratch — predicts per-player TB/HR/K/H |
| `neural_net.py` | MLP (12→16→8→1, tanh+sigmoid) with hand-coded backprop + Xavier init + permutation feature importance |
| `ensemble.py` | Logistic-regression meta-learner stacking the 4 base models |
| `calibration.py` | Brier, log loss, ECE, reliability diagrams, Platt scaling |
| `ratings.py` | Elo (with MoV) + Glicko-2 (rating + RD + volatility) team rating systems |
| `backtest.py` | Walk-forward backtest. Latest: 62.75% hit, +26.1% ROI, +2.08% CLV over 51 plays |
| `linemaker.py` | Bookmaker's-eye engine: opens at target hold %, re-shades on incoming money flow |
| `arbitrage.py` | Cross-book arb / middle / low-vig finder |
| `risk.py` | Bankroll Monte Carlo + Kelly fraction heatmap |
| `correlations.py` | Gaussian copula SGP pricer (exposes book's hidden parlay juice) |
| `live.py` | In-game win expectancy from base-out RE24 matrix + forward Monte Carlo |
| `series.py` | 3-game series multinomial distribution + rotation matching |
| `playoff.py` | Season-end Monte Carlo → P(playoffs) / P(division) / P(WS) |
| `portfolio.py` | Markowitz portfolio optimizer (coordinate-descent on EV - λ·Var) |
| `hedge.py` | Equal-payout hedge / break-even hedge / arbitrage check |
| `sos.py` | Strength of Schedule, strength-adjusted record, projected wins |
| `injury.py` | WAR-based win-probability hit when a player goes IL |
| `data_fetcher.py` | MLB Stats API + The Odds API clients (needs `ODDS_API_KEY` env var) |
| `pipeline.py` | Daily slate runner — writes `today.json` |
| `train.py` | **Master entry point** — runs every module, writes all 20 JSON artifacts |

To verify the whole stack works: `cd python && python3 train.py`. Expect "All artifacts written to ../data/" in ~5 seconds.

---

## Calibration & curation — the honesty layer (added 2026-06, READ THIS)

The single most important subsystem. The model's raw probabilities are
**overconfident** (real ECE ~11%; over 5,063 settled bets the raw firehose runs
**−15.2% ROI**). Two real-outcome guards, learned from the settled pick ledger
(`data/all_picks_ledger.json`), fix this and are what make the product honest.

**`python/prob_calibration.py`** — the shared engine. Key functions:
- `proven_negative_families()` / `is_proven_negative(market)` — market families
  that LOST money over a real sample (n≥25, net≤−5u). Boards HARD-EXCLUDE these.
  Dropping the 14 losing families turns the book from −15.2% to **+14.1% ROI**
  (1,469 bets, 67.5% hit). This is the headline metric.
- `empirical_calibrate(raw, market)` — Bayesian-blend a prob toward its family's
  realized hit rate. `calibrate_play(market, play, line, raw)` does the same for
  raw book props whose names don't carry line/side (reconstructs the family key).
- `overconfident_families()` / `is_overconfident(market)` / `is_overconfident_play(market, play, line)`
  — families where avg predicted exceeds realized by ≥12pp (model prob is broken;
  fake edge at ANY price). NARROWER than proven_negative: "priced-short" families
  (right prob, −EV at fair) can still be +EV at a soft PrizePicks line.
- `prob_to_american(p)`, `reconstruct_family(market, play, line)`, `reset_caches()`.
- DO NOT touch `market_taxonomy.py` to fix vocab — prob_calibration reconstructs
  family keys itself (zero risk to the profitable todays_top_plays pipeline).

**`python/verify_calibration.py`** — regression test proving the guards aren't
vacuous. Runs in the daily pipeline; fails the build if a guard regresses.

**Boards built on the engine (all curated + calibrated):**
- `high_confidence_board.py` → `high-confidence.html` — tiered model-conviction board.
- `props_parlay_builder.py` → `props-parlay.html` — props-only parlays.
- `prizepicks_value.py` → `prizepicks-value.html` — +EV PrizePicks legs (calibrated
  prob vs PP flat-payout break-even) + suggested Power Plays (ROI + quarter-Kelly).
- `calibration_map.py` → `calibration-map.html` — publishes predicted-vs-realized
  per family + the guard-impact (−15.2% → +14.1%) banner. Show-your-work.
- `calibration_real.py` → `data/calibration.json` — REAL reliability diagram from
  the ledger (replaced a synthetic demo) for the ML Lab chart.

**Rule of thumb:** any new board that surfaces picks MUST route probs through
prob_calibration (curate + calibrate) before display, and re-derive fair odds
from the calibrated prob so price and probability never disagree.

## Front-end pages

16 HTML pages, all sharing the same nav and dark-mode style:

| Page | Purpose |
|---|---|
| `index.html` | Dashboard — Play of Day preview, sharp flow, today's slate |
| `play-of-day.html` | Deep dive on the flagship pick — factor decomposition, line shop |
| `mlb.html` | Full slate + pitcher matchups + park/weather grid |
| `models.html` | Model docs + live EV/Kelly calculator |
| `ml-lab.html` | All 4 ML models side-by-side + feature importance + reliability diagram |
| `live.html` | In-game win-expectancy with PBP timeline |
| `simulator.html` | Interactive 10k-game Monte Carlo |
| `backtest.html` | Walk-forward equity curve + segment breakdown |
| `linemaker.html` | Bookmaker view of line movement |
| `arbitrage.html` | Live arb / middle / low-vig scanner |
| `bankroll.html` | Bankroll MC + Kelly heatmap |
| `props.html` | Player prop edges |
| `trends.html` | Sharp money flow + ATS / O/U trends |
| `learn.html` | 12-chapter EdgeStat Academy (Kelly, EV, CLV, variance) |
| `track-record.html` | Public play log + cumulative P&L |
| `about.html` | Mission + founder + roadmap |

Every page is `<200 lines`. Every chart uses Chart.js (CDN). No build step.

---

## How the JS connects to the Python output

The Python pipeline writes JSONs to `data/`. The JS files read them via `fetch('data/foo.json')`. If a JSON is missing, JS falls back to seeded mock data in `js/data.js` so the site never breaks.

Key JS files:
- `js/data.js` — seed data + team lookups
- `js/ml-models.js` — client-side mirrors of the Python probability math
- `js/charts.js` — Chart.js wrappers
- `js/simulator.js` — port of Python simulator for browser-side MC
- `js/ml-lab.js` — ML Lab + Live page wiring
- `js/extras.js` — backtest / linemaker / arbitrage / bankroll wiring
- `js/main.js` — slate table, ticker, page-router for the rest

---

## Conventions Brandon prefers

- Treat him as finance-fluent. Use "edge," "alpha," "CLV," "Kelly," "Sharpe," "drawdown" naturally.
- Lean dark mode, terminal-aesthetic. No light themes.
- Numbers in `JetBrains Mono`. Green for positive edge, red for negative.
- Real ML > buzzword ML. Show the math. Backprop hand-coded, GBM hand-coded, Cholesky hand-coded. No black boxes.
- Concise responses. Skip apologies. Always offer concrete next steps.

---

## What to do when picking this up

If a new Claude session opens this folder, the typical task is one of:

1. **"Deploy it"** — point user to `deploy.bat` or walk them through PAT creation. See `DEPLOY.md`.
2. **"Add more analytics"** — extend the Python stack. Each module is self-contained. After adding one, wire it into `train.py` and a corresponding HTML page.
3. **"Fix or improve a page"** — every HTML page is in the root. Find the corresponding JSON it reads and the JS file that wires it.
4. **"Connect real data"** — replace mock data in `js/data.js` with `fetch('/data/today.json')`. Wire The Odds API in `data_fetcher.py` (needs `ODDS_API_KEY`).
5. **"Make a new desk"** (NBA / NFL / sports cards) — clone the pattern. Most of the Python stack is sport-agnostic; just retrain models on the new sport's data.

Always verify your changes work:
- HTML: open in browser, no console errors
- Python: `python3 <module>.py` (each module is runnable standalone) or `python3 train.py`
- Full smoke test: `python3 -m http.server 8000` then click through all pages

---

## What still doesn't exist (rough roadmap)

- Real-data wiring (currently uses synthetic-but-realistic data)
- Stripe paywall for premium plays
- Mailchimp / ConvertKit hookup for the newsletter form
- Mobile app push alerts on steam moves
- NBA / NFL model extensions
- API access for power users

---

## Quick file index for fast ramp

If you're touching the model: start with `python/mlb_model.py`, `python/features.py`, `python/train.py`.
If you're touching the front-end: start with `index.html`, `js/main.js`, `css/style.css`.
If you're deploying: `DEPLOY.md`, `QUICKSTART.md`, `deploy.bat`, `CNAME`.
If you're debugging: each Python module runs standalone (`python3 sos.py` etc.), each prints diagnostics.

Total LOC across project: ~11,300 lines. ~5 second full pipeline runtime.

---

**Contact:** brandonpleone@gmail.com — Brandon Leone, Southern California.
