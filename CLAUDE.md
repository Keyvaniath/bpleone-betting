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

- **2026-10-26 (late) — LOCKS: 543 OF 921 COULD NEVER SETTLE.** locks_history
  (homepage Locks card) took top_25[:5] blind: 384 KBO "1+ TB" props (no KBO
  box feed) and 123 MLB-PP props whose box line never arrived sat "pending"
  since May; MLB game-line locks read historical_games.json, which never
  existed. NOW: a lock is made only on a gradable market (_gradable: MLB props
  via player_gamelogs, game lines via historical_<sport>); MLB game-line locks
  mirror the ledger's lock_of_day row (verified final, DK price, totals voids;
  dup-collapse voids ignored); anything still pending after 7 days is VOID
  (reason stored, n_void + n_void_by_sport published, homepage says so). The
  settled record is unchanged in substance (307-59 -> 308-60, +45.5% on
  ¼-Kelly risked; props and ledger agreed on every overlap). The May MLB game
  locks (35) predate the ledger harvest and the rolling finals window; they
  were never counted and are void, not regraded (¼-Kelly stakes, <1u total).

- **2026-10-26 (late) — AWAY-SIDE TEAM CODES NEVER GRADED.** MLB game lines
  matched picks to finals by whole-string substring, which tolerates
  TBR/TB, KCR/KC, SDP/SD, SFG/SF only for the HOME team ('cle @ tb' is inside
  'cle @ tbr'; 'tb @ mil' is not inside 'tbr @ mil'). With one of those teams
  AWAY, the pick aged into "unsettleable" (24 curated voids since 9/19, plus
  every World Series game in Milwaukee sitting pending). Fixed:
  all_picks_tracker._mlb_same_game (side by side, prefix-tolerant, rewrite
  aliases) at all three MLB sites; locks_of_day._same_game likewise.
  outage_backfill v5 refetches the long finals window so the September voids
  can grade. Picks on games that never existed (Oct "TBR @ NYY", "SDP @ LAD"
  -- stale-slate phantoms) find no final and stay void, correctly.

- **2026-10-26 (late) — POD_PL NOW GRADED BY THE LEDGER.** pod_pl.json (homepage
  POD card, /pod-history, track-record, mlb.html) graded ITSELF: matchup
  strings vs a rolling historical_mlb window (4 verified-wrong results, e.g.
  9/01 CHW ML "won", final CHW 3 @ HOU 6; 7/02 MIA@COL O12 "lost", final 4-14),
  its own recorded prices (in-play +940, placeholder -110/+100, fake 8.5
  totals; the "price_suspect" repair paid model-fair odds, still not a real
  price), and it logged DEMO_SLATE's CIN @ COL -110 and the All-Star game.
  None of the 10/23-10/26 restatements reached it. NOW: pod_pl_tracker mirrors
  each entry's ledger row (source pod, or also_sources pod) -- result, payout
  at book_american, voids -- and never grades. 49 entries the ledger never
  carried: data/pod_pl_regrade_2026_10.json (tools/build_pod_pl_regrade.py:
  DK pre-game snapshot -> event_id/price, final by event_id or the ledger's
  verified final; 12 graded, 37 void). Voids are excluded from W-L. RESTATED
  34-28 +4.49u (+7.24%) -> 33-25-2 +4.24u (+7.32%), 58 void; disclosed on
  pod-history. pod_history.json (pod_history.py) is a separate dead tracker
  (settles on a track_record `play_hit` field that does not exist: 0 of 294
  ever settled) -- read only by multi_sport_pot_rollup; not on any page.

- **2026-10-26 (late) — MLB TOTALS: LINES NO BOOK POSTED.** The 10/26 pass voided
  only POD totals on the 8.5 placeholder; Top 25 and the Under Alerts read the
  same today.json total. tools/build_total_lines_audit.py checks every settled
  MLB total (282, all curated) against what books posted BEFORE first pitch
  (git history of espn_odds.json [DK], odds_history.json [Odds API],
  multi_book_lines.json [commit time < DK commence_time]). 134 on DK's line ->
  graded at DK's real over/under juice (repriced_total); 47 on a line no book
  posted pre-game (mostly "UNDER 8.5" with DK at 6.5-7; POD "UNDER 15.5" /
  "OVER 4.5" = in-play) -> voided (unposted_total). They had gone 30-17: the
  fake 8.5 manufactured UNDER edges. 101 on another book's pre-game line or with
  no DK snapshot stay as recorded (they net -11.1u, so keeping them flatters
  nothing). Seed data/ml_reprice_2026_10d.json (B's no-op line_real rows yield
  to it). RESTATED curated 932-429 +195.69u (+14.38%) -> 902-412 +184.34u
  (+14.03%); Alpha untouched (no Alpha pick was a total). Also: team-total and
  alt-total modules skip games with no book total instead of assuming 8.5.
  GOTCHA for these audits: key snapshots by the ET date of commence_time, not
  the snapshot day -- series games share a matchup string.

- **2026-10-26 (night) — IN-PLAY PRICES + THE DK STANDARD FOR ALL HISTORY.** POD's
  moneyline record (+167% ROI, n=14) was built on impossible prices: TBR +940,
  PIT +840, CHW +525, DET +398, KCR +310 -- DraftKings pre-game had -137 / +102
  / -142 / +119 / -111. bovada._market_by_desc took the FIRST "Moneyline"
  market, and Bovada lists in-play / period markets under the same name (and
  live events in the same feed). FIX: bovada skips live events + non-full-game
  periods; pipeline uses the DK line FIRST whenever espn_odds has the game.
  HISTORY: every settled MLB moneyline without book_american (179 with a DK
  line) graded at the DK pre-game line -- data/ml_reprice_2026_10c.json, kind
  dk_standard, lowest precedence after seeds A/B. Gap distribution: 0-5c 93,
  5-15c 54, 15-50c 24 (all tiny), >50c 8 (+23.50u -> +3.61u: the garbage).
  14 with no DK line keep their (plausible) recorded price. RESTATED: curated
  932-429 +216.50u (+15.91%) -> +195.69u (+14.38%), W-L unchanged; **Alpha v2
  18-16 +9.51u -> -1.63u (-4.79%)**, all-time 66-38 +22.87u -> +11.73u
  (+11.28%) -- 10/13 TBR "+940" alone was +9.40u of it (real +0.73u). Alpha
  SELECTS on EV vs the recorded price, so a bad price looked like a huge edge
  and got picked: price errors concentrate in the selected pick. Disclosed:
  ledger_summary.price_corrections (track-record) + alpha_pick_record
  .price_corrections (alpha-pick page). **RULE: a recorded price that implies a
  >50-cent disagreement with DK is a data error, not an edge -- any selector
  that ranks on edge vs recorded price must be fed the house price.**

- **2026-10-26 (eve) — THE OTHER PLACEHOLDERS: +100 AND 8.5 (read with the 10/23
  entry).** A headless crawl of all 135 live pages (Chrome --dump-dom, console
  + visible NaN/undefined scan) showed play-of-day "MIL_ML Market price +100 -
  Total 8.5, book null" with DK at MIL -104 / total 7.0. pipeline.py priced
  ONLY from The Odds API (no key) and Bovada (0 games from CI IPs) and never
  read espn_odds.json, then filled `total or 8.5`, `ml_away or 100`, `ml_home
  or -110`; mlb_model's GameInput defaulted the same and priced every total at
  -110. The 10/23 re-price searched only for -110, so the +100 away side was
  never corrected. FIX: pipeline falls back to espn_odds.json DK lines (<6h
  old), carries real over/under juice; GameInput defaults are None and an
  unpriced market gets NO edge and NO recommendation (POD can be "no play").
  HISTORY: data/ml_reprice_2026_10b.json (tools/build_reprice_plus100.py, same
  git-history method) applied by ml_reprice.apply_ledger in every build: 29
  moneylines re-priced from a fake +100 (+3.0u -> -1.31u; 27 top_25_board, 2
  pod; LAD -226 had paid +1.00u), 9 pod totals VOIDED (line 8.5 never existed
  at DK: real 9.5/11.0/8.0/none), 5 kept (8.5 was real). Top 25 + POD ARE
  curated (curated = by SOURCE; there is no per-pick `curated` flag -- I first
  checked that nonexistent flag and wrongly said "headline unchanged"):
  curated 936-434 +16.02% (+219.45u) -> 932-429 +15.91% (+216.50u), disclosed
  on track-record via ledger_summary.price_corrections (both the 10/23 and
  10/26 corrections, which the page had never shown). Alpha v2 18-16 +9.59u -> +9.51u
  (+27.97%); all-time 66-38 +22.95u -> +22.87u (+21.99%) -- only 8/17 STL
  (+100 -> DK -109) moves. **RULE: no price default anywhere, of any value;
  search for EVERY placeholder a producer could emit, not the one you saw.**
  Also: pipeline_health.json had TWO writers in different shapes (watchdog
  "OK"/file_health vs pipeline_health.py "ok"/artifacts) -> audit.html showed
  "7/undefined" and index.html a false "aging" banner; pipeline_health.py now
  writes artifact_health.json. nhl-players read pts_per_game (data:
  points_per_game); ml-lab.js threw on a missing #liveBigEvent before drawing
  the live chart. Scanner gap closed: `.get(k, -110)` (negative literal =
  UnaryOp) was invisible to scan_getnum.

