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

- **2026-07-12 — Live-aware UI ("links to everything that work for LIVE data"):**
  `site_directory.py` -> `data/site_directory.json` = full page catalog (125 pages,
  13 groups) + per-sport live status normalized from the *_state feeds (per-feed
  adapters live in THIS module only — add new sports there). Consumers:
  directory.html (the "Everything" page: searchable, LIVE badges w/ today-counts,
  "next MM/DD" for off-season, shims flagged), nav.js (🗺 Everything in the top bar
  + green live dots / next-date hints on Sports & Players menu entries), index.html
  ("Live now" chip strip under Start-here + "everything →"). Runs in daily-pipeline
  (pre-commit) AND the heartbeat, so badges stay fresh all day. Prod-verified:
  13 groups / 125 links / 8 live sports, zero console errors.

- **2026-07-12 — IA consolidation + P2 polish (audit follow-through, all shipped):**
  nav.js slimmed 113 -> 64 links (dropdowns now Sports 19 / Players 7 / Picks 8 /
  Edges 9 / Models 8 / More 9; cut pages stay reachable by URL — do NOT re-add them
  to the menu without a reason); homepage "Start here" strip (4 canonical doors);
  backtest.html retitled "Performance Analytics" (unique CLV/drawdown content kept,
  no longer claims to be the track record); nba/wnba/nhl-players-real.html renamed
  to clean URLs with redirect shims (never resurrect "(REAL)" scaffolding);
  account.html redirects to login until accounts launch; methodology Brier
  live-fills from calibrated_reliability (70/30 holdout sentence is DATE-STAMPED —
  no live artifact exists for it); track-record's Avg CLV tile uses the SAME
  exact-rows rollup as clv.html (clv_tracker rows + bb leans — never reintroduce
  clv_log.json as a third source); calibration-map guard banner carries a universe
  caption (whole-ledger replay vs recommended-boards record — meant to differ).
  All 8 changes prod-verified. Both follow-up chips dismissed (done in-session).

- **2026-07-11/12 — THE DUPLICATE-WAGER CORRECTION (newest, read first — the headline
  numbers DROPPED on purpose):** a 5-dimension full-site audit found the flagship
  proof stack resting on a physically impossible UFC record (fight_r1_finish_yes:
  60.4% round-1 finishes graded against a ~23% price). Investigation: grading was
  CORRECT; the corruption was DUPLICATION — pick_id includes the snapshot date, so a
  future event on a board for days re-entered daily (182 UFC "picks" = 26 fights; one
  fight counted 13x), plus twin boards (top_25_board + lock_of_day) double-recorded
  the same wager. Ledger-wide: 1,509 duplicate picks (781 settled, +335u phantom).
  FIX (all_picks_tracker.py, commit 226efceb4): `_collapse_duplicate_wagers()` voids
  extras keyed by wager identity + byte-identical outcome (idempotent, every run) +
  an ADD-GUARD (skip picks whose wager is already pending; event sports also skip
  14-day-settled repeats) + `_reconcile_settled_voids` respects duplicate-voids.
  CONSEQUENCE (final post-correction state, verified on prod 2026-07-12): settled
  6,803→6,049; curated book +300u/+30.3% → **+185u/+23.8%**; durable book
  +550u/65.1% → **+147.6u/35.7% (CI floor 30.0)**; UFC family → **23-14/+67.7u**.
  Still a real, defensible edge — just honest. **Do not "fix" the lower numbers
  back — they are the correct ones.** Never hardcode pre-collapse figures
  (+550u durable, +65.1%, UFC +139.8%/+216u, curated +300u/+30.3%).
  FOLLOW-THROUGH (same day): a pick can now be BOTH settled and voided (dup copy),
  so every consumer's record predicate must be `settled AND NOT voided`. A 6-agent
  sweep audited all 30 ledger consumers: 17 had the stale filter (fixed in
  4a6f2f679 — incl. prob_calibration's curation stats, recalibration's isotonic
  fit, confluence double-agreement, d1_sync logging dups as W/L); 12 safe; 1 n/a.
  Any NEW ledger consumer must use the canonical predicate. Also fixed: a dict
  `team` field crashed the daily pipeline's debug print (slate_player_pot) —
  display code must never abort the run.
  Also shipped from the audit: honest "today" slates (espn_generic + nba/nhl
  pipelines only count games starting today ET — NFL was showing September Week 1 as
  "today"), slate-incomplete banner (index+mlb read data_health's local-vs-upstream
  gap), WWNBA typo, canonical track-record hero link, dead redirect anchors,
  methodology mobile table. Remaining: nav IA consolidation + P2 polish (chips
  task_4dd41347 / task_f2ad5edb). Audit also confirmed: 0 broken links across all
  128 pages, ~130 JSON endpoints all valid, mobile/responsive strong.
  Daily 9am-PT alpha tweet pipeline: alpha_tweet.py → data/alpha_tweet.json →
  "Post to X" one-tap card on alpha-pick.html (+ scheduled task
  daily-alpha-tweet-9am-pt). Posting is MANUAL by design.

