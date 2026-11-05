# Odds integrity — incident record and source of truth (P0)

Owner: Brandon Leone. Started 2026-11-03. Branch `integrity/odds-provenance`
(nothing here reaches production without Brandon's approval).

## System facts (inspected)

- Repo `Keyvaniath/bpleone-betting`; site **betting.bpleone.com** (`CNAME`),
  static pages served from `main` (push to main = live). Python pipeline in
  `python/`, run by GitHub Actions (`daily-pipeline.yml` 14:00/22:00 UTC,
  `continuous-heartbeat.yml` ~2h, `live-games.yml` 15 min) which commit
  `data/*.json` back to main.
- Odds sources: DraftKings via ESPN's public scoreboard (`python/espn_odds.py`
  -> `data/espn_odds.json`, history `data/odds_history.json`); The Odds API
  (`ODDS_API_KEY`, lapsed); Bovada board (`multi_book_lines.json`); PrizePicks
  lines (no odds). **No source carries sportsbook player-prop prices.**
- Predictions are statistical/rule models (Elo, Poisson/NB/normal, Monte
  Carlo), no LLM in the probability path.
- Record of truth: `data/all_picks_ledger.json` (+ cold `ledger_archive.json`),
  built by `python/all_picks_tracker.py`; settlement in the same file.
- Daily Alpha card: `python/alpha_pick_of_day.py` -> `alpha_pick_record.py` ->
  `alpha_email.py --send-self` (owner-only SMTP if secrets exist) + a comment on
  the "EdgeStat daily Alpha" GitHub issue; suppressed off-season.

## Where placeholder / synthetic prices enter (confirmed in code)

| Path | File:line | What it does | Reaches |
|---|---|---|---|
| Selection EV default | `todays_top_plays.py:_fair_odds_for_source` (~l.100) | a candidate with no price gets -110 (-136 PrizePicks), unflagged | EV, Kelly, ranking -> Top Plays, Alpha Pick, locks, email |
| Selection "EV" vs own price | `todays_top_plays.py:~l.385`, `alpha_pick_of_day.py:16-19, 235-250` | props: `decimal_odds` = the MODEL's fair price ("book proxy"); EV = calibrated p x model price - 1 (not a market quote) | Alpha ranking, email |
| Grader payout fallback | `all_picks_tracker.py:3058, 3578, 3622` | no price -> decimal 1.91 (-110) | settled units, every record |
| POD payout fallback | `pod_pl_tracker.py:110` | no market_price -> 1.91 | POD record |
| Model totals juice | `mlb_model.py:184-185` | unposted total -> -110/-110 | MLB total EV |
| Team-total edges | `book_vs_model_team.py:198-199` | totals assumed -110/-110 | book-vs-model edges |
| Evaluation fallbacks | `forward_test.py:54`, `validate_curation_oos.py:51`, `prob_calibration.py:201`, `durable_edge_analysis.py:28,56`, `family_durability.py:42`, `dow_pl.py:43` | missing payout -> +0.91 | held-out / forward tests, calibration, curation |
| Threshold tuning | `param_recommender.py:282` | units = wins x 0.909 - losses | auto-applied parameter changes |
| Other EV/ROI | `slate_roi_projector.py:73,87`, `sharpe_ranking.py`, `alpha_pod_tracker.py:99`, `cws/kbo/tennis_pot_history`, `outage_backfill.py:101` | -110 / 1.91 defaults | secondary boards |

Not contamination (illustrative only): `risk.py` / `train.py` bankroll and
Kelly-heatmap demos at -110.

## Corrections already applied (2026-10-23 .. 11-03, on main)