- **2026-10-26 (pm) — CRASH AUDIT: EVERY CI MODULE REPLAYED ON BAD DAYS.** Method:
  a sandbox copy replays all 363 python commands of daily-pipeline +
  heartbeat + live-games + training-loop with the network cut (sitecustomize
  denies sockets, no-op sleep) under three data states -- as-is, "off-day"
  (slate lists emptied) and "nulls" (numeric fields of the first record of
  every list set to None). Round 1: 11 / 13 / 21 modules crashed; now 2 / 2 /
  2-3, and those are network-only (outcomes.py, smoke_tests.py). Fixed:
  (1) **`X.get(k, NUM)` feeding math/compare/assignment** -- the default only
  covers a MISSING key; a stored None crashed. 586 sites in 251 files rewritten
  mechanically: default 0 -> `(X.get(k) or 0)`, else `_nz(X.get(k), D)` (None-
  only fallback, keeps a real 0); assignments to a name the function later
  tests `is None` were left alone. Verified at the AST level (HEAD with the
  rewrite applied == working tree, modulo the helper) -- that check caught a
  dropped-paren bug in the first pass (`(a or {}).get(k, 0)` -> `a or {}.get(k)
  or 0`) before it shipped. **RULE: write `(d.get(k) or 0)` / `_nz(d.get(k),
  D)`, never `d.get(k, D)` in arithmetic.** (2) **Failure-path payloads must be
  shape-identical**: espn_generic (8 sport pipelines), lol_model, ufc_matchup,
  cfb_model, nfl_stub, training_convergence all crashed their own print on the
  empty/error shape. (3) **espn_generic no longer clobbers a good board with
  0 games when ESPN is unreachable** (keeps a <6h-old board, flags
  fetch_error, leaves generated_at so health ages it). (4) **D1 sync had not
  completed since 6/28**: it re-sent all 15k picks (~150 serial requests)
  every heartbeat inside a 1-min step, timed out, and the settle pass (after
  every insert) never ran. Now incremental (digest per pick in
  data/.d1_sync_digest.json), 30s self-budget, progress saved per chunk,
  entry_odds = book_american first, red only after 24h with no progress.
  (5) **Bounded heartbeat steps (timeout-minutes + continue-on-error) timed out
  invisibly** -- killed before `|| echo` runs. They now carry ids `soft_N` and
  the gate reads `toJSON(steps)` outcomes. (6) The last 12 python `|| true`
  steps (live-games sport pipelines, alpha_email, d1_sync, live_alerter,
  multi_book_lines, preflight, data_health) now record-and-continue. (7) The
  Worker's /db/log-picks + /db/settle-picks accepted anyone's POST; a
  SYNC_TOKEN check is staged (enforced only once Brandon sets the Worker
  secret + EDGESTAT_SYNC_TOKEN GitHub secret and deploys -- no behaviour change
  until then). Harness: tools/crash_replay/ (README there) -- rerun it after
  any broad refactor.

- **2026-10-26 — TWO RED WORKFLOWS, NO CASCADE (the 10/22 design working):**
  heartbeat + daily-pipeline went red every run 10/25-10/26 naming exactly
  calibration_status.py and cross_sport_parlay_builder.py while every other
  module ran (data stayed fresh, health green). Both were summary PRINTS:
  `{p.get('k', 0):.1f}` with the key present as None (MLB off-day), and a
  0-legs payload whose keys differed from the success payload. Fixed with
  `_fmtv(v, spec, dflt)` at 38 sites in 15 files (format a real value, print
  the default for None, never raise) and a shape-identical empty payload.
  **RULE: never write `{x.get(k, d):spec}` -- use `_fmtv(x.get(k), 'spec', d)`;
  the sweep regex is in the 10/26 commit message.** The new Gmail filter
  delivered the failure email to Brandon's Inbox (starred) -- the alert loop
  works end to end.

- **2026-10-23 (night) — MONEYLINES WERE GRADED AT A PLACEHOLDER -110 (read before
  touching any price):** tonight's Alpha read "MIL ML @ -110" with DK at -192.
  todays_top_plays._fair_odds_for_source filled -110 when a slate had no price
  yet (and the shrink lost its market anchor, 72% -> 59.8%) -> fake +12.9%
  edge, inflated payouts, the -150 juice gate bypassed. 77 settled MLB
  moneylines (76 curated) affected; 10 Alpha v2 days (7 would NOT have cleared
  the gate at the real price). FIX: `book_american` = the real DK line;
  `_price_american()` (book first) prices settlement/regrade/juice gate; Alpha
  `_px()` prices gate/edge/payout (locks still key on recorded fair_american);
  intake prices every MLB moneyline from espn_odds and DROPS unpriced ones;
  todays_top_plays never defaults a moneyline. History re-priced from the git
  history of espn_odds.json (data/ml_reprice_2026_10.json): 68 re-priced, 9
  'unpriced' voids (never resurrected). **ml_reprice.apply_ledger runs INSIDE
  every ledger build** -- as a one-shot it was overwritten by a concurrent
  live-games ledger commit. **RULE: a one-shot data correction to the ledger is
  not durable (4 workflows rebuild it); make it idempotent and apply it in the
  build.** Tonight's lock WITHDRAWN pre-game (lock `withdrawn` field; page +
  email show the correction). Restated: curated 943-436 +17.21% -> 936-434
  +16.02%; Alpha v2 +11.51u -> +9.59u (+28.2%); Alpha all-time +22.1%.