- **2026-07-08 — "The One Pick" alpha single-pick tracker:**
  Brandon wanted the single best Alpha pick per day tracked separately (the full board
  "feels like an ETF"). `alpha_pick_record.py` → `alpha_pick_record.json` → card on
  alpha-pick.html. Rule: the single highest model-EV **MLB player prop** each slate,
  flat 1u, backfilled from the ledger, selected on pre-game prob+odds ONLY (no
  hindsight). Two selection lessons baked in: (1) game moneylines void in the ledger →
  the old headline "record" was 0-0/14-void → restrict to player props; (2) the live
  game-line Alpha prob cap of 0.85 is WRONG for props (it excluded the proven
  hrr-under family ~0.86 and left the model's overrated coinflip props) → prop ceiling
  raised to 0.90. Result: 32-5, 86% hit, +50% ROI (51-day backfill) beside the curated
  board's +30%; honest framing = both clear a real edge but one bet/day is far higher
  variance (~50 vs ~1000). Wired into daily-pipeline after alpha_pod_tracker.
  **Follow-up "Alpha Props" (same module, payload.props_slate): the One Pick + up to 2
  diversified extras = highest-EV pick from each NEXT distinct market family, hard
  no-two-share-a-market rule (genuinely different bets, never a re-stamp). Design
  chosen by a 4-way Workflow design panel; 2 adversarial verifier agents CONFIRMED the
  record. TWO GUARDS: dedup by (player,market,odds) — the ledger stores each wager
  TWICE (top_25_board + lock_of_day) so top-N would double-count; families chosen by
  pre-game EV only, never past ROI. Slate 48-17 / 74% / +28% / ~1.75/day; per-slot
  breakdown shows the edge is ALL in the anchor (slot0 +54%, diversifiers ~breakeven).**

- **2026-07-02→06 — Rigor ladder + synthetic decontamination:**
  - **Walk-forward LADDER** (`forward_test.py`): the forward test now auto-freezes a NEW
    cut-set rung whenever the newest one matures (>=400 settled, >=7d apart, cap 12).
    Rung 1 (6/22) matured at n=540: curated +42.3% vs raw -13.3%, zero hindsight. Rung 2
    froze 7/02. Ladder table on track-record.html; top-level artifact fields mirror rung 1.
  - **Family durability scorecard** (`family_durability.py` -> track-record card): every
    surviving family tiered by bootstrap-CI floor + split-half stability. 2 DURABLE
    carriers (fight_r1_finish_yes n=155 CI-floor +105%; mlb_hrr_3.5_under n=612).
    "Durable book" aggregate: ~767 settled, +62% ROI, CI floor ~+54%.
  - **SYNTHETIC DECONTAMINATION (do not regress):** data/track_record.json is the
    deprecated SYNTHETIC feed (118k fake props, FROZEN 6/02). Purged from all public
    surfaces: dow_pl.py + clv_per_bet.py + daily_summary.py + residuals.py + anomalies.py
    now read the REAL ledger (adapter maps picks -> {date, player: player_or_matchup,
    market, model_projection: projection, actual: outcome.actual}); the CLV-per-bet card
    auto-hides until real prop closes exist. 10 dead modules REMOVED from the workflows
    (walk_forward, player_bias, learning_curves, loop_value, streak_chart_data,
    training_progress, per_prop_ci, multiplier_tuner, context_calibration,
    backfill_context). Legacy chain still wired but verified no-op (all corrections 1.0):
    outcomes.py / calibration_runner.py / model_trainer.py -- final retirement is a
    flagged owner task; calibration_runner.load_corrections() feeds pipeline.py so
    disconnecting it is a MODEL-BEHAVIOR decision, don't do it casually.
  - **Stale-number policy:** the curation headline (+14.1%/-15.2% era) drifted badly.
    calibration-map/track-record/methodology now LIVE-FILL those numbers from
    curation_oos_validation.json in_sample -- never hardcode ledger-derived numbers in HTML.
  - Picks-hub data fixes: convergence_detector stamps each scoreboard's sport (was all
    "MLB"); todays_picks maps label/batter subjects + infers sport (no "?" rows). Homepage
    Locks card labeled as quarter-Kelly basis (net/ROI are on ~21u risked, not 1u flat).