Seeds applied idempotently each ledger build (`ml_reprice.apply_ledger`), raw
recorded fields kept (`fair_american`, `repriced.from_payout`, `voided_reason`):
A (10/23) and B/C (10/26) MLB moneylines re-priced at DK pre-game or voided;
D (10/26) totals on lines no book posted voided / DK juice; E (11/03) 481
placeholder-priced settled picks -> 109 re-priced at a real pre-game book price
(DK > Odds API > Bovada, exact line, never after first pitch), 372 voided (all
props: no prop price exists); E `model_fair` (11/03) 60 curated game lines
graded at the model's own price -> 32 re-priced, 28 voided. PrizePicks props
split out of the curated headline (own line); fractional locks-history stakes
rescaled to 1u. Intake gate `_block_unpriced` (no book price + -110 fair that
is not the model's ~52.4%) stops new ones.

## Classification (current, to be formalised per record)

- **A — verified genuine timestamped odds:** game lines with `book_american`
  stamped at intake from a DK snapshot taken before the pick.
- **B — reconstructed:** `repriced` rows (seeds A-E) priced from a pre-game
  snapshot in git history; provenance in `repriced.book` / `book_snapshot_at`.
- **C — unverifiable, excluded:** voided rows (`voided_reason` starts
  `unpriced` / `unposted`); and every prop graded at the model's own fair
  price or PrizePicks' break-even (no sportsbook quote) -- excluded from the
  curated headline but still in the all-picks / Alpha figures. OPEN.

## Fail-closed fix (branch `integrity/odds-provenance`, 2026-11-03, NOT merged)

- `python/quotes.py` -- the pricing contract: exact American->decimal (|A|<100
  / missing -> None, never a default), binary EV, no-vig from one matched
  two-way market, model-derived minimum acceptable price; `find_quote` reads a
  DraftKings snapshot (`espn_odds.json`) and returns a quote with provenance
  `book_snapshot`, book, provider, event id, scheduled start, selection, line,
  `observed_at`, `snapshot_id`; `actionable` rejects missing, invalid, stale
  (> 180 min), started / within 5 min of start, and non-book provenance
  (synthetic, model_fair, venue_breakeven, reconstructed). Stable rejection
  codes. Props -> `unsupported_market` (no sportsbook prop source).
- `todays_top_plays.py` ranks only quoted candidates; EV at the quoted price;
  everything else -> `projections` (actionable: false, reason) + a `funnel`
  block. Today: 639 input -> 0 actionable (562 unsupported props, 62 game
  lines with no current DK quote, 12 curated out, 3 ungradeable).
- `alpha_pick_of_day.py` re-prices every candidate (incl. the book-vs-model
  totals that assumed -110/-110) through the contract; `other_picks` flagged
  actionable / non-actionable. `alpha_pick_record.py` rule v3 (from
  2026-11-04): an Alpha needs a `book_american`; locked history unchanged
  (verified byte-identical: 67-38).
- Settlement: no price -> void "unpriced: no price on record at settlement"
  (outcome kept), never 1.91; the two re-grade passes skip unpriced picks.
  POD / POT / alpha-POD / outage records: no price -> no win credit / no
  record. Evaluation (`forward_test`, `validate_curation_oos`,
  `prob_calibration`, `durable_edge_analysis`, `family_durability`, `dow_pl`):
  missing payout -> no win credit (was +0.91). `param_recommender` Kelly-sizing
  rule (ROI at an assumed -110, auto-applied) disabled.
- Tests: `python/tests/test_odds_integrity.py` (26, pass locally with pytest
  9.1.1) + a CI step in `daily-pipeline.yml`. Real data: 0 picks newly voided,
  curated unchanged (290-243, -3.92u).

## Price provenance (branch `integrity/price-provenance`, 2026-11-03, NOT merged)

Every ledger + archive row carries `price_provenance` {class, kind, book,
observed_at, snapshot_id, inferred}: **A** `book_snapshot` (timestamped quote
at pick time -- stamped at intake from the quote the board / desk carried);
**B** `reconstructed` (seed re-price, `repriced.book` / snapshot) or
`book_untimestamped` (book price stamped without a time -- all history before
11/03); **C** `model_fair`, `venue_breakeven` (PrizePicks), `unpriced`. Backfill
is `inferred: true`; a re-price moves A -> B and keeps
`price_provenance_at_intake`. Ledger summary `by_price_class` (all / curated),
shown on track-record. Backfill result: all settled B 299-252 (-4.09u), C
9,390-11,113 (-3,535u), A none yet; curated entirely B 289-243 (-4.60u) after
one more curated total (`over_7.5`, lower case, missed by the case-sensitive
audit) was voided. Fixed with it: the `top_25_board` collector dropped
`book_american` / `quote` (a quoted board pick would have been graded at the
model's price); the game-lines desk now attaches its snapshot quote. Tests: 29
pass.

## Website honest states (branch `site/honest-states`, 2026-11-03, NOT merged)

`python/today_status.py` -> `data/today_status.json` (counts only, from
espn_odds / game_lines_desk / today / todays_top_plays / alpha_pick_of_day):
per sport games on the DK board, priced, picks, held back, desk verdict, a
plain-language status; the Alpha state with the funnel reason; the props
note. index.html: "Today, by sport" strip under the hero; Play of the Day no
longer stuck on "Loading..." (`if (!pod) return` left the placeholder up);
Alpha card shows the reason and the BOOK price (was labelled Fair Odds);
Book Edge / Parlay cards say why they are empty; the parlay card is labelled
research-only. Runs in the daily late pass, the heartbeat and live-games.

## Remaining pricing risks (branch `integrity/pricing-risks`, 2026-11-03, NOT merged)

- `ml_reprice.apply_ledger`: the pending-pick fill stamped "the live DK line"
  from `espn_odds.by_matchup` -- not status-filtered (could be IN-PLAY) and a
  LATER price than at publication. Removed (0 pending picks used it today); the
  intake price gate refuses unpriced picks, legacy ones void at settlement.
- `mlb_model.py`: total edges only at the real posted juice (was -110).
- `book_vs_model_team.py`: totals at the real over/under juice (was 1.909 on
  both sides); the row's `book_american` is the side's real price (was a
  hard-coded -110), `book_decimal` the side's own (was the OVER's for an
  UNDER), no-vig from this market's two sides (was 0.5).
- `slate_roi_projector.py`: real price or skipped (was -110); the elite-board
  block that INVENTED p_win (0.50 + 0.03/signal) and a -115 price removed.
- `sharpe_ranking.py`: ranks only at a real `book_american` (was -110).
- `parlays.py`: a game leg needs a real market price (was -110).
- `player_breakdown.py` (+ player.html): ROI over priced plays only (was -110
  for missing prices); "no priced plays" shown.
- **`arbitrage.py` published a hand-written DEMO daily** (invented quotes, a
  book named "Synthetic-Glitch", a line "intentionally errored") as
  `data/arbitrage.json`, rendered on arbitrage.html / extras.js. Now publishes
  `available: false` + reason (one live book; arbitrage needs 2+); `--demo`
  prints only. linemaker.json is a demo but labelled "Illustrative simulation"
  on its page -> kept.
- Remaining -110 literals are docstrings, detection of placeholders
  (`calibration_status`, intake gate), the applied one-shot, labelled demos
  (`risk.py`, `portfolio.py`, `pipeline.py` DEMO_SLATE -- blocked at intake), and
  model-conviction prop selection bands "vs a -110 book" (props are never
  actionable). Tests: 35 pass.

## Open (P0)

1. (merged a5aee8bd58, approved 11/03) selection + settlement + evaluation fail closed.
2. CLOSED 2026-11-05 (re-inspected): `mlb_model.py` edges a total only at its
   posted juice; `book_vs_model_team.py` totals need the real over/under
   price (no -110/-110); `sharpe_ranking.py` ranks only rows with
   `book_american`; `slate_roi_projector.py` takes a real price or nothing and
   its elite-board block (invented p and -115) iterates over `[]`.
3. (merged c413a65fd9) per-record `price_provenance`.
   NFL feed (branch `integrity/nfl-feed`): `espn_odds.fetch_sport` also
   requests the NEXT week for NFL / NCAAF (`week=N+1&seasontype=T` from the
   bare board, postseason week 1 after the regular season), merged by event
   id. 11/3: the bare board held 14 Week-9 finals and 0 upcoming games; with
   the fix 15 upcoming NFL games carry DraftKings lines -> desk board 15 rows,
   4 picks, 4 games held as QB-uncertain. Follow-up CLOSED 2026-11-05:
   `ml_reprice` stamped pending placeholder moneylines from `by_matchup` (not
   status-filtered, and a later price than the one at publication).
   `apply_ledger` had dropped this 11/03; the one-shot `run()` still had it
   (marker-gated, so dormant) -- removed too, with a test (in-play board ->
   no price stamped).
4. Alpha record (locked days) is 70 props at the model's own price (+13.36u) +
   35 DK game lines (-0.78u): counting rule is Brandon's call.
5. TRACED 2026-11-05: `data/runtime_config.json` has been written once
   (1eaaabdcb1, 2026-05-18, "auto-apply medium-severity recommendations"):
   `calibration.n_prior_default` 8 -> 5 (from projection residuals in
   calibration_live: price-independent) and `live_edges.edge_threshold_pp`
   5 -> 3.5 (from a zero-alert day: price-independent). The only 0.909-unit
   rule (`plays.kelly_fraction`) never reached runtime_config and is disabled
   since 11/03. No applied parameter was tuned on placeholder payouts.
   Side note for Brandon (model behaviour, not changed): CLAUDE.md calls the
   legacy calibration_runner chain a no-op ("all corrections 1.0"); today's
   calibration_live has batter_total_bases 0.90 (n=63) and batter_hits 0.99
   (n=261), which pipeline.py applies to MLB projections. Dormant until MLB
   resumes.

## Site-wide audit (branch `integrity/nfl-settle-by-event`, 2026-11-03, NOT merged)

Trigger: Brandon's screenshot of nba.html -- P(home) 94.8% / "fair" -1835 for
MIL @ BOS off an Elo of a 7-game win-pct. Four read-only auditors covered all
121 live pages (sport desks; picks/edges/props; record/model pages; homepage,
Alpha, email) against the standard: every displayed number is a real book
price (DK, timestamped), a validated model's output with its verdict, or a
recorded result. ~150 findings; the P0 class was the same everywhere: a model
output with no sportsbook price presented as a pick, edge, price, record or
proof. Fixed (commits on this branch):

- NFL settlement by ESPN event id (exact-side fallback, refuses empty /
  ambiguous); 10/10 settled desk picks re-grade the same.
- `board_prior.py`: sport boards publish the desk blend (with verdict) or DK
  no-vig, else nothing; record Elo kept only as `p_home_win_record_elo`.
  Pages show DK moneylines, not fair prices.
- Fail closed at every "pick" surface: best_bets (DK-priced rows only),
  multi_sport_top (`projections`), nba_book_edges (validated desk only),
  locks (`by_price`: sportsbook 3-0 vs PrizePicks 307-59 unverified), Alpha
  slip (voids not pushes; no PP pool), email + tweet (record at DK prices
  19-16 -2.2% first; props "graded at the model's own odds").
- No-price desks (golf, LoL, CS, KBO, tennis, player pages): projections only,
  `is_pick: false`; no STRONG vs an assumed -120 book, no parlays, no TBD
  rows, no hard-coded totals or day-of-year starters; golf silent pre-event.
- Record pages: per-source record at sportsbook prices
  (`by_source[src].sportsbook`: lock_of_day 338-60 +188u -> 2-0 +1.1u);
  family_durability on A/B only (no durable family); held-out CI "entirely
  below zero"; synthetic track_record.json off every public page; models.html
  fabricated backtest table deleted; strategy-sim Kelly only on A/B.
- learning_integrity: tests calibration + ROI at real prices; the old code
  matched "WIN" against "won", so every pick scored a loss. SIDE EFFECT:
  learning_guards / self_learn_weights now see 15 trustworthy sources, not 52
  (model-weight change -- Brandon to confirm).
- Homepage: honest hero, model-projection cards / empty panels / mock
  newsletter / default parlay retired, receipts coloured by sign, no clv_log
  "CLV", steam = "line moved", not "sharp money".

Merged to main 2026-11-04 (5d252af7ee) on Brandon's go.

Backlog pass 2026-11-04 (branch integrity/backlog-1104):
- dow_pl: ROI by day only on sportsbook-priced rows (A/B, PrizePicks out);
  522 rows, not ~14k; best/worst day needs n >= 30 and the page says a +/-20%
  gap at n < 100 is noise.
- sport_coverage: IN-SEASON = pending picks or a game scheduled in the next 14
  days (state file); a props refresh alone no longer counts (WNBA, World Cup,
  KBO, CWS were IN-SEASON on one). Desks with no schedule feed (F1) keep the
  props rule.
- validate_curation_oos: caveats + headline follow the result (they asserted a
  significant edge while the held-out CI was [-7.3%, -2.5%]).
- clv_by_source: "leading indicator of real edge" -> open->close movement is a
  direction check, not CLV vs the logged price. self_train: "well-calibrated"
  -> home-bias check only.
- whale_picks / fade_picks: fade ROI uses the DK quote only (the fair-odds
  fallback is 0 by construction); whale copy no longer says "size up".
- nfl-players: P(over) chips neutral (no green/red edge colouring).
- 12 NBA modules: "LA Clippers" (ESPN's name) -> LAC; it fell back to "LA" and
  every Clippers player went unpriced.

Reviewed, not changed: the ~46 prop modules with a "STRONG vs hypothetical
-120" selection bar never store -120 as a price (rows carry the model fair
price, class C, excluded from every sportsbook record); *_pot_history pages
already render calibration only. docs/ is public, but so is the repo.
Still open: convergence ELITE = signal count (no price claim; picks hub gates
it on a quote); odds_key_preflight wording is accurate.

## Pricing guard + quote join (2026-11-04, branch integrity/pricing-guard)

Backlog branch merged to main 39badb82e0 on Brandon's go. Crash replay on the
merged main: 2/368 failing in base, off-day and nulls (outcomes.py and
smoke_tests.py, network only).

- `python/verify_pricing.py`: every row on 13 pick surfaces (todays_picks,
  top plays, best bets, multi-sport top, pregame alerts, bet slate, fades,
  whales, Alpha) must carry a sportsbook price that is not the model's fair
  price, observed <= 180 min before the artifact was written, for an event
  not yet started -- or say it is a projection (actionable/is_pick false). A
  12-case self-test runs first (a real -110 quote passes; fair-only, stale,
  started, in-play, non-book and untimestamped prices fail). Wired into
  daily-pipeline (after every pick producer) and the Smoke Test. Today's
  artifacts pass with 0 rows; the 10/12 artifacts fail with 151 violations.
- QUOTE JOIN BUG: espn_odds keys games by abbreviation ("JAX @ BAL"), the
  sport state files by full name ("Jacksonville Jaguars @ Baltimore Ravens").
  find_quote matched the strings exactly, so every NFL/NBA/NHL/NCAAF/NCAAB
  game-line candidate was "no_quote" even with a DK price posted.
  find_quote/price_candidate now take `event_id` (ESPN id, sport must agree).
- That miss was hiding a second problem: slate_team_pot read `p_home_win`
  (live / the record Elo on older states -- DET@MIA went out at 91.6%). It
  now reads the board's vetted `p_home_display` and carries event_id,
  p_source, desk_verdict. todays_top_plays ranks a sport-board game line only
  when p_source is the game-lines desk AND the verdict is PROMISING; DK
  no-vig is the market itself (reason market_prob), UNPROVEN / NO EDGE desks
  stay forward tests (reason desk_<verdict>). Today: 15 market_prob, 13
  desk_unproven, 0 ranked -- the board is still empty, now for the stated
  reason.
- best_bets DK props (paid Odds API, the ONLY prop rows with a real book
  price): each row now carries its DK quote (dk_over/dk_under, fetched at
  props.json generated_at, commence_time), must pass quotes.actionable, and
  its edge is the CALIBRATED probability's EV at that price (>= +2%). It used
  to publish the raw-model edge with no price or time (the CLAUDE.md TODO
  "apply recalibrate() in the prop edge path").
- Provenance carried through: locks_of_day (book_american + quote; new locks
  settle at the DK price), whale_picks, bet_slate (BOOK rows had the DK price
  in `fair_american`; POD/Alpha now carry the quote; page shows "DK Price"),
  book_vs_model_team (odds_observed_at per line_source), pipeline.py POD
  (odds_observed_at, commence_time, book) -> multi_sport_top.
- DEMO SLATE LEAK (found by the new guard in crash replay): when the MLB pull
  FAILS, build_slate returns DEMO_SLATE tagged is_demo, and no page honours
  the tag (~95 today.json consumers) -- with the network down, CIN @ COL ML
  -110 became the Play of the Day and a multi-sport top pick. pipeline.py and
  train.py now publish via `_production_manifest`: keep today's last good real
  slate (fetch_error, kept_from), else an empty slate with fetch_error; the
  demo slate only with `--demo`. Crash replay after: 2/369 failing (network
  only) in all three states, pricing guard passing.

Merged to main 2026-11-05 (4bf34c0e5b) on Brandon's go.

## Guard coverage + stale boards (2026-11-05, branch integrity/open-items-1105)

A scan of every data/*.json list that carries a price and an edge/play found
three current surfaces the guard did not check, all now in PICK_SURFACES:
- `picks_export.json` (public JSON + CSV): team-sport rows used
  `p_home_win` (the W-L record Elo on older states) and every row shipped at
  the model's fair price with no projection flag; the MLB POD row read a
  nonexistent `model_price` and so exported no price at all. Now: the
  board's vetted `p_home_display`, `price_basis` + `is_pick` on every
  row (a pick only at a sportsbook price), POD carries its DK `market_price`
  with observation time.
- `player_pot.json` (LoL/CS/KBO props, no sportsbook prices them): every
  row `is_pick: false`, `price_basis: model_fair`. The homepage card was
  already retired; the briefs already label it projections.
- `cfb_model.json`: edges carried a real DK price with no observation time.
  Now `odds_observed_at` + `book`, `generated_at` in UTC (espn_odds is
  UTC; local time made a fresh quote look like it came from the future), and
  NO edge when the DK board is > 180 min old (`board_fresh` /
  `board_age_min`; ncaaf.html says why). Before, the heartbeat could
  re-price CFB edges against a board hours old.
Smoke Test rebuilds these three from the commit's own code before the guard
(so a merge is not judged on artifacts the previous code wrote).
History files (locks_history, *_pot_history, rollups) are records, not
current picks, and stay out of the guard.

Merged to main 2026-11-05 (ac48825a59) on Brandon's go.

## One Alpha snapshot: site, tweet, email (2026-11-05, branch integrity/alpha-snapshot)

Mandate phase 8. alpha-pick.html, the tweet draft and the email are all
composed from alpha_pick_record.json in the same run. verify_pricing.py now
checks that on every run (part 3, with its own 6-case self-test): same
date, same pick state (pick / no-pick / off-season / withdrawn), and on a
pick day the DK price in the email subject, the tweet text and the tweet
payload -- never the model's fair price shown as the odds; an unpriced pick
shows no price anywhere.

Found while building it: alpha_tweet.json `picks[].odds` carried
`fair_american` (the model's own price) under the name "odds". The tweet
TEXT was already on the DK price (11/03); the public JSON field was not.
Now `odds` = the sportsbook price ("" when none) + `price_basis`.
Replayed 52 recorded days (8/10 - 11/05) of alpha_pick_record through the
current composers: 0 disagreements, 0 crashes. No recorded day carries a
DK price on the pick (pre-11/03 locks are never edited), so the DK path is
covered by an end-to-end test (fair -150 / DK -125).

## Pre-launch audit (2026-11-05, branch launch/audit-1105)

Brandon: "audit everything and find any issues -- make it perfect, this is the
last ask before we send it out to people." Method: a headless crawl of all
135 live pages (console errors, text leaks), a secrets scan of the public
repo, a phone-width probe of 24 key pages, four read-only auditors over
every page group against the standard above, each P0 re-verified by hand.

Clean before the pass: no secrets in the repo, no encoding damage, all 8
workflows green, 0 console errors on 135 pages, no NaN/undefined at phone
width, OG card + sitemap present.

Fixed on this branch (P0 first):
- WORKER WRITE PATH: `POST /admin/save-overrides` accepted any JSON from
  anyone; the heartbeat pulled it into `data/model_overrides.json`, which
  `self_learn_weights` blends into the model. Now: the route needs
  `X-EdgeStat-Admin: <ADMIN_TOKEN>` and is refused while the secret is
  unset; the D1 write routes FAIL CLOSED without `SYNC_TOKEN` (they used to
  open); the heartbeat sync step is removed and the script needs an explicit
  `EDGESTAT_OVERRIDES_SYNC=1`. NEEDS: `wrangler secret put ADMIN_TOKEN`,
  `wrangler secret put SYNC_TOKEN` (+ the EDGESTAT_SYNC_TOKEN GitHub secret
  with the same value) and `wrangler deploy` -- Brandon's actions.
- LEGAL PAGES every visitor accepts at the age gate were templates
  ("[LEGAL ENTITY NAME]", "[STATE]", "[DATE]", "Template notice ... not
  reviewed by an attorney"). Filled: Brandon Leone d/b/a bpleone, California
  courts (the bracketed arbitration clause dropped), dated 2026-11-05, one
  contact address. privacy.html now describes what happens: no analytics
  script, no cookies, Formspree holds the subscribe address, GitHub /
  Cloudflare / jsDelivr see IPs as hosts, no affiliate data. Counsel review
  is still owed (GO-OFFICIAL checklist).
- D1-FED PAGES OFFLINE: backtest-replayer.html and lifecycle.html read a
  Worker copy of the ledger that stopped syncing 2026-09-08 and stores
  payouts in a shape they could not read -> "+0.00u" for a 27-67 version,
  PrizePicks-era lock records shown as a record. Both are a notice page
  until the copy is rebuilt with price classes.
- NFL DFS: `nfl_dfs_calibration.play_key` mapped every status but Q to
  "healthy" (p_play 0.958) -- Davante Adams (IR), Lamar Jackson (OUT), Jalen
  Hurts (IR) topped the Val/$K column. IR/OUT/O/D/PUP/NFI/SUS -> p_play 0.02;
  the column shows the calibrated x_value.
- ESPN PLACEHOLDER LINES (-100000/+5000 "DraftKings" on lopsided college
  games) are dropped in espn_odds.py (|ml| > 3000) and guarded again in
  board_prior.py, so they no longer become a 98% "market" probability, a
  LOW_VIG flag, a line-move alert or a TRACK button.
- OFF-SEASON DESKS: espn_generic stops uppercasing ESPN's stale season type
  (WNBA "PLAYOFFS" three weeks after the Finals, CWS "SEASON" off a June 22
  final): `active_season` = games today or within 14 days; otherwise
  "no games scheduled -- last final <date>"; finals carry their date on the
  board; the static "LIVE" chip is hidden unless a game is in progress
  (nav.js, every page). live.html / live-momentum.html say the poller is
  MLB-only and label the stored LAD@SDP example and the 484-game CLV table
  as archived. mlb / player / f1 / wnba-players say off-season instead of
  "pipeline may not have run yet".
- NFL PROPS: 953/953 projections were "strong edges" with a "Fair" price
  column; now "projections", "Book price: none", and passing rows are held
  for teams whose starter the desk marks uncertain (BAL/CLE/MIN/NYG/PHI on
  11/05 -- Huntley and Jackson both had BAL pass_int rows).
- BOARD ROWS show the probability's source/verdict under the number on all
  nine desks (was hover-title only): "UNPROVEN", "NO EDGE", "DK no-vig".
  live-now.html uses `p_home_display` (NHL rows disagreed with nhl.html) and
  the golf bestbet card is gone.
- TRACK RECORD: Best/Worst/Live-settled showed the RECORDED price next to a
  payout at the DK price (TBR "+940" paying +0.73u); now `book_american`.
  The curated 289-243 / -0.86% line leads the page, same as the homepage;
  POD is a sub-line.
- ALPHA PAGE: the DK-priced 19-16 / -2.2% cell and sentence lead; the
  blended 67-38 (+12%) is labelled a hit record; the 35-6 slip bar (67
  voids) no longer leads; per-slot ROI% replaced by "model odds"; history
  prices labelled DK vs model; "Post to X" removed (account suspended); the
  daily-email operator card is owner-only (localStorage edgestat_owner=1);
  the hero says why there is no pick.
- HOMEPAGE: empty amber #staleBanner (CSS beat `hidden`); six "--" tiles
  now honest counts (picks at a DK price, line-move alerts from the tape);
  the three "--" play cards hide their tile grids on a no-play day; CLV
  card says the source was retired; the 3-0 / +62% locks line says "too few
  to mean anything"; the prove-it line excludes PrizePicks like the
  track-record chart; operator loop card never shown; "Last refresh" is the
  data time; ticker vocab humanized.
- PHONE NAV: `.mainnav` collapsed to a 64px column with a scrollbar on every
  page but the homepage; now a full-width swipeable row (style.css, cache
  bumped to ?v=20261105 on 121 pages + sw.js; main.js versioned too).
- SHELLS MADE HONEST: pricing ("Pro is not for sale yet", no Stripe claim,
  no fake free-account CTA), support, sportsbooks ("no partner link", no
  commission wording while there are no partners), subscribe copy
  ("occasional updates, sent by hand"), nav labels, about.html roadmap
  rewritten to the November state, alerts.html lede (a line move is a move),
  arbitrage copy (no "look square" / "free money"), prizepicks-value header
  (feed dark), config.html read-only (no GitHub-editor Apply), config /
  model-control out of the public directory, operator text off line-shop /
  pickem / status, nrfi tiles for prices that do not exist removed,
  trends "Avg CLV (real)" tile removed, props/parlays "DK" labels replaced
  by the row's book, STEAM_TOTAL 0.5 -> 1.0, sport_coverage no longer calls
  MLB IN-SEASON on two stale pending picks and lists NCAAB, slate_player_pot
  lists only players whose team plays today (was 463 NBA rows across 30
  teams on a 2-game night), tonight.html pitch-count empty state,
  methodology/clv/calibration-map use one CLV truth and label their
  universes, widget.html carries the 21+ line, a branded 404.html.

Verified after the pass: 49 integrity tests, pricing guard green on 16
surfaces, JS syntax on every edited script, the pages above re-probed on
localhost.

Left for Brandon (not code): GitHub Pages "Enforce HTTPS" is off
(http://betting.bpleone.com serves plain HTTP); the three Worker secrets and
`wrangler deploy` above; counsel review of the legal pages; whether to keep
serving the repo root (CLAUDE.md, X-LAUNCH-KIT.md, python/, worker source
are one URL away -- the repo is public anyway); the Odds API key has 500
requests this month while props.json has 0 props (no MLB; NBA/NFL props
would be the only sportsbook-priced props on the site).