- **2026-10-23 — DAILY ALPHA EMAIL IS LIVE, PASSWORD-FREE (Brandon's choice):**
  daily-pipeline posts data/alpha_email.json ONCE per date (marker
  `<!-- alpha-date:YYYY-MM-DD -->`) as a comment on issue #46 "📬 EdgeStat
  daily Alpha", which @-mentions the owner, so GitHub emails it; off-season
  posts nothing. Verified: the 10/23 card landed in his Inbox, starred +
  important + INBOX/CI Failures (his Gmail filter: from notifications@github.com,
  subject bpleone-betting). NB his inbox is swept to Trash by something other
  than a filter -- the star/important flags are the defense. The SMTP
  `--send-self` path stays wired but inert without secrets. Never close #46.

- **2026-10-23 — HEADLINE IS NOW ALL-TIME (Brandon decided: "All-time, merge archive"):**
  ledger_summary's headline = working ledger + data/ledger_archive.json.
  The archive was seeded with 5,946 settled picks the OLD tail-cut eviction
  destroyed (May 20 - Jun 7), rebuilt from git: each pick at its FINAL state
  across daily ledger versions, today's void rules re-applied in memory with
  the live ledger (duplicate collapse dropped 323 phantom copies; 24 recovered
  twins that would have displaced LIVE rows were dropped instead -- live rows
  are never altered), audited for same-event repeats (0). Restated: firehose
  12,448 @ -18.25% -> 18,394 @ -19.19%; curated 769-370 +14.22% -> 943-436
  +17.21% (the 242 recovered curated picks are MLB/MLB-PP, 0 same-day twins).
  `working_ledger_only` + `restatement` blocks keep the old basis auditable;
  track-record shows a dated note. Family evidence, calibration, the NFL era
  split stay on the WORKING ledger (they describe the current model).
  strategy_sim includes the archive so "firehose flat" still equals the
  headline. Eviction archives `also_sources` + `p_predicted` now.

- **2026-10-23 (final) — THE HEALTH MONITOR WAS BLIND IN CI:** data_health aged
  state files by os.path.getmtime, and in an Actions checkout mtime = checkout
  time, so in the run that PUBLISHES data_health.json every file looked ~0 min
  old -- the live-poller, golf and per-sport staleness checks could never fire.
  Ages now come from each artifact's generated_at (mtime fallback). Thresholds
  track the DELIVERED cadence: live-games.yml is scheduled every 20 min but
  GitHub runs it ~5x/day, so live data >60 min behind = yellow, >240 = red.
  Golf now refreshes on the heartbeat (golf_pipeline + golf_live_tracker; it was
  daily-only) with a 300-min bar. 8 producers added to DESK_FRESHNESS. ALSO
  this day: every remaining `|| true` workflow step (154) records failure
  (soft by design: odds_key_preflight, multi_book_lines, alpha_email
  --send-self, alerters, data_health); daily-pipeline has a concurrency group.
  **RULE: never measure freshness by file mtime in CI -- read generated_at.**

- **2026-10-23 (latest) — NBA/NHL PROPS WERE PRICED OFF 2024-25 TABLES + PRESEASON:**
  the 27 NBA/NHL/WNBA prop generators carry hard-coded PLAYER_DB tables
  (2024-25 averages AND teams). A real-stats layer existed
  (espn_player_stats -> player_stats_<sport>.json -> real_stats_lookup) but:
  (1) the athlete gamelog it read is CURRENT season only with PRESEASON mixed
  in (Luka: 1 regular + 3 preseason); (2) its 5-game floor sent every early-
  season player back to the 2024-25 table; (3) it read only the first 12
  names per roster, and roster order is NOT depth (Makar, Sabonis, Fox
  missing); (4) teams always came from the table -- 25 of 62 NBA stars and 6
  NHL had moved (Giannis MIA, Durant HOU, Davis WAS), priced into the wrong
  game; retired players (Chris Paul, Fleury, Suter) were still projected.
  FIX: espn_player_stats is now BULK (statistics/byathlete, regular season
  only: ~20 calls/league, 27s vs 4 min, NBA 330 -> 472 players, NHL 377 ->
  821), blending this season toward last season by games played,
  w = n/(n+K). **K MEASURED on 2025-26 (prior 2024-25, predict next 10 games
  from first n): NBA K=5 (after 1 game RMSE 6.45 current-only -> 3.57
  blended); NHL K=30 (skaters want heavy prior; goals favour prior alone).**
  real_stats_lookup serves `blended` records without the 5-game floor, matches
  names punctuation/suffix-tolerantly, and `apply_live_teams()` (one line
  after each NBA/NHL table) sets the CURRENT team in the generators' vocab
  (GSW/NYK/NOP/SAS/UTA/WAS; LAK/NJD/SJS/TBL/UTA) and blanks the team of anyone
  on no current roster. WNBA team overlay NOT applied (its tables disagree on
  codes: CON/CONN, LV/LVA) -- DONE 10/23 via apply_live_teams(to_code=<the
  module's own _abbr/_norm_team>), so each table keeps its own vocabulary.

- **2026-10-23 (newest) — NFL PROPS JUDGED FROM 10/23 FORWARD (Brandon's call):**
  the form-rule change makes earlier NFL props a different model. Every NFL
  model prop carries `model_rule` ("form_v1"/"form_v2"), stamped at intake from
  nfl_player_props.json's `form_rule`; older rows fall back to recorded_at vs
  prob_calibration.NFL_FORM_V2_FROM (commit 8c762aac8c's deploy). ERA = WHEN
  PRICED, not game date (Week 8 props priced 10/22 stay v1; the v2 line fills
  from Week 9). `prob_calibration.judged(p)` is False for v1 rows and gates ALL
  family verdicts: ledger by_market_family/by_canonical (what curation reads),
  overconfident_families, sport_curation_report, recalibration's isotonic fit.
  Consequence: the 4 NFL families v1 had condemned (longest_rush_over,
  pass_yds_under, rec_yds_over, rush_yds_under) are UN-excluded until v2
  evidence accrues -- intended. ledger_summary/recent_picks carry
  `nfl_props_by_model` (two lines, never summed); track-record shows them under
  NFL, nfl.html above Model Props. by_sport NFL stays the all-picks total.
  **RULE: when a model changes, split the record by the rule that PRICED each
  pick, and let no verdict mix eras.**

- **2026-10-23 (latest) — NFL DFS OVER-PROJECTION = THE OPTIMIZER'S CURSE, fixed:**
  published lineups ran ~-60 pts/slate vs projection. A FULL-POOL backtest
  (every projected player, Weeks 1-3 mains, rebuilt from git history: last
  pre-slate nfl_dfs.json x union of committed box logs; n=828, 634 played)
  showed **the model is UNBIASED across the pool (+0.2/player)**. The gap is
  selection: the optimizer seats the players whose projection most exceeds
  salary, i.e. the over-estimates (3.0+ pts/$1k realized 0.82x; <1.5 realized
  1.58x). Plus injuries: D (doubtful) was never excluded (5/5 sat), Q sat
  25-53%. FIX = `nfl_dfs_calibration.py`: lineups maximize
  **xfp = p_play x (implied + w x (proj - implied))**, implied =
  ppk[pos] x salary/1k; w=0.32 (only a third of the model's disagreement with
  DK salary holds up), p_play by tag x projection band. Leave-one-week-out:
  lineup bias -64.6 -> -7.3, actual skill pts 106.0 -> 111.7 (n=3 weeks --
  directional). Calibrated realization 0.95-1.06 in EVERY value band.
  SELF-REFITTING: receipts snapshot the whole pool per slate into
  data/nfl_dfs_pool_history.json (seeded with the reconstruction), score every
  player after the slate, and the calibration step (before nfl_dfs) refits
  once >=300 played rows. `proj` stays the raw model mean; lineup slots carry
  proj = xfp + model_proj. Receipts: DST read only nfl_state (current week ->
  always "unscored" while its proj counted: ~6 pts phantom bias) -> now
  nfl_historical first; bias is like-for-like (`proj_scored`); records are
  split by `proj_basis` (model_raw pre-10/23 at -52.5 like-for-like, vs
  calibrated_v1) and NEVER averaged together. **RULE: never grade an
  optimizer on its own objective -- calibrate what it maximizes, and judge a
  projection model on the whole pool, not the lineup.**
  **SECOND ROOT CAUSE, same day -- "recent form" was ONE GAME:**
  nfl_player_props._blend put a flat 65% on the mean of nfl_player_gamelogs,
  an ~8-day box window = one NFL game, and took volume (att/carries/targets)
  from it outright; projections swung 10+ pts between runs an hour apart
  (Golden 15.8 -> 27.1). FORM RULE v2: season-to-date regular-season mean,
  weight n/(n+2), yardage AND volume; espn_box_logs CFG_NFL `retain_days`
  160 merges each fetch into the file (seeded from the git-history union);
  preseason rows are filtered from both the form rule and the gamelog-only
  baseline (a $3k WR was projected 14.6 off August snaps); box keys matched
  normalized. Walk-forward Weeks 2-6, same 986 player-games: MAE 6.12 -> 5.76,
  corr 0.483 -> 0.545, top-20% bias -3.14 -> -0.78 (K grid 2/4/8/16 all beat
  v1). Pools recomputed walk-forward under v2 -> calibration w 0.32 -> 0.54
  (fits only on pools with the CURRENT projection_rule). LOWO lineups: shipped
  106.0 @ -64.6 bias -> v2+calibrated 130.8 @ +10.9 (n=3 weeks, directional).
  **This also changes the NFL BETTING props** (same simulator): priced off
  season form, not last week -- judge the nfl_* families from 10/23 forward.

- **2026-10-23 — FOLLOW-THROUGH (same session, all pushed + CI-verified):**
  (1) **A clean run's data was LOST at the commit step**: alpha_email.py
  rewrites the TRACKED emails/latest.html, the commit staged only data/, and
  when main moved mid-run `git rebase` refused on the dirty tree (exit 128).
  Every committing workflow now rebases `--autostash`; daily-pipeline stages
  emails/ (the page's email preview had been stuck on 9/08).
  (2) **NFL names**: the props desk keys "jaxon smithnjigba"/"amonra st
  brown"; ESPN keeps hyphens -> 0 props on either had EVER graded. Fixed in
  _grade_nfl_pick's normalizer. **NFL DFS receipts zeroed every punctuated or
  suffixed player** (raw box keys looked up by nb.norm_name): Achane, Chase,
  Smith-Njigba, St. Brown, James Cook III scored "DNP -> 0". Fixed + ONE
  disclosed correction (scorer_version 2): touched slates rescored where box
  rows survive (`rescored.previous` keeps old totals), RETRACTED where they
  aged out (9/09, 9/13, 9/14); retraction only fires with a 30+ day box window
  loaded. Honest result: bias barely moved (-60 -> -59/slate on 0-1 DNPs) --
  the projection over-shoot is REAL, don't blame the scorer again.
  (3) **MLB run lines** (HOME/AWAY_MINUS_1.5) had no grading branch -- 0 ever
  settled; now graded off the final margin. (4) **todays_top_plays excludes
  never-settling markets** (>=20 unsettleable voids, 0 graded; KBO
  one_plus_tb was featured 48x, graded 0); data-driven, self-clearing.
  (5) **NBA/WNBA picks dated by their game** (shared `_board_dates`; a WNBA
  Finals pick made 10/22 for the 10/24 game was dated 10/22); NBA/WNBA never
  drop, NHL drops off-board picks. (6) **Ticker perf**: js/main.js (14 pages)
  fetched the 11.5MB ledger per page load for 5 rows -> recent_picks.json
  (~208KB; also refreshed on the heartbeat). (7) **MAX_PICKS 14000 -> 20000**
  (bound again with 957 voids of headroom as NFL/NBA/NHL restarted).
  outage_backfill is VERSIONED (now v4; `previous_passes` keeps each pass) --
  bump BACKFILL_VERSION when a grader fix needs the long window once more.

- **2026-10-22 (newest) — OUTAGE BACKFILL + GRADER FIXES + PHANTOM PICKS:**
  (1) **779 real picks were voided by the cascade** ("unsettleable: no outcome
  feed" -- feeds dark, not games missing). `outage_backfill.py` (one-shot,
  wired just before the ledger step; marker data/outage_backfill_2026_10.json,
  `--force` to re-run) re-runs every outcome feed once with a lookback to the
  oldest void (36d), adds the voided MLB players to the gamelog universe, then
  runs the normal ledger build. Nothing is graded by the backfill itself.
  Rehearsal on prod: 235 recovered (NFL 129-60, NHL 22-11, F1 4-3, UFC 2-2,
  tennis 1-1). Still void = true non-plays/feeds with no history (KBO box,
  MLB favourite run lines, DNP props).
  (2) **NFL record moved DOWN on purpose:** props stamped the UTC date, so
  every prime-time (SNF/MNF/TNF) prop's box row sat on the next day and never
  matched -> ET slate date (nfl_player_props), name suffix normalization,
  nearest box row within +/-1 day, zero-stat lines = 0 when the player IS in
  the box. NFL 791 settled -2.4% -> 980 settled 700-280 -3.2%. Don't restore.
  (3) **NHL grader:** MINUS_1.5 puck lines were graded as +1.5 (always too
  generous); P-period totals + ANYTIME_GOAL_NO never graded; espn_box_logs
  read period scores from `value` (ESPN uses displayValue -> all None).
  **RULE: a grader matching "a row within N days" must take the NEAREST row
  and refuse an equal-distance tie -- never the first in list order** (a 10/15
  hits prop was graded on 10/17's game). Applied to skater props AND
  `_find_nhl_game`. 4 settled picks re-graded (all won->lost), each with a
  `regraded` audit dict {from_result, from_payout, at, reason}.
  (4) **NHL PRESEASON leaked into the record** (no generator gate):
  `_void_preseason_nhl` voids NHL picks dated 9/01-9/28 (opener 9/29,
  `_NHL_2026_OPENER` -- bump it each season) regardless of result: 71 had
  settled at -24.4u. Same rule as the NFL; reason 'preseason' is intentional.
  (5) **PHANTOM PICKS on fake games.** pipeline.py fell back to DEMO_SLATE
  (SDP@LAD, BOS@NYY, CIN@COL) whenever the MLB schedule was EMPTY, and
  run_pipeline dropped the is_demo tag -- so on every off-day today.json
  published demo games as real and mlb_run_line_props / mlb_unders_alerts
  wrote picks on them (a batch every 5 days: the add-guard blocks while
  pending, the 4-day void frees it). An empty real schedule now writes
  `games: []` + `no_games: true` (all 77 wired today.json consumers verified
  clean on it); demo slates carry `is_demo` and the ledger intake drops MLB
  picks on a demo matchup. NHL had the same disease from FROZEN generator
  artifacts during the cascade -> `_nhl_intake` stamps each NHL pick with its
  game's ET date from nhl_state (abbrev-tolerant: NJD/NJ, TBL/TB) and drops
  picks not on today's board. Alpha's off-season check ignores voided rows.
  **RULE: a fallback/demo/stale input must be tagged AND the tag must survive
  to every artifact -- check intake, not 80 generators.**
  (6) live-games.yml (40 bare steps, every 20 min) converted to the same
  record-and-continue + Failure gate pattern -- it had the cascade's exact
  weakness (one crash skipped the ledger AND the commit).

- **2026-10-22 (latest) — WHY BOTH OUTAGES WERE SILENT: the alert was muted
  since July.** The freshness canary DID trip red during the 30-day cascade
  ("sport_coverage.json: 316h old") -- but health-alert.yml dedupes against an
  OPEN issue, and **issue #45 had been open since 2026-07-01**, so every trip
  logged "Alert already open: #45" and sent NOTHING (also through the 6-day
  September outage). FIX: health-alert now CLOSES the alert issue on recovery
  (with a "recovered" comment) so an open alert always means "dark right now",
  and while still dark it RE-NOTIFIES with a comment at most once per 22h.
  **RULE: an alert channel whose dedupe key can stick open is a mute button --
  every dedupe needs an auto-clear.** Also: NFL DFS receipts gained the MLB
  desk's terminal `unscoreable` state (box rows age out of espn_box_logs' ~8-day
  window; 4 slates frozen during the cascade can never be graded -- disclosed,
  never guessed) plus a stale-snapshot freeze sweep (the freeze only touched the
  CURRENT slate, so past-dated snapshots stayed open forever). Confirmed the
  9/08 MLB 'IL' fix: receipt bias -59.8 -> -14.1, dead slots 4.4 -> 0.9/slate.
  Open watch: NFL DFS optimal runs -61 pts/slate on n=3 (2 clean slates) --
  part winner's-curse from optimizing on projections, too small to tune yet.

- **2026-10-22 (later) — ALPHA OFF-SEASON STATE + the broken no-pick tweet:**
  (1) **The Alpha pool stays MLB-only, measured not assumed.** Replaying the
  v2 gate over every other sport's settled ledger picks produced ZERO
  qualifying days outside NFL's two (MLB: 93 days, 52-38, +23.8%, upper bound
  -- today's calibration map). Structural reason: non-MLB picks are recorded at
  the model's OWN fair odds, 0-EV by construction, so none clear +2%
  calibrated EV at recorded odds. Widening the pool = loosening the rule to
  manufacture output -- don't. Instead alpha_pick_record publishes
  `season_state` ("offseason" when no MLB ledger day in 5+ days AND month in
  Oct-Feb; Opening Day ends it automatically). Off-season: page shows a
  season-closed callout with the v2 record; alpha_tweet writes tweet=None (no
  daily post); alpha_email composes a season card and --send-self no-ops.
  Verified by simulating 2026-11-15 end to end.
  (2) **Every NO-PICK day's tweet draft was garbage** ("? -- " as the play):
  `elif one:` treated the no-pick MARKER as a pick, making the honest no-pick
  branch unreachable. Now `elif one and not one.get("no_pick")`; the real 10/20
  draft verified. (3) Proof run 39860872402 after the cascade fix: SUCCESS,
  324/325 steps ran, 0 failed, failure gate "all modules ran clean".

- **2026-10-22 — THE 30-DAY CASCADE (read before touching any workflow):**
  daily-pipeline failed EVERY run 9/22-10/22 and **234 of 324 steps were
  SKIPPED** each time, while the commit step (`if: always()`) still pushed
  data and the 2-hourly heartbeat kept the ledger settling -- so the site
  LOOKED alive. Frozen for a month: alpha_pick_record/tweet/email, NFL props +
  DFS + receipts, CFB ratings (edges re-priced daily against WEEK-4 ratings),
  top_calibrated_edges, sport_coverage. TRIGGER: the Presidents Cup (a TEAM
  event) became golf's "active tournament"; ESPN lists team competitors with no
  athlete names; golf_winner_model then golf_region_props crashed on a DISPLAY
  print (`f"{x.get('name','?'):20s}"` -- .get's default does NOT apply when the
  key exists with None). DEADLOCK: golf_region_props runs BEFORE golf_pipeline,
  so the crash prevented the refresh that would have replaced the bad state.
  FIXES: (1) golf_pipeline only selects events with >=10 NAMED competitors and
  drops nameless rows; (2) all 14 `.get(k, dflt):FMT` sites rewritten to
  `(.get(k) or dflt):FMT` (repo-wide count now 0); (3) **STRUCTURAL: every
  python step in daily-pipeline (210) and the heartbeat now RECORDS failure to
  $RUNNER_TEMP/failed_steps.txt and CONTINUES; a final `Failure gate` step
  (if: always()) turns the run red and names the failed modules.** A broken
  module is now visible the same day and can no longer darken the other 233.
  **RULE: never add a bare `run: python X.py` -- append the
  `|| echo "X.py" >> "$RUNNER_TEMP/failed_steps.txt"` suffix.**
  ALSO FOUND: nfl_stub.py (an old scaffold, step ~1101) OVERWROTE the real
  nfl_state.json written by nfl_pipeline.py (~959) with "off-season / 0 games"
  on EVERY run all season. nfl_player_props only worked because it runs between
  them; the NFL page, sport_coverage, the heartbeat and NFL DFS receipts' DST
  scoring all read the stub. nfl_stub now refuses to clobber a real state.
  State after recovery (local run 10/22): golf on the live Bermuda Championship
  (120 named players), CFB ratings on 514 2026 games, NFL Week 7 (14 games,
  583 props), Alpha v2 18-16 +11.51u (+33.9%) over 34 days, curated 769-370
  +14.2% on 1,149 settled; NFL props 791 settled ~break-even with
  longest_reception (-9.05u) and rush_yds (-7.61u) crossing the curation bar.

- **2026-09-08 (later) — MOBILE/PWA PASS + NFL-DFS MULTI-DAY SLATE FIX:**
  (1) **PWA**: manifest.json + assets/icons (from the brand mark; the site had
  NO favicon before) linked from every page's <head>; sw.js caches the app
  SHELL only, network-first, and NEVER data/*.json -- an installed app must not
  show a stale pick. Install-to-home-screen works on iOS/Android; that is the
  "mobile version" path (no store, no native build).
  (2) **Dense rows on phones**: style.css's blanket
  `[style*="grid-template-columns"] {1fr !important}` (the ≤720px collapse for
  layout grids) was also flattening every data row to ONE column -- a 5-cell
  rating row was 169px tall. Row classes (.sb-row/.dfs-row/.mk-row/.lu-slot/
  .pl-head/.op-row) are now excluded, keep their inline template, get a
  min-width, and scroll sideways inside the card; nav.js tags cards that
  actually overflow with .is-scrollable ("swipe →" hint). **RULE: any new
  inline-grid data row needs a class from that list or it will stack on
  phones.** (3) **Homepage accordion** on ≤720px only (first 4 cards open,
  rest toggle from their header; 21,000px -> 11,990px). nav.js width detection
  falls back to clientWidth and bails on 0 -- a hidden tab reads innerWidth 0,
  which looked like "phone" and collapsed a desktop page during testing.
  (4) **Preview server**: .claude/serve.py honors PORT (autoPort) after a port
  collision with the other session's dev server. (5) **NFL DFS receipts**: DK
  dates the weekly Main slate by its FIRST kickoff -- Week 1's 16-game group is
  stamped 09-09 (Thu) though 13 games play Sun 09-13 + 1 Mon. The scorer fired
  at age>=1 with a 3-day window -> would have graded Week 1 on Friday with
  every Sun/Mon starter as DNP->0 and frozen it as scored. Now SLATE_SPAN_DAYS=6
  for players + DST and scoring waits for the full span. NB the 09-13 receipt
  entry is a DIFFERENT draft group (151307 vs 153054), not a duplicate --
  the 085506c5f7 commit message is wrong on that point; nothing was dropped.
  (7) **BOTTOM TAB BAR + SPORTS SHEET** (nav.js, ≤720px only): Home / Picks /
  Alpha / Record / Sports, 60px targets, safe-area aware; "Sports" opens a
  bottom sheet CLONED from the live Sports dropdown so nav_badge's live dots
  ride along. body.has-tabbar pads the bottom. Desktop untouched.
  (8) **DAILY ALPHA EMAIL** (python/alpha_email.py, runs after alpha_tweet):
  composes subject + plain text + email-safe HTML from the same record ->
  data/alpha_email.json + emails/alpha-daily-<date>.html + emails/latest.html;
  alpha-pick.html gets a "Daily email" card (Open in mail = prefilled mailto,
  Preview HTML, Copy text). **NOTHING SENDS TO ANYONE from code.** The only
  send path is `--send-self` to ONE owner address, and only when the repo
  secrets ALPHA_EMAIL_TO / SMTP_USER / SMTP_PASS exist (Gmail app password);
  the step is wired in daily-pipeline and no-ops without them. Subscriber
  sending stays Brandon's manual action (durable rule).
  (6) **CACHE-BUMP RULE (bit us the same day):** css/style.css and js/nav.js are
  referenced from 120 pages; prod served the new HTML with the OLD cached
  css/js -- rows still stacked, accordion inert, service worker never
  registered. Any change to style.css or nav.js MUST bump `?v=` on every page
  (current: ?v=20260908b) and the SW SHELL list in sw.js must carry the same
  bumped URLs. Verified on prod after the bump: 5-col rows, 20 cards
  collapsed, SW registered.

- **2026-09-08 — NFL WEEK 1 OPENED + THE 'IL' HOLE + LOSSLESS EVICTION:**
  (1) **The NFL gate flipped correctly on schedule.** ESPN still reports
  season_status "off-season" (Week 1 kicks 9/10-9/15), but the DATE-HARDENED
  gate opened as designed -- nfl_player_props self-reports "regular" and 675
  strong_edges entered the ledger. This is intended behaviour, not the
  preseason failure: starters now play full games, so season-baseline
  projections are valid. Conviction is NOT saturating (only 9 of 676 sit at the
  0.80 cap; median prob 0.748, median fair -296). WATCH: these are priced at
  the model's OWN fair odds, so each is ~0-EV by construction -- they profit
  only if the model is under-confident, and they will settle into the curated
  book over the next week. Expect the headline curated ROI to move on NFL.
  (2) **THE 'IL' HOLE (biggest DFS bug to date).** mlb_dfs's lineup pool
  excluded ("O","OUT","IR") -- a list borrowed from football. **Baseball uses
  "IL"**, which was never in it, so DK was flagging injured players and the
  optimizer seated them anyway: 40 IL players on the 9/08 slate, 34 seatable,
  and receipts had carried 3-6 dead slots per lineup for weeks (avg bias -64,
  -46 after the 9/03 staleness patch). The STALE>7d heuristic added 9/03 caught
  ZERO players DK had not already flagged -- **the vendor's status field was
  the signal all along**; it stays only as a backstop for unstatused players.
  DTD is deliberately NOT excluded (those players usually play). Judge the fix
  on slates dated 9/09+; earlier slates keep their original scoring.
  **RULE: never port a status-code list between sports -- enumerate the
  vendor's actual values per sport (MLB: IL/DTD; NFL: O/Q/OUT/IR).**
  (3) **Eviction is now LOSSLESS.** The tail-cut destroyed SETTLED rows when
  the window overflowed. At ~200 picks/day (727 on 9/08 as NFL opened) the
  14000 cap binds in ~2 weeks, so evicted settled picks now append to
  data/ledger_archive.json (compact, idempotent) and ledger_summary reports
  `archived_history` separately. DECIDED 2026-10-23: all-time (archive merged) -- see the 10-23 entry. Merging the archive in
  would make it all-time again but restates published numbers upward -- his
  call, not an automatic change.
  (4) CFB desk graded its first pick end-to-end: 9/05 UNLV @ HAW settled off
  the ESPN event id (a LOSS -- we had HAW home, UNLV won 21-6). 3 picks pending
  for 9/12. Ratings now carry 99 real 2026 games.

- **2026-09-03 — THE LEDGER WAS EATING ITS OWN TRACK RECORD (read before adding
  any new pick source):** all_picks_ledger hit MAX_PICKS=10000 with **zero
  eviction headroom** -- 9840 settled, 160 pending, 0 voided, 0 stale pendings.
  The eviction ladder is correct (voided rows -> dead pendings -> tail-cut last)
  but with nothing signal-free left to spend, **every pick added was tail-cutting
  the oldest SETTLED result**: the public record was shrinking daily by however
  many picks the desks produced. Same erosion as 2026-07-06 (settled 6526 ->
  6357), returning by a different route once the voided rows ran out. Raised
  MAX_PICKS 10000 -> **14000** (no restatement -- past evictions are already
  gone from the artifact, recoverable from git; this stops it forward).
  **RULE: before wiring a new pick source, check eviction headroom
  (voided + stale pendings). At zero headroom a new desk buys its rows with
  real settled history.**

- **2026-09-03 — COLLEGE SCOREBOARD TRUNCATION (espn_odds, 25 of 99 games):**
  the BARE ESPN scoreboard returns a CURATED SUBSET for college sports -- 25
  NCAAF events on a day with 99. `limit` alone does nothing; **`groups=80`
  (FBS) is the unlock** (`groups=50` for NCAAB D-I). Added `SPORT_QUERY` in
  espn_odds (per-sport params; pro leagues take none and are untouched). This
  is the SAME trap as the week-form scoreboard in cfb_results_cache -- assume
  any college ESPN endpoint truncates until proven otherwise. Effect: NCAAF
  25 -> 99 games, ratable 19 -> 51, first qualifying CFB edge surfaced.

- **2026-09-03 — THE EMPTY-MATCHUP MIS-GRADE (locks_of_day, live bug, predates
  CFB):** `_settle_game_market` built its game key as
  `g.get("matchup") or g.get("name") or ""` -- but NO `historical_<sport>.json`
  file carries either key (historical_games.py writes home_abbrev/away_abbrev).
  So g_mu was ALWAYS empty, and the guard `matchup not in g_mu and g_mu not in
  matchup` is trivially False for an empty string (`"" in anything` is True),
  so the `continue` never fired and **every game-line lock settled against the
  FIRST game on its date.** Demonstrated on real data: a MEM @ UNLV pick whose
  home side LOST graded 'won' off SJSU @ USC. Affected NFL/WNBA/MLS/EPL/NCAAB/
  NCAAF (MLB failed safe -- its mapping points at a filename that doesn't
  exist). Fixed: key built from abbrevs, and FAIL CLOSED (return None) when the
  key or the pick's matchup is empty. **RULE: a settlement matcher must never
  treat an empty key as a match -- assert the key is non-empty before
  comparing.** Found by an adversarial review panel, not by a test; the same
  panel also corrected the CFB graduation bar's implied claim (100 settled
  picks cannot distinguish a +3% edge from zero -- the bars are a FLOOR that
  opens a CLV-based human review, and the desk now says so).

- **2026-09-03 — COLLEGE FOOTBALL DESK (new sport, built end-to-end):**
  CFB had lines + scores but no model, no picks, and NO SETTLEMENT BRANCH (an
  NCAAF pick would have fallen through to the MLB default and tried to grade
  against baseball finals). Three new modules:
  `cfb_results_cache.py` (every FBS game of a season from ESPN) ->
  `cfb_ratings.py` (Elo + MoV damping) -> `cfb_model.py` (model-vs-book edges).
  **TWO ESPN TRAPS, both verified:** (1) the college-football scoreboard's WEEK
  form REQUIRES `groups=80` -- without it a week returns 16 events instead of
  53 (the DATE form is unaffected, which is why historical_games.py was fine);
  always pass `limit=400`, CFB Saturdays run 60+ games. (2) the site API's
  `/teams?groups=80` SILENTLY IGNORES the filter and returns all 760 teams
  across every division -- it flagged all 934 of 2025's games as FBS-vs-FBS.
  The real FBS list (146) comes from the CORE api
  (`sports.core.api.../seasons/<yr>/types/2/groups/80/teams`), ids parsed from
  the $ref urls so it stays one call.
  **EVERY CONSTANT IS MEASURED** (`python cfb_ratings.py --tune` reproduces):
  K=55, HFA=60 from a 2025 walk-forward grid; CARRYOVER=0.45 tuned by
  predicting the START of 2025 from 2024 (n=195) -- ~55% regression to the
  mean, CFB rosters churn far harder than the NFL's. FCS opponents pool into
  ONE rating at 35% weight (2025: FCS games averaged a 34.0-pt margin vs 16.4
  FBS-vs-FBS, so MoV-naive Elo would mint rating off cupcakes).
  **THE HONEST NUMBERS (do not restate upward):** 70.3% acc / 0.1907 Brier
  walk-forward mid-season (n=617), but only 64.6% / 0.2063 off prior-season
  ratings (n=195) -- the September regime. Bucket calibration is clean (gaps
  +0.001..+0.060, no systematic bias). A sharp close is ~0.19 Brier, so THIS
  MODEL DOES NOT BEAT THE MARKET ALONE; that is why cfb_model shrinks toward
  the book at cap 0.90 (harder than the MLB desk's 0.80 -- that model has
  thousands of settled games, this one has zero) and requires a 4% edge in a
  35-80% band. Typical output is 0-4 edges/slate; ZERO IS A NORMAL, HONEST
  RESULT and the page explains it rather than manufacturing a play.
  **EXPERIMENTAL, and it is enforced:** picks enter the ledger as `cfb_model_*`
  (tracked-not-featured, the worldcup precedent), and `graduation_status()`
  computes the promotion bars against the real ledger every run (100 settled
  picks at non-negative ROI) and publishes them on the desk. Promotion is a
  deliberate human step; nothing self-promotes.
  **SETTLEMENT:** `_grade_cfb_pick` settles by ESPN EVENT ID (espn_odds now
  carries `event_id` + `neutral` for ALL sports -- that is what makes it
  possible), immune to the UTC date shear and matchup ambiguity that have bitten
  this repo twice. The date path is a fallback accepting +/-1 day ONLY when
  exactly one game matches (safe: college teams play weekly) and refuses to
  guess otherwise. The ledger collector DROPS any edge lacking event_id or
  game_date -- the RLM lesson enforced at intake. NB the collector must emit
  `game_date` (not `date`): the finalizer pops that key, and a pick setting
  `date` directly gets it overwritten with the snapshot day.
  Wired into daily-pipeline BEFORE all_picks_tracker (so edges land the same
  run) and re-priced on the heartbeat; both cfb artifacts registered in
  data_health DESK_FRESHNESS. v1 is MONEYLINES ONLY -- no spreads, totals, or
  player props, and no CFB DFS. Method documented at methodology.html#cfb-model.
  **MEASURED vs THE MARKET (do not replace with an assertion):** the desk used
  to claim "a sharp close is ~0.19 Brier" to justify its shrinkage -- that was
  asserted, never measured. `cfb_ratings.py --vs-market` now scores our
  walk-forward probs against ESPN's CLOSING moneylines on the SAME games and
  caches data/cfb_market_benchmark.json. Result (n=343, 2025 FBS, weeks 4+):
  **market 0.1866 Brier / 74.1% acc vs model 0.2026 / 69.1%, same side 81%** --
  the closing line is SHARPER than this model, and the desk says so in those
  words. NB ESPN nests closing prices inconsistently (close.american on some
  records, close.moneyLine.american on others); an extractor that handles only
  one silently returns zero lines for every game. cfb_model also FAILS CLOSED
  if prob_calibration can't import (publishing ungated picks is worse than
  going dark).

- **2026-09-02 — THE 6-DAY PIPELINE OUTAGE (read before touching
  verify_calibration):** daily-pipeline failed EVERY run 8/28-9/02 because
  verify_calibration pinned specific families (to_score_run_no empirical,
  mlb_tb_1.5_over overconfident) whose ledger stats DRIFTED out from under the
  checks -- guards must probe families chosen from the LIVE sets, never
  hardcode a family name as an expectation. Everything downstream was dark 6
  days (finals, settlement, alpha locks) while the heartbeat kept the site
  looking alive. Four settlement bugs found clearing the backlog: (1) finals
  stamped event-UTC dates (west-coast night games slid +1 day; ARI@SF 8/27 sat
  unmatched at 8/28) -- historical_games now stamps the queried board day;
  (2) 'HOME ML'/'AWAY ML' space vocab never graded (0 settled ever) -- now
  normalized in settle/recompute/regrade/_wager_key; (3) rlm_strong was
  UNSOUND: live_clv keys by matchup so open/close spanned DIFFERENT games of a
  series off a stale May cache -- producer now same-day+fresh only, collector
  requires game_date, 67 conflated picks voided ('rlm' void reason is
  intentional, never resurrect); (4) {TEAM}_ML grading used exact abbrev ==
  (SFG/SF etc. never matched) -- now prefix-tolerant. MLB DFS receipts
  corrected: gamelog universe includes DFS lineup players (2nd
  settlement-universe hole), slots score 0 only when the player's ID-KEYED log
  covers the date, lineup slots carry mlb_id (name matching graded the wrong
  Max Muncy), 11 coverage-gap slates retracted + rescored. HONEST FINDING (do
  not 'fix'): the -66 avg receipt bias is REAL -- DK left long-injured
  Athletics unstatused (Rooker out since 6/08) and v1 seated 3-6 ghosts/slate;
  the pool now benches players whose latest box-log game is >7d old
  (STALE>7d). Alpha day 8/27 dropped out of v2 per the aged-out-lock rule (the
  real SFG ML +101 WON but its ledger row was cap-pruned; do not restate).

- **2026-08-18 (late) — PROVENANCE LAYER + attribution audit:** every headline
  number now shows its why/how/source. (1) Alpha v2 gate emits a `why` chain
  (raw prob -> family n/realized/shift -> implied prob -> edge vs the +2% bar);
  alpha-pick.html renders it on today's pick; methodology.html#alpha-v2
  documents the 4-step rule with the lock file linked. AUDIT CATCH: the
  '{TEAM}_ML' vocab never reached prob_calibration's family map, so those picks
  were gated on the RAW prob with zero family evidence -- _market_for_cal() in
  alpha_pick_record canonicalizes to ML_AWAY/ML_HOME before every calibration
  call (history + record_v2 verified byte-identical; forward days now carry
  real family evidence). (2) DFS provenance: mlb_dfs rows carry sample+mlb.com
  link; nfl_dfs + nfl_player_projections rows carry gp_2025/espn_id + espn.com
  link; all three pages render them. (3) STALE-ATTRIBUTION SWEEP: 'Bovada'
  claims corrected on book-edges/top-edges/index/game (lines are DK via ESPN's
  free feed since 2026-06); book_vs_model_team stamps line_source
  (espn_dk|matchups_snapshot) on every edge row. props.html banner corrected
  (was: '401'; truth: valid key, quota spent, resumes ~Sept 1) and pickem.html
  explains the PP bot-wall dark state instead of an empty grid.
  data-sources.html rebuilt: every feed w/ URL + cadence + the honest-UA
  policy + direct links to the public JSON artifacts.

- **2026-08-18 — MLB DFS DAILY RECEIPTS:** mlb_dfs_receipts.py ->
  data/mlb_dfs_receipts.json -> the "Daily Lineup Receipts" card on
  mlb-dfs.html. MLB slates run daily, so this grades the published optimal
  EVERY MORNING (snapshot all slate day, freeze at day's end = the last
  pre-lock pipeline refresh, score next morning from statsapi box scores
  with the exact DK MLB formula; no-box-row scores 0 flagged; scored slates
  never edited; cumulative proj-vs-actual bias accrues). player_gamelogs
  now also stores sb/hbp (batters) and win (pitchers) -- DK components the
  feed lacked; rows logged before 8/18 score those as 0 (disclosed). Wired
  after mlb_dfs in daily-pipeline.


- **2026-08-17 (late) — MLB DFS DESK + NFL gate date-hardening + all-desk
  audit:** (1) mlb_dfs.py -> data/mlb_dfs.json -> mlb-dfs.html: DK MLB
  Classic (ContestTypeId 28 -- NOT 21; per-sport ids differ) salaries from
  the free lobby; v1 MEAN projections labeled as such (hitters = season
  per-game rates via props_pipeline._batter_season, pitchers = season
  per-start rates via stats_repo, PROBABLE STARTERS ONLY from
  matchups.json -- never the 380-arm bullpen pool); exact 0/1 DP optimizer
  with FULL DUAL-ELIGIBILITY (a '2B/SS' may be seated at either slot; DP
  tries each eligible position per transition; brute-force-verified
  self-test runs every invocation). Roster P,P,C,1B,2B,3B,SS,OFx3 @ $50k.
  v2 path = the NFL desk's Monte Carlo treatment (distributions,
  park/platoon/lineup-order). Free-data only, no paid-quota cost. Wired in
  daily-pipeline (unconditional step), directory, mlb.html + nfl-dfs.html
  cross-links. (2) NFL preseason gate DATE-HARDENED: between preseason
  weeks ESPN's label flips to "off-season", so the picks gate now holds
  until NFL_2026_WEEK1 regardless of the label. (3) All-desk audit: health
  green, 0/17 coverage flags; 8 sports live (MLB/WNBA/KBO/CS2/Tennis/Golf/
  UFC/F1), the rest correctly dormant with next-dates.


- **2026-08-18 — DFS RECEIPTS LOOP + NCAAF LINES + BOTH SOCIALS LIVE:**
  (1) nfl_dfs_receipts.py -> data/nfl_dfs_receipts.json -> the "Lineup
  Receipts" card on nfl-dfs.html: published lineups SNAPSHOT all week and
  FREEZE at the slate date (last playable version wins, same immutability
  philosophy as the alpha locks), then score the day after from real box
  scores via actual_dk_points() (self-tested vs hand examples; DNP scores 0,
  disclosed per-slot; DST partial PA-tier-only, labeled). Cumulative
  proj-vs-actual bias per build. Scored slates never edited. Week 1
  (2026-09-13) already armed. (2) ncaaf.html gained the Live Book Lines card
  (espn_odds NCAAF rows -- ~99 games priced; Week 0 kicks 8/22).
  (3) SOCIALS: X @edgestatbets + Bluesky @edgestat.bsky.social both
  BROADCASTING (see X-LAUNCH-KIT header) -- machine writes, Brandon presses
  every Post, forever.


- **2026-08-17 — WEEKEND AUDIT: settle-vocab bridge, {TEAM}_ML wagers, quota
  torch, lock resilience.** Four connected fixes: (1) MLB game-line settling
  could NEVER match Washington/Arizona/Athletics (substring match tolerates
  prefixes like KC-in-KCR but not rewrites WSH/WSN, AZ/ARI, ATH/OAK) -- those
  teams' picks silently aged into 'unsettleable' voids, wins and losses alike;
  an abbrev bridge in the matcher settled 45 stuck picks incl. the 8/14 WSN
  Alpha loss (graded honestly into v2's 3-4). (2) '{TEAM}_ML' (e.g. STL_ML)
  is now graded AND canonicalized to ml_home/ml_away in _wager_key, so twin
  vocab copies collapse instead of double-counting when both grade.
  (3) THE QUOTA TORCH: multi_book_lines burned 3 paid Odds-API credits per
  2-hour heartbeat (~36/day) on 8-book GAME lines the free ESPN feed already
  covers -- August's reset quota fell to 4 credits in days. Now once-per-day
  (sticky had_odds_api flag) + a global ODDS_DAILY_CAP=14 env in both
  workflows (props 8 + multi-book 3 + pipeline enrich 3); paid props are dark
  until Sept 1 (4 credits < RESERVE) and September's 500 survives.
  (4) v2 lock resolution is dup-collapse-proof: dup-voided copies stay in the
  ungated index, live copies win two-tier resolution, _lock_key canonicalizes
  {TEAM}_ML, and _is_mlb_moneyline accepts ML_*/{TEAM}_ML/'HOME ML' vocabs --
  a published pick day can no longer flip to NO PICK because its locked copy
  got collapsed. Humanizers (tweet + page) render {TEAM}_ML as 'STL moneyline'.


- **2026-08-14 — CASE-INSENSITIVE WAGER KEY (the third duplicate leak):**
  sharp_strong emits lowercase markets ('ml_away') while the boards emit
  'ML_AWAY' -- the case-sensitive _wager_key gave the same moneyline two
  identities, so the ADD-GUARD waved the second copy through and BOTH counted
  (3 double-counted losses in 8/10-8/13 alone). _wager_key now lowercases all
  components, and _collapse_duplicate_wagers gained a SAME-DAY pass (same
  wager + same game date + same result = one position) that catches settled
  copies whose outcome payloads differ in formatting -- the byte-identical
  pass had been missing those twin-board copies all along (190 historical
  dups voided on first run: 89 top_25_board + 101 lock_of_day). Curated
  corrected to 618-241 / +15.4% all-time, last-30 -8.0%. Numbers moved DOWN
  on wins -- correct, do not restore. Any NEW source must emit markets in
  the boards' casing, but the key no longer cares.


- **2026-08-13 (latest) — NFL PROPS UNIVERSE WIDENED + WEEK 1 PREVIEW +
  PLAYER EXPLORER:** shared baseline machinery extracted to nfl_baselines.py
  (roster/id resolution, cached 2025 season baselines, info-dict ladder) --
  BOTH nfl_player_props and nfl_dfs import it so the universes can't drift
  (refactor verified result-identical: 201 projected, optimal 150.8 @ 50k).
  nfl_player_props v2: the in-season universe is now EVERY baseline-resolvable
  skill player on the slate (curated 28 sim at SIM_N=4000, wide universe at
  SIM_N_WIDE=2000), not just the hand-curated DB. During preseason the PICKS
  gate stands (rows/strong_edges empty -- the ledger collector reads ONLY
  strong_edges) but the desk publishes a WEEK 1 PREVIEW off the DK slate:
  preview_rows (top 150 leans, collector-invisible keys) + the new data-rich
  artifact data/nfl_player_projections.json (191 players, per-market
  mean/median/p10/p90 + P(over) at EVERY standard line + DK pts + salary
  join; mode preview|live). nfl-players.html = the explorer (search, pos
  filters, expandable per-player market tables) -- in nav Players menu +
  directory. dk_points_from_sims moved into nfl_player_props (nfl_dfs
  delegates). At Week 1 everything flips live automatically: picks resume on
  the WIDENED universe, artifact switches to mode 'live'.

- **2026-08-13 (later) — NFL DFS DESK (nfl_dfs.py -> data/nfl_dfs.json ->
  nfl-dfs.html):** weekly DraftKings projections from OUR Monte Carlo + exact
  salary-cap optimal lineups. Salaries come from DK's PUBLIC endpoints
  (www.draftkings.com/lobby/getcontests?sport=NFL -> ContestTypeId 21 classic
  groups -> api.draftkings.com/draftgroups/v1/draftgroups/{id}/draftables;
  EdgeStat UA works; preseason slates skipped by the same Week-1 gate; slate
  cached no-clobber in nfl_dfs_salaries.json). Projections: the props desk's
  play-level MC (_sim_player) DK-scored PER SIMULATION (100/300-yd bonuses land
  on tail sims) -> mean/floor p10/ceiling p90/value. Baseline priority:
  curated NFL_PLAYER_DB > 2025 season per-game rates (ESPN core-API athlete
  statistics, one-time-cached in data/nfl_2025_baselines.json -- do NOT
  delete; ~700 players seeded locally; CI tops up new slate players at
  <=NFL_DFS_FETCH_CAP=120/run) > current-season gamelogs (>=3 games; the
  rookie path). DST is VEGAS-IMPLIED (opp implied total -> DK points-allowed
  tier curve + league-avg sacks/TO/TD ~= +5.9 base), labeled as such, flat
  league-average when lines haven't posted. OPTIMIZER: exact 0/1 DP over
  (position-counts x $100 salary buckets) for DK Classic
  (QB/2RB/3WR/TE/FLEX/DST, $50k) -- verified against brute-force enumeration
  in the module's __main__ self-test (run it after ANY optimizer edit); three
  builds (mean/p90 ceiling/p10 cash) + budget variants (45/48/50k) off one DP
  table. O/IR players excluded from pools; unprojected players (rookies w/o
  2025 stats) counted + top names disclosed, never silently dropped. DFS rows
  NEVER enter the betting ledger. Wired into daily-pipeline after
  nfl_player_props; page linked from nfl.html + directory ("Parlays & DFS").

- **2026-08-13 — NFL SEASON BUILD-OUT + the preseason honesty gate:** football
  is live in the odds stack — espn_odds DEFAULT_SPORTS now includes
  nfl/ncaaf/ncaab (SPORT_PATHS already had them); real DK lines flow to the
  desks, line_movement, and clv_tracker with zero extra plumbing (all
  sport-generic; verified 16 NFL + 99 NCAAF games priced). nfl.html is a real
  desk now: preseason banner, Live Book Lines card (espn_odds NFL rows), Model
  Props card (nfl_player_props strong_edges). **THE GATE (do not regress):**
  nfl_player_props takes NO picks while nfl_state.season_status == "preseason"
  — season-baseline projections priced starters as if they'd play four
  quarters (0.80 conviction at -400 on six-snap cameos); 95 such preseason
  props had already entered the ledger and were retired by
  all_picks_tracker._void_preseason_nfl (idempotent, runs BEFORE settlement so
  they can never grade first; _reconcile_settled_voids treats 'preseason'
  voids as intentional, same as 'duplicate wager'). The gated payload is
  shape-identical (rows/strong_edges empty + preseason_note) and the page
  renders the why; nfl.html also blanks the synthetic-ELO P(home)/fair columns
  during preseason (0-0 records make them fiction). Everything self-activates
  at Week 1 (2026-09-08 cutoff constant _NFL_2026_WEEK1).

- **2026-08-10 — ALPHA PICK RULE v2 + curated-attribution fix (read before touching
  alpha_pick_record / the curated stats):** investigation of the flat last-30
  (curated 54-50/−0.8u vs +23.8% prior) found THREE stacked causes. (1) The
  PrizePicks feed DIED 2026-07-09 — hard 403 even from a home IP with browser
  headers (TLS-fingerprint wall); prizepicks_lines.json has 0 lines. The proven
  soft-line under families (PP_batter_hrr_under_*: 533-110, +149u lifetime) went
  dormant with it — that WAS most of the +23.8% era. Revival needs a real props
  data source (paid Odds API tier), not headers. (2) The ADD-GUARD let whichever
  feed ran first keep sole credit for a wager, so the curated boards' copies were
  skipped and the curated record silently drained to game-lines-only. FIX:
  the guard now stamps `also_sources` on the kept OPEN copy and the curated
  rollup counts source OR also_sources (attribution only — still one row, never
  a double count). Settled picks are never stamped retroactively. (3) MLB game
  totals went 5-16/−11.5u in August (stale-input suspicion during the ESPN
  outage) — lifetime the class is +2.1%/n=239 so it does NOT meet the frozen
  proven-negative bar; NOT cut (that would be tail-chasing); watch it.
  **ALPHA PICK RULE v2 (forward-only, date-gated at 2026-08-10):** v1's raw-EV
  rule was selecting from proven-negative families (hit_no etc.) once PP died —
  3-8 over its last 11, violating the "every surfaced pick routes through
  prob_calibration" rule. v2: candidates must clear is_proven_negative +
  is_overconfident, the conviction band applies to the CALIBRATED prob, and
  calibrated EV at recorded odds must clear +2% — else an honest NO-PICK day
  (real payload + postable "we don't force bets" tweet; alpha_tweet.py and
  alpha-pick.html both render it). Pool widened to MLB MONEYLINES (v1 excluded
  them because "MLs void in the ledger" — false since espn_odds settlement;
  family is 68-38/+21% lifetime, priced against a real book line; totals stay
  out). Days < 2026-08-10 replay under v1 BYTE-IDENTICALLY — the 48-16 v1
  record is never restated; payload discloses rule_v2 + record_v2 and the page
  carries a dated amendment note. Each v2 day's selection LOCKS on first sight
  in data/alpha_v2_selections.json (append-only, cron-committed) and replays
  from the lock forever — late ledger arrivals or calibration drift must never
  rewrite a published day. Do NOT delete the sidecar; do NOT "fix" a locked
  day's pick.
  **SAME-DAY FOLLOW-UP — the SETTLEMENT-UNIVERSE fix (player_gamelogs.py):**
  the gamelog fetch universe was "players with open props today" (props.json +
  pickem.json) but the GRADER's universe is "players on pending ledger picks" —
  disjoint sets once the boards went quiet (dead PP feed, exhausted odds
  quota). Result: MLB batter props entered by the model feeds could never
  grade; a 439-pick settlement backlog had silently accrued (the One Pick
  record was 48-16 only because its 8/3+ losses couldn't settle; truth after
  the fix = 48-22/+19%). player_gamelogs.py now ALSO fetches everyone on a
  pending MLB ledger pick (names resolve via sr.pitcher_id_by_name — a generic
  cached people-search) and refuses to clobber a useful cache with an empty
  fetch. If pendings ever pile up >2 days again, check THIS file's universe
  first. Also: the daily tweet's receipt now DATES itself when it isn't
  literally yesterday's slate ("8/2: …" not "Yesterday: …" after a gap), and
  weekly_receipts_thread renders ML picks as "SIDE moneyline (A @ B)".

- **2026-08-07 — ESPN 403 OUTAGE + fetch-header rules (do not regress):** ESPN
  (Akamai) began 403ing ~Aug 6: (1) any request with NO `Accept` header (urllib
  sends none by default; curl sends `Accept: */*`, so manual curl checks LIE);
  (2) from datacenter IPs (GitHub Actions), any Mozilla/browser-claiming UA
  whose TLS fingerprint is Python's (home IPs tolerate this — a local pass does
  NOT prove CI will pass; validate header changes in an Actions run). Every
  ESPN fetch now sends the honest `"User-Agent": "EdgeStat/1.0"` +
  `"Accept": "application/json, text/plain, */*"` — never "upgrade" a fetcher
  to a fake Chrome UA. The outage was silent for a day because every module
  degrades gracefully; the loud failure was nhl_goalie_matchup's degraded
  payload missing n_games/n_picks → KeyError in its __main__ summary print →
  10 straight daily-pipeline failures (same class as the slate_player_pot
  crash: DISPLAY CODE MUST NEVER ABORT THE RUN — degraded payloads must be
  shape-identical to success payloads, prints use .get()). NB: PrizePicks
  keeps its own browser-header stack (their bot-wall wants the opposite);
  the EdgeStat-UA rule is for ESPN hosts.

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