- **2026-06-29 — Picks hub + ledger-integrity incident (read first):**
  - **Picks hub** (`picks.html` + `python/todays_picks.py` -> `data/todays_picks.json`):
    one filterable board consolidating the curated pick boards (Locks/Alpha/Best-Bets/
    Consensus/Top-Plays/Convergence/Fades). Six board pages (todays-top-plays, top-3-picks,
    locks-of-day, consensus-picks, convergence, fade-picks) are now **redirect stubs** ->
    `picks.html#<category>`. Template for the rest of `CONSOLIDATION-ROADMAP.md`.
  - **DATA-LOSS INCIDENT + safeguards (do NOT remove these):** a cron git-race committed
    merge-conflict markers into `data/*.json`; `all_picks_ledger.json` became unparseable,
    so `all_picks_tracker._load()` returned `{}` and the next run **reset the ledger from
    scratch** (6,506 settled -> 305, curated +235u -> +8.9u). Three layers now protect it:
    (1) **marker guard** in all 5 committing workflows (never commit conflict markers --
    abort+retry); (2) **tripwire** in `all_picks_tracker` (refuses to overwrite the ledger
    if settled would drop >50% vs `data/ledger_highwater.json`, an independent high-water
    sidecar that survives a corrupted ledger); (3) recovery-from-git pattern. If you ever
    see the ledger shrink, restore from the last good commit (`git show <sha>:data/
    all_picks_ledger.json`) -- the cron then re-accumulates on top.
  - Earlier 2026-06-28: dead-board cleanup (17 removed), homepage proof-hero (forward-test
    + bootstrap CI lead the receipts band), data-health canary honesty (quota-exhausted =
    yellow not red) + desk-coverage check, page-weight digests (recent_picks.json).

