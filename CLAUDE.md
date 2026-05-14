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

## Current deployment state

- **GitHub repo created and live:** `https://github.com/Keyvaniath/bpleone-betting` (public)
- **First commit done:** `CNAME` file committed (sets up custom domain pointer)
- **REMAINING:** push the other ~65 files. GitHub Pages not yet enabled. Squarespace DNS for `betting.bpleone.com` may or may not be configured.

The reason the upload stalled: Chrome extensions are blocked from reading the user's local disk and from interacting with `github.com/settings/*` pages. The fastest path forward is one of these:

1. **User runs `deploy.bat`** from this folder — does `git init / add / commit / push` in one shot
2. **User pastes a fine-grained GitHub PAT** scoped only to `bpleone-betting` with `Contents: read+write` — then any agent can push via the sandbox bash
3. **User drag-and-drops** the folder into the GitHub upload tab manually

Don't try to bypass Chrome's restrictions. Don't ask for the account password. PATs and drag-drop are the legit paths.

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