- **2026-06-19 session additions (read first — newest state):**
  - **17 sport desks, all live** (`sport_coverage.py` / sport-coverage.html). Added
    **Tennis** as a full desk: `tennis_pipeline.py` pulls upcoming ATP/WTA from ESPN's
    free tennis scoreboard → `tennis_state.json` (12 prop modules were starved — nothing
    wrote that file). `tennis.html` + nav + surface-adjusted ELO match-win/ace boards.
    NB: ESPN serves whole future brackets + TBD placeholders, so the pipeline filters
    placeholders and keeps only today..tomorrow by each match's own start date.
  - **Per-sport settlement wired** for the niche desks via `*_pot_history.py` (snapshot
    the day's best edge, settle from a free feed): KBO (`kbo_pot_history`, Daum hermes —
    fixed a key bug: real keys are homeTeamName/homeResult/gameStatus/homeWlt), CS
    (`cs_pot_history`, bo3.gg slug-parse), NCAA Baseball (`cws_pot_history`, ESPN-by-id),
    Tennis (`tennis_pot_history`, ESPN finals). Each flips its sport_coverage row from
    "no outcome feed" → "settlement wired, pending" → a real W-L once games complete.
    All surfaced on pod-history.html "Per-Sport Desk Records".
  - **Desk-level curation** (`prob_calibration.sport_curation_report` /
    `proven_negative_sports`): raw-vs-curated net per whole sport, only flags a desk
    negative AFTER family curation (so MLB's −1021u raw isn't cut — its curated subset is
    the +14% engine). Published on calibration-map.html. Money map: MLB-PP +181u/81%,
    UFC +75u, Golf +21u profitable; F1/NHL underperforming; none hard-cut.
  - **golf**: fixed `golf_live_tracker` (reads nested `active_tournament`) + `golf_bestbet`
    (gates position bets on `golf_state.is_in_progress`, not the under-reporting live tracker).
  - **F1 POLE** was already fixed (normalized one-winner `pole_share`, flag only the
    favourite ≥18%); the −44u in the ledger is historical/sunk. TOP_3/TOP_6 are valid marginals.
  - **Go-official layer (compliance + monetization + reliability)**: legal/trust pages
    (terms/privacy/responsible-gambling/disclaimer/affiliate-disclosure/data-sources),
    site-wide `js/compliance.js` (21+ age gate + RG footer, auto-loaded by nav.js),
    affiliate framework (`sportsbooks.html` + `js/affiliate-config.js`, disabled until
    real links), reliability (`data_health.py` freshness canary + `status.html` +
    `health-alert.yml`), and a code-complete subscription backend (Stripe billing in
    `cloudflare-worker/src/billing.js` + `js/premium.js` + `pricing.html`, inert until
    configured). Owner-action checklist + deploy steps in **GO-OFFICIAL.md** /
    **SUBSCRIPTION_SETUP.md** (LLC, attorney, data license, Stripe account).
  - **Known data-blocked (CORRECTED 2026-06-23):** `ODDS_API_KEY` is NOT lapsed/unset —
    `odds_key_preflight.py` validated it live in the cron: the secret IS set and the key
    is VALID (returns 40 sports), but its monthly quota is **EXHAUSTED (1 request left;
    a free/low tier the pipeline burned through)**. So player-prop BOOK lines are dark for
    lack of REQUEST BUDGET, not a missing key. The lever is **raising the plan tier** (more
    requests/mo) — NOT buying a new key. Game lines come free from ESPN regardless. Live
    state on status.html (Odds feed row); setup in ODDS_KEY_SETUP.md.

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
- **Odds feeds (2026-06 update):** `ODDS_API_KEY` (paid The Odds API) is still lapsed,
  BUT **game-line odds are no longer dependent on it** — `python/espn_odds.py` pulls
  live DraftKings moneyline/total/spread from ESPN's free scoreboard API (no key) →
  `data/espn_odds.json`, and `book_vs_model_team.py` now edges off those fresh lines
  (preferred over the frozen matchups.json/Bovada market). ESPN team abbreviations are
  normalized to the model's vocab (TB→TBR, KC→KCR, SD→SDP, WSH→WSN, SF→SFG, ATH→OAK).
  Runs in run_props_batch before book_vs_model_team. STILL DARK: **player-prop** book
  odds (ESPN scoreboard only carries game lines), so the PrizePicks `pp_advantage`
  path stays dormant until the paid key returns. Everything odds-INDEPENDENT (model
  boards, calibration, recalibration) works regardless.
  NB: book_vs_model `_shrink_toward_book` defers HARD to the sharp MLB ML close
  (cap 0.80, slope ×3) so model overconfidence can't surface as a fake +50% edge.
- **Free-data stack built on espn_odds (2026-06):**
  - `espn_odds.py` now pulls ALL in-season leagues (MLB/NBA/NHL/WNBA) and appends a
    timestamped snapshot per game-day to `data/odds_history.json` each run (only on a
    line move; capped/pruned 8 days). Wired into the heartbeat (~12×/day).
  - `line_movement.py` → `line-movement.html`: open→current moneyline (de-vig pp) +
    total moves; STEAM flag. `clv_tracker.py` → `clv.html`: Closing Line Value for
    the model's game-line leans (did the close move to our side) + beat-the-close
    rate. Both consume odds_history; "pending" until ≥2 snapshots accrue per game.
  - `prizepicks_lines.py` → `data/prizepicks_lines.json`: free multi-sport PrizePicks
    menu from their public API (browser headers + 1.5s inter-league delay to dodge
    429). pickem.py still pulls PP-MLB for the model-scored value board; this is the
    broader live menu. DraftKings player props remain NOT free (the one paid-gated
    cross-check). All run in run_props_batch.
- **Strategy Simulator (2026-06):** `strategy-sim.html` + `python/strategy_sim.py` —
  interactive replay of the ENTIRE settled ledger (compact columnar deck
  `data/strategy_sim.json`, regenerated in pipeline + heartbeat). Flat 1u or
  unit-Kelly (sized off a FIXED 100u bank, non-compounding — compounding an
  in-sample hit rate prints billion-unit fantasy curves; tried, caught, fixed),
  raw vs calibrated prob, curation toggles, prob floor, sport + family filters
  (an explicit family pick overrides the curation drops). Every setup is a
  shareable URL. "Firehose flat, no filters" reproduces the public track record
  EXACTLY (it replays the ledger's own payouts). The index "prove it" strip and
  track-record "Honest Book vs Firehose" chart read the same deck.
- **Situational rollup (2026-06):** `anomaly_detector.py` aggregates STEAM_MOVE
  (line_movement movers), COMPOUND_BULLPEN + PEN_MISMATCH (bullpen_freshness),
  UMP_K_EXTREME (matchups ump assignment) alongside the original residual/streak
  types → `anomalies.html`. ORDERING MATTERS: it must run AFTER run_props_batch +
  bullpen_freshness (it does — moved 2026-06-09; also refreshes in the heartbeat).
- **Bullpen-fatigue bridge (2026-06):** `mlb_bullpen_freshness.py` emits
  `teams[{team, ip_2d, tier, fatigue_index}]` — the vocab `mlb_innings_4_6/7_9_totals`
  consume (continuous 0–1, 2 IP→0 / 8→0.5 / 14+→1, NORMAL≈the old 0.5 default).
  Before this the generators' fatigue adjustment was a silent no-op (vocab
  mismatch — same bug class as the NHL goalie fix). game.html shows the bullpen /
  starter-leash / umpire / compound-signal rows on the game card.
- **WNBA live scoring environment (2026-06):** `wnba_scoring_env.py` — game-level
  factor from REAL results (team_form_wnba avg PF+PA vs league), Bayesian-shrunk
  (k=8) + clamped [0.92, 1.08], multiplied into all six WNBA prop generators'
  pace factor (the static preseason tables stay as the baseline; this is the live
  trim — and it covers the 2026 expansion teams the static tables don't know).
- **2026 World Cup desk (2026-06):** `worldcup_model.py` → `data/worldcup_cards.json`
  → `worldcup.html` (in the Sports nav + a dashboard card). A proper **3-WAY**
  match model (soccer needs draws — ~25% of group games): strength = coarse FIFA
  seed bands (`SEED_BAND`, labeled on every card) blended with in-tournament record
  elo, seed weight `2/(2+gp)` so the tournament's own results take over by the
  knockouts. Goals = per-side expected from the elo gap on an exp scale (`HALF_GOALS`
  1.36, `GOAL_K` 0.50) so the TOTAL flexes with mismatch (was a flat 2.6 — over/under
  is now a real per-game signal) → independent-Poisson grid → 1X2 / O2.5 / BTTS.
  `_recommend()` attaches `rec` {prediction, props[]} per card + a ranked `best_bets`
  board; `worldcup.html` leads each card with an "EdgeStat's Pick" strip + anytime
  scorer chip. **Fixtures come ONLY from the live scoreboard (state="pre"); the
  state-file fallback was removed** (its stale status leaked live/finished games as
  upcoming cards) + an orientation-agnostic "already played" guard. Model picks flow
  to the ledger as `wc_model_*` (experimental) and settle off the soccer grader.
  **Ordering constraint:** `worldcup_model` must run BEFORE `soccer_goalscorer_props`
  (which now reads WC fixtures from `worldcup_cards.json`) and before `run_props_batch`
  — enforced in daily-pipeline; both refresh in the 2h heartbeat through July 19.
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

**`python/recalibration.py`** — GENERATOR-LEVEL recalibration (added 2026-06). Learns
a per-family MONOTONIC isotonic transform (model-predicted prob → realized rate) from
the settled ledger: prediction-bucketed + Bayesian-shrunk + pool-adjacent-violators,
with family-average / identity fallbacks. Collapses the raw model's calibration error
**ECE 11.2% → 2.7%** (Brier 0.235 → 0.203; held-out fit-on-70%/test-on-30%: ECE
12.6% → 5.4%, so it generalizes). `recalibrate(raw, market)` is the public transform.
Output `data/recalibration_map.json`; surfaced on calibration-map.html. Runs in the
pipeline after the ledger build. HONEST FRAMING: this does NOT create ROI (pricing at
your own fair odds is 0-EV); it makes the model's numbers TRUE and makes book-vs-model
edges real (not inflated by overconfidence) once the odds feed returns.

**Applied upstream (2026-06, "sharpen the model"):** the recalibration engine is now
folded in at the SOURCE, not just at display:
1. `prob_calibration.empirical_calibrate` / `calibrate_play` route their family blend
   through `recalibration.recalibrate_family()`, so EVERY board gets the bucketed
   isotonic curve (held-out validated) instead of a flat family average.
2. `game_calibrated_probs.py` → `data/game_calibrated.json`: game-line win probs are
   too thin in the ledger for outcome calibration, so they're shrunk toward the sharp
   de-vigged free book line (cap 0.80, ×3). Surfaced on game.html as a "Book-calibrated"
   sub-line under the win-prob bar. Does NOT mutate today.json (no double-shrink).
3. `all_picks_tracker.py` stamps an ADDITIVE `p_calibrated` on every ledger pick with a
   usable raw prob (via `_calibrated_prob` → `recalibrate`), keeping `p_predicted` RAW
   so the learning loop never trains on its own calibrated output (non-circular). Emits
   a `calibrated_reliability` block (ECE raw 0.109 → cal 0.027 in-sample over 4,997
   settled; held-out in recalibration_map.json) into ledger_summary.json. `n_calibrated`
   picks stamped per run. verify_calibration guards the stamp (additive + non-vacuous).

**Still TODO (when the paid odds feed returns):** apply `recalibrate()` in the PROP
edge-computation path (book_vs_model already defers to the book for game lines) so
displayed prop edges use the honest prob. Do it additively; display boards already
calibrate, so don't double-calibrate.

**`python/verify_calibration.py`** — regression test proving the guards aren't
vacuous (13 checks: curation, calibration, overconfidence, side/line-aware book-prop
guard, AND recalibration ECE/Brier-improve + monotonic + identity). Runs in the daily
pipeline; fails the build if a guard regresses.

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
