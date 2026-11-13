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

Done on Brandon's "flip the https toggle and fix all of those" (same day):
GitHub Pages Enforce HTTPS is ON (API, verified https_enforced true); the
Worker has ADMIN_TOKEN and SYNC_TOKEN secrets, the EDGESTAT_SYNC_TOKEN
GitHub secret matches, and the Worker is deployed (version 173fcae2):
POST /admin/save-overrides and /db/log-picks answer 401 without the token,
/db/health 200. The site no longer serves the repo's internals: .nojekyll
removed and _config.yml excludes *.md, python/, tools/, docs/, the Worker
source, legal/ and the deploy scripts (the repo itself stays public).

Still Brandon's: counsel review of the legal pages (GO-OFFICIAL checklist),
and whether to spend the Odds API's 500 monthly requests on NBA/NFL player
props -- today props.json has 0 props and no prop on the site carries a
sportsbook price.

## Play of the Day, cross-sport (2026-11-05, branch launch/audit-1105)

Brandon: "Play of the day can be from any sport -- we prefer it comes from
one of the major 4: NBA or hockey in the fall, football on Saturday /
Sunday." It had been MLB-only (today.json), so the page read "No MLB games
on today's slate" for the whole off-season.

`python/play_of_day.py` -> `data/play_of_day.json`, run right before every
ledger step (daily x2, heartbeat, live-games). Pool = every game-lines desk
pick (NFL/NBA/NHL from game_lines_desk.json, the college edge from
cfb_model.json, the MLB POD from today.json) whose game is TODAY (ET) and
whose DraftKings quote passes `quotes.actionable` (the desk stores the
snapshot stamp without the side's price, so the module attaches
book_american before the check). One play: best EV at the DK price, tier
first, major-4 before college. The desk's verdict sets the tier and is
printed on the play:

  0 MLB Play of the Day · 1 validated desk pick (PROMISING) · 2 forward-test
  play (UNPROVEN: logged at the DK price, graded, never curated) · 3
  experimental (college; the close is sharper).

A NO EDGE desk (NBA and NHL today, w = 0) makes no picks by rule and so
cannot produce a play; the page lists each sport's reason instead of
inventing one, and shows the next dated desk pick ("Next play: Sun NYJ
moneyline +440, forward test"). The standard is unchanged: nothing without a
live sportsbook price, nothing that hides its verdict.

Ledger: all_picks_tracker harvests the play as source "pod" AFTER the desk's
own row, so the add-guard folds it onto that row (also_sources=pod);
pod_pl_tracker grades it from there, so the POD record on track-record now
spans sports. verify_pricing checks `play_of_day.json:play` as a pick
surface. Tests: 3 (major-4 preference over a higher-EV college edge, stale
quote -> no play, NO EDGE never plays, college fallback labelled tier 3,
ledger ordering).

What this does NOT do: manufacture NBA/NHL plays. Those desks' own
validation says the model adds nothing to DraftKings' price; the lever for a
daily NBA play is the NBA model (injury/availability inputs), not the
selector.

## 2026-11-11: no play today, and why -- the lean study + NBA availability model

Brandon: "find the play for the day -- remember we do all of the 4 major
sports -- continue to build until it is complete." Wednesday 11/11: 10 NBA
games, 6 NHL, 3 college, no NFL, MLB off. The NBA and NHL desks are NO EDGE,
so the rule produces no play. Two things were measured before accepting that.

1. LEAN STUDY (would a "desk lean" on a NO EDGE desk be an honest play?).
   Walk-forward, this season, 1u at the DraftKings close:
     NBA (n=159, market LL 0.5418, Elo 0.5929): model EV >= 4% 44-59 -21.3%;
       prob 35-70% 18-33 -18.2%; + gap <= 10pp 12-18 -10.6%; gap 2-6pp 7-10
       -30.3%. When the model sits 10pp+ above the market the side wins 41.5%
       (market said 51.6%, model said 67.6%).
     NHL (n=291, market 0.6435, model 0.6510): EV >= 4% 57-77 -10.3%; banded
       55-67 -3.8%; gap 2-6pp 44-62 -21.4%.
   Every rule loses on both sports: where the model and DraftKings disagree,
   DraftKings is right. A featured "lean" would be a knowingly negative-EV
   pick, so the Play of the Day does NOT get a NO-EDGE-desk tier. (Baselines,
   for scale: every favourite NBA +3.4% / NHL +2.1%, every underdog -30% /
   -16%; "follow a 2pp line move at the close" NHL 29-10 but NBA 36-26 at
   -0.7% -- one of ten rules on two sports, not a signal.)

2. NBA MODEL v2 -- AVAILABILITY + REST (`python/nba_avail.py`, seed
   `tools/build_nba_avail_seed.py` -> `data/nba_player_games.json`: 1,471
   finals since 2025-10-21, 644 players, minutes + Game Score per game, grown
   each desk run). Walk-forward value missing = roster players not playing x
   expected minutes x (Game Score per minute above replacement), minus the
   team's own running average (Elo already absorbed what it has seen); plus
   back-to-back. Logistic on [logit(Elo), avail, rest, 1]. The four constants
   were chosen on LAST season only (54-point grid, split-half CV 0.5957).
     last season (fit, n=1,125): Elo 0.5991 -> 0.5848
     THIS season vs the DK close (n=159, looked at once): Elo 0.5929, v2
       0.5958, DraftKings 0.5418 -> blend w = 0 -> NO EDGE, unchanged.
   Honest reading: availability is real signal (last season), but three weeks
   into a season the roster/minutes state is thin and the market is far ahead
   of any Elo-based prior. v2 is the NBA desk's model of record (selected on
   last season, not on this one); the gate decides, and it says no picks.
   Live: ESPN's injury report per game (Out = out, Day-To-Day = half); a game
   with >= 2.5 Game Score points of Day-To-Day value is blocked. The desk card
   shows the ladder, the finding, and each game's listed absences and their
   value vs the team's usual.

Result for the day: NO PLAY (stated with each sport's reason), next dated
plays Sat 11/14 (college, experimental) and Sun 11/15 (NFL forward tests).
play-of-day.html now also shows today's major-sport board at DraftKings
(prices, not picks). What would change the answer for NBA/NHL: a model that
beats the DK close in the walk-forward test -- not a looser selector.

## 2026-11-11 (later): merged to main, two deploy defects fixed, totals tested

`launch/audit-1105` merged to main (38f0bbcb1b) on Brandon's "merge the audit".
GitHub had an Actions/Pages outage at the time: the first Pages run died at
startup with no jobs (not a Jekyll error); the next build succeeded.

1. JEKYLL EXCLUDE LIST HID THREE CONTENT FILES. `*.md` is excluded from the
   site so CLAUDE.md and the launch kit are not served, but brief.html and
   daily-summary.html fetch data/auto_brief.md, data/daily_summary.md and
   data/daily_summary_v2.md. Fix in `_config.yml`: `include:` those basenames
   (include beats exclude in Jekyll 3.10's entry filter) and
   `optional_front_matter: enabled: false` (GitHub Pages enables that plugin by
   default; it would render Markdown without front matter to .html). Verified
   live after the build: the three files 200 as text/markdown; CLAUDE.md,
   python/, tools/, docs/, cloudflare-worker/, legal/, *.bat, _config.yml all
   404; 171 pages/scripts/assets byte-identical to the repo. Test:
   `test_pages_config_serves_every_markdown_file_a_page_fetches`.

2. AN UNESCAPED APOSTROPHE KILLED A SCRIPT BLOCK. The 11/5 audit changed a
   default string in alpha-pick.html to "No prop projections on today's slate."
   inside a single-quoted JS string: a syntax error, so that whole inline
   script (the Alpha Props slate) did not run. It reached main with the merge
   and was live for about an hour. Nothing caught it because the Smoke Test
   only ran on python changes and no check parsed page scripts. Now:
   `tools/check_inline_js.js` parses (never executes) every inline script on
   every root page plus js/*.js and sw.js (217 scripts); the Smoke Test runs it
   and the integrity tests on page/script pushes too; pytest wraps it
   (`test_every_inline_page_script_parses`). The same check caught a second
   instance in the share card below before it left the machine.
   RULE: text inside a JS string on a page uses &#39; for an apostrophe.

3. TOTALS: NO EDGE ON ALL THREE SPORTS (do not re-run with the same inputs).
   Question: moneylines give no NBA/NHL play; do totals? The line history has
   DraftKings' real over/under prices (spread prices are NOT recorded, so a
   spread desk cannot be priced honestly and was not attempted). Pre-registered:
   additive offence/defence EWMA chosen on LAST season only; this season's
   DK-priced games; the desk's own gate (blend weight w fitted on the over/under
   log loss vs DraftKings' no-vig over probability; NO EDGE when w = 0).
     NFL n=136: DK 0.6923, model 0.7399, w=0. Betting the raw model: 45-50, -9.8%.
     NBA n=159: DK 0.6933, model 0.7501, w=0. Raw model: 65-70, -8.1%.
     NHL n=291: DK 0.6915, model 0.7065, w=0. Raw model: 30-59, -36.7%.
   (Coin flip = 0.6931: DraftKings' totals are priced to a coin flip and a
   points-for/points-against model is worse than that.) A first pass compared
   squared error against the posted NUMBER and made NHL look marginal (blend
   w=0.65): wrong test -- in the NHL the book moves the price, not the 6.5, so
   the comparison has to be against the price. Script: tools/totals_study.py.
   A totals desk would need inputs the market does not already have in the
   price (confirmed lineups/goalies at bet time, pace/shot-quality data).

4. SHARE TEXT FOR THE DAY'S CARD. play_of_day.json now carries `post`: a
   copy-ready text (<= 280 chars) for the play or the no-play day, shown on
   play-of-day.html with Copy / Open in Bluesky / Open in Threads. DRAFT ONLY:
   nothing posts by itself (machine writes, Brandon sends; no X link). A price
   appears only for today's play -- actionable by construction -- with the
   desk's tier and the time the price was seen; the next play is named without
   a price; a no-play day says why. Test:
   `test_play_of_day_post_quotes_a_price_only_for_todays_play`.

CI on the merge: Smoke Test green, Daily pipeline green (failure gate clean,
which includes the pricing guard and the integrity tests).

5. PUSHED ON HIS "push it" (c25bf2ba35): the alpha-pick script fix, the script
   parser in the Smoke Test, and the share card. Verified live: the Alpha hero
   script runs, the share text is in play_of_day.json, Smoke Test green in CI
   with the new steps.

6. SELF-AUDIT AFTER THE DEPLOY, two more checks.
   a. RUNTIME CRAWL: all 136 root pages loaded in a browser on localhost, each
      given time to finish its fetches; uncaught errors, unhandled rejections,
      console.error and visible "undefined / NaN / [object Object] / Loading /
      Failed to load" text were collected. Result: none on any page. (The hook
      attaches just after navigation, so an error thrown in the very first
      inline script could be missed; the syntax parser covers that class.)
   b. DEAD REFERENCES: tools/check_site_refs.py resolves every local href, src
      and fetch target on every page and script (1,469 references) against what
      the Pages build serves (tracked, not excluded by _config.yml, no "_" or
      "." path segment). One real defect: 404.html pointed at a favicon that
      does not exist, and its links were relative, so the 404 page shown for a
      nested path (/a/b) linked to /a/index.html. Now absolute paths and the
      real icon. The checker runs in the Smoke Test and under pytest
      (`test_every_local_page_reference_is_served`).

## 2026-11-11 (night): a play for each major sport -- desk pick, or a labelled MODEL LEAN

Brandon, after a no-play Wednesday with 10 NBA and 6 NHL games: "there are no
plays across all sports? even NBA or hockey tomorrow? you can pick your play
from any sport not just NFL, it would be nice if you had a play of the day for
each of the 4 sports when they play." This is his call, made with the lean
study in front of him. It is implemented so that the standard is not lowered
SILENTLY: a lean is a different, lower tier, named as such everywhere.

WHAT A LEAN IS (`game_lines_desk.LEAN_RULE`, written down before its record
was computed, not tuned). The 11/11 lean study showed that betting the model
AGAINST DraftKings loses on NBA and NHL. So a lean is taken only where the
model and the market AGREE: the side that is the favourite by both the desk
model and DraftKings' no-vig price (each >= 55%), priced no shorter than -300;
one per sport per day, the game with the highest min(model, DK) probability.
A game the desk holds for an uncertain QB or a material day-to-day NBA player
gets no lean either. An unconfirmed NHL goalie does not block a lean (the
record below uses the projected-goalie model, which is what is knowable then).

WHAT IT IS NOT. Not an edge. At DraftKings' own no-vig probability the expected
value of a moneyline favourite is the book's margin, about -4% per bet. Every
surface says so: tier 4 "model lean (no proven edge)", the reason line, the
hero note, the desk card, the share text ("A lean is not a proven edge.").

WALK-FORWARD RECORD THIS SEASON (one lean per game day, 1u at the DK close):
  NFL 13-4, +1.80u (17 days)   NHL 30-11, +2.37u (41 days)   NBA 11-8, -3.06u (19 days)
Small samples around an expected -4%; published next to every lean and
refreshed each run (`sports.<sport>.lean.backtest`).

WHERE IT SHOWS. `play_of_day.json` gains `sport_plays` (the best play for each
major sport that plays today, any tier). The single featured `play` is the best
of them by tier, so a lean is featured only when no desk pick (tiers 0-3)
qualifies anywhere. play-of-day.html: "Today's play in each sport"; homepage
card: "Also today"; desk cards: the lean on the board row and the rule's
record. The next dated play is never a lean (a lean is made on the day).

THE RECORD STAYS CLEAN. A lean is logged in the ledger under source
`sport_lean` at the real DraftKings price and graded on the final (NBA
moneylines had no grader: added, by ESPN event id). `sport_lean` matches no
curated prefix, and a featured lean is NOT harvested as `pod` (tiers 1-3 only),
so leans never enter the curated record or the Play of the Day record. The
pricing guard checks `sport_plays` like every other pick surface: a lean needs
a fresh, pre-start DraftKings quote or it is not shown.

Tests: lean rule + record; per-sport plays and featuring order; ledger source;
NBA moneyline grading. 62 pass.

LEANS ARE ACCOUNTED FOR IN PUBLIC (same night). ledger_summary.json gains
`sport_leans`: the forward record of every lean actually logged (W-L, units at
the DraftKings price logged, pending, by sport, the 12 most recent with
finals). Voided rows are excluded. play_of_day.json carries it as
`lean_forward` (from the ledger's previous run) and the "Today's play in each
sport" card shows "Leans logged so far" with the latest results;
track-record.html shows it as its own line next to the PrizePicks line:
"separate, not an edge, not curated". The walk-forward backtest and the
forward record are two different numbers and are labelled as such.

PLAYS HISTORY, ALL TIERS (same night). A sport play that is a desk pick
(tiers 1-3) is now tagged in the ledger as `sport_play`: listed after the desk
rows, so the add-guard folds it onto the desk's own row as
also_sources=sport_play (one row, attribution only; matches no curated prefix,
which a test reads from the ledger source). ledger_summary.json gains
`sport_plays`: desk picks and leans counted SEPARATELY (never summed) plus the
16 most recent plays with results. play-of-day.html shows "Plays logged so
far" from it (falls back to the leans-only block on older data).

## 2026-11-12: The Board -- every game, graded; Alpha = the day's top-scored bets

Brandon: "we want to have odds and bets for each sport and game and grade it
and then have our alpha picks which is our 3-5 highest graded scored picks
from each day in addition to being able to sort by sport -- copy the UI of
something similar to an underdog or prizepicks with how easy it is."

`python/board.py` -> `data/board.json` -> `board.html` (top nav, phone tab bar,
homepage "Start here", directory). Runs right after play_of_day.py in the
daily pipeline (both passes), the heartbeat and live-games.

WHAT IS ON IT. Every pre-game NFL / NBA / NHL game on the DraftKings board for
today and the next 7 days (MLB joins in season): both moneylines, the total
with its real over/under prices, the spread number (no spread PRICE is
recorded, so it is never a bet), the model and no-vig probabilities, our side,
a grade, a score and one plain reason. Every price carries the time it was
observed and its snapshot id. The page marks a game "started" from the clock.

THE GRADE (fixed by rule; `board.score_pick`; not tuned on results):
  A 85-100  desk pick, PROMISING desk      85 + min(15, EV%)
  B 65-80   desk pick, UNPROVEN desk       65 + min(15, EV%)
  C 40-60   model lean (LEAN_RULE)         40 + 20 * (min(p_model, p_dk) - .55) / .25
  D 35 / 25 NO BET. Model side shown for information: model and market agree
            but outside the lean rule (35), or they disagree (25). The 11/11
            lean study is why a disagreement is not a bet.
  HOLD      no side: QB or day-to-day player unsettled.
Only A, B, C are bets. D and HOLD are never logged.

ALPHA PICKS (his definition): the 3 to 5 highest-scored bets of the day, any
grade. Provisional before 11:00 ET; from the first run at or after 11:00 ET
the list is LOCKED in `data/board_alpha_log.json` (append-only): a locked pick
is never removed or re-priced; the list only grows to five with games that had
no line at lock. Never padded: fewer than three bets shows fewer than three.
On a day with no A/B bet the Alpha picks are grade C leans and say so. They
are a SEPARATE list from the MLB Alpha Pick (alpha_pick_record.json, locked
days, its own +2% edge gate); both pages say so.

RECORD. A board bet is logged on its GAME DAY only (later days are a preview)
at that day's DraftKings price: ledger sources `board_pick` and `board_alpha`,
listed after the desk rows and the leans so they fold onto the existing row
(also_sources) and only the remaining leans become rows. Neither is a curated
prefix (test reads the prefix list from the ledger source). ledger_summary
`board`: all bets, alpha, by grade (grade derived from what the row IS: lean =
C, proven desk = A, else B), by sport, by day, 60 most recent with finals.
board.html "Graded so far" reads it (one run behind, like the leans).

CALIBRATION FIREWALL. The moneyline families (ml_home / ml_away) are shared
across sports and MLB's Alpha gate reads their evidence. A lean is not a claim
that the model beats the price, so `prob_calibration.judged()` is False for
sources sport_lean / board_pick / board_alpha: a season of -4% leans cannot
condemn the family. Desk picks keep their own source and still count. (Known,
pre-existing: NFL desk picks share those family keys with MLB moneylines.)

GUARD. `board.json:picks` is a pricing-guard surface: a bet needs a fresh,
pre-start DraftKings quote. A stale board has no bets and no Alpha picks.

THE SLIP is a per-device list (localStorage), one side per game, singles only,
copyable. No wagering, no parlay pricing.

FIRST NIGHT OF LEANS (11/11): NBA HOU -264 won 115-108, NHL EDM -192 won 3-2
(+0.90u). Two bets; it says nothing about the rule.

HOUSEKEEPING. The old session folder was cleaned up by the app; the working
clone is now `C:\Dev\bpleone-betting` (the localhost preview entry
"edgestat-betting" points there). nav.js changed -> `?v=20261112` on every
page + sw.js (shell cache `edgestat-shell-20261112`).

Tests: 67 pass (board grading, alpha lock, ledger logging + firewall, results).

INDEPENDENT REVIEW OF THE BOARD (same day, a second agent reading the diff
cold; seven defects, all fixed before anything shipped):
 1. PRICE: a board/alpha tag folds onto whichever row logged the wager first,
    and that row keeps its own (earlier) price -- PHX was logged at -244 by the
    02:43 ET run and locked as Alpha at -229. The fold now stamps what the
    board SHOWED on the kept row (board_price, board_grade, board_score,
    alpha_price; first sight on game day wins) and `_board_block` computes
    units from those: the locked price for the Alpha line, the board's game-day
    price otherwise. Verified on the real ledger.
 2. CURATED LEAK: a row logged as a lean could turn curated if the desk later
    made the same side a featured pick (also_sources=pod). `_is_curated_pick`
    now returns False for a row whose source is sport_lean / board_pick /
    board_alpha.
 3. ALPHA LOCK FAILED OPEN: an unreadable lock file read as empty, so the next
    run would re-lock at new prices and overwrite every earlier day. Now: a
    file that exists but does not parse -> provisional list, nothing written;
    writes are atomic (temp file + os.replace).
 4. SLIP: stored prices and "EdgeStat pick" labels were never refreshed. On
    load each entry is re-derived from the live board or dropped; a game with
    no live quote cannot be added.
 5. BOOK: nothing checked the quote's provider. `play_of_day._dk_only` makes a
    non-DraftKings quote not actionable for plays, leans and board bets.
 6. GRADE: results derived a folded row's grade from the desk verdict; the
    stamped board_grade is used first.
 7. EVENING: once every game today had started, today vanished from the day
    chips and the locked Alpha strip with it. Today is always a board day.
Also re-run after the nav change: the 137-page runtime crawl, clean.
Tests: 69 pass.

FIRST LIVE RUN (11/12, after the merge): today's board bets reached the ledger
(6 rows, all grade C; curated unchanged), but WSH @ NJ, locked as Alpha at
-155, was tagged at the then-current -162: the Alpha tag was built from the
current board row, not the locked entry. Fix: the `board_alpha` tag is built
from `board.alpha.picks` (locked status only) and its locked price always
wins on the kept row, which also corrects the 11/12 NJ row on the next run.

ALPHA LOCK TIMING (checked 11/12). The list locks on the first run at or after
11:00 ET (16:00 UTC). GitHub's cron is lossy: the heartbeat is scheduled every
2 hours but ran 3-4 times a day this week, at irregular times. Every day from
11/8 to 11/12 had at least one run between 16:00 and 24:00 UTC, so every
evening slate would have locked, but on some days the lock lands mid-afternoon,
and a Sunday 1:00 PM ET NFL game can start before the first run after 11:00 ET.
Such a game is not in that day's Alpha list (a started game is never a bet),
and a day with no run before the last game starts has no Alpha record at all;
the page then shows the list as provisional. A reliable 11:00 ET trigger needs
the Worker cron (Brandon's call, see the 10-28 entry), not more GitHub crons.
Copy-ready Alpha post: board.json alpha.post, offered only for a locked list.

## 2026-11-12 (evening): risk-adjusted scores; why every lean is a favorite

Brandon: "does it only pick favorites also? Not risk adjusted rewards?"
Measured on the board at the time: all 11 bets (6 today, 5 for Sunday) were
favorites. Two reasons, one by design and one a flaw.

BY DESIGN: a lean is the favorite the model and DraftKings agree on. An
underdog lean would mean betting against both, and the 11/11 study showed every
way of betting the model against DraftKings lost (every underdog this season:
NBA -30%, NHL -16%). At DraftKings' own probability a lean's expected value is
the book's margin (about -4%) and its risk-adjusted value is negative (about
-0.05), so a lean is scored on how strongly model and market agree, not on
reward. Desk picks (A/B) CAN be underdogs (NYJ +440 and CLE +190 earlier this
week); none qualified at this snapshot.

THE FLAW: A/B scores ranked on raw EV, which rewards longshots: NYJ +440 at
17% EV would have outscored BUF -440 at 9% EV, though per unit of risk BUF is
about three times better (EV/sigma 0.24 vs 0.08). Now A/B add
min(15, 15 * (EV/sigma) / 0.30): EV per unit of standard deviation of the
bet's result, at the desk's probability and the DraftKings price (a per-bet
Sharpe ratio). Today's effect: BUF -440 74 -> 77, SF -205 71 -> 69. Changed
before any board bet settled; the locked 11/12 Alpha list is not touched.
Every bet carries `risk` {win_prob, pays, ev_pct, sigma, risk_adj, kelly,
favorite}; cards show "favorite/underdog · win · pays · EV · risk-adj"; the
page sorts by risk-adjusted EV and filters favorites / underdogs.
Same evening: the Play of the Day ranks picks with an edge (tiers 1-3) on the
same risk-adjusted EV (`play_of_day.risk_adj`, one definition shared with
board.risk), raw EV only when it cannot be computed; leans still rank on
agreement. The board's "Graded so far" now follows the sport chip.

## 2026-11-13: lean price cap -300 -> -200 (product call, not a results call)

Brandon: "it just seems like the model is taking the largest favorites as
their play of the game". True by construction: the lean takes the game where
model and DraftKings agree most strongly, which is the heaviest favorite
allowed (11/13 featured OKC -283, pays 0.35u). Five selection rules were
backtested walk-forward on this season (one lean per sport per day, 1u at the
DK close; all only take a side both model and market favour):
                                           NFL      NBA      NHL    median price
  strongest agreement, >= -300 (old)     +1.80u   -2.28u   +3.47u   ~ -220
  strongest agreement, -110..-200 (new)  +5.19u   -1.40u   +0.70u   ~ -180
  closest to even money, >= -300         +5.00u   -5.03u   -0.09u   ~ -165
  model most above market, >= -300       +1.41u   -4.05u   -3.40u   ~ -180
  model most above market, -110..-200    +2.42u   -1.20u   -5.11u   ~ -165
Every rule is expected to return about -4% at DraftKings' no-vig price; the
spread between them is noise on 17-45 game days per sport, and no rule was
chosen for its record. The cap moved to -200 on product grounds: a featured
play should pay at least half a unit, and the expected value is the same.
Consequence: fewer leans (NHL 34 lean days of 45, not 43), and some days a
sport has no play (11/13: no NBA favourite qualified; the only lean is NHL VGK
-162). Locked Alpha lists are never re-priced (11/13 keeps OKC -283 and NYR
-225, locked at 12:51 ET under the old cap). Leans logged before 11/13 stay in
the ledger as logged.

## 2026-11-13: closing line value on every board bet

"Think like a sharp": W-L over a few dozen bets is mostly luck; beating the
closing number converges much faster. `_board_block` now scores every board
bet (and the Alpha line at its locked price) against DraftKings' last
pre-start snapshot in dk_lines_<sport>.json: clv_pts = implied probability of
the close minus implied probability of our price (+ = we got the better
number), and clv_ev = our price's EV at the no-vig close. Counted only after
the start. Caveat: the heartbeat is lossy, so the "close" can be an hour or
more before the start, and often equals the price we logged.
First read (11/12 board, 6 bets): average -0.3 pts, EV at the close -4.5%,
which is what a lean taken at the market price should show. For contrast the
NFL desk's 31 forward-test picks average +1.76 pts (beat the close 52%), EV at
the no-vig close about 0.0%.

## 2026-11-13: line moves + hold on the board; desk picks taken when the edge appears

Every board card shows the opening DraftKings moneyline (first snapshot the
desk recorded), the no-vig move since, and DraftKings' hold. The first read
showed the NFL desk's early-week picks being confirmed by the market (NE @ DET:
the desk took DET +110, now -155; MIA @ IND: IND -135, now -205) -- and that
the board's record could never show it, because board bets were logged on game
day only. Now a desk pick (grade A/B) is logged the first time the board shows
it, at that price, any day; a lean (grade C) still waits for its game day
(it carries no edge and depends on that day's injury news).

ALPHA LOCK TRIGGER (same day). `.github/workflows/alpha-lock-trigger.yml`
asks for one heartbeat at 11:07 ET (summer cron) and 11:09 / 11:47 / 12:29 ET
(winter crons) -- only when the live board.json is not yet locked for today
and no heartbeat is already running (the heartbeat cancels in-progress runs,
so a blind dispatch could kill the run that was about to lock). It does no
work itself. GitHub can skip any of these fires; four chances make an
11:00-12:30 lock likely, not certain. The Worker cron is still the reliable
fix (Brandon's call).

## 2026-11-13: spread prices captured (step one toward a spread desk)

Football is bet mostly against the spread, and the site had only the spread
NUMBER, never its price, so no spread could be priced or backtested (11/11:
"spread prices are not recorded"). ESPN carries DraftKings' point-spread odds
(pointSpread.home/away.close.{line,odds}); espn_odds now keeps
spread_{home,away}_{line,price}, the desk's dk_lines history stores them in
every snapshot, and board cards show both sides with prices. First fetch:
every pre-game NFL (26), NBA (9) and NHL (2) game priced. No spread is graded
or picked yet: a spread desk needs a cover model (margin distribution, key
numbers) and a backtest on the history now accumulating. Also shipped today:
a copy-ready recap of the last fully graded Alpha day that never drops a pick
to fit (dropping one could hide a loss).

SPREAD COVER TEST (same day; tools/cover_study.py). Before any spread desk:
does the desk model predict covers against DraftKings' closing spread NUMBER
better than a coin flip? (Prices were not recorded before today, so this tests
information, not returns.) Model margin = sigma * Phi^-1(p_model), sigma 13.5
NFL / 12 NBA; pushes dropped. Pre-registered: build only if the log-loss gain
over ln 2 has a 90% CI clear of zero.
  NFL n=131: model 0.6855 vs 0.6931 (blend w=0.65: 0.6819); gain +0.0076,
             CI [-0.028, +0.039]; leans >= 4 pts off 50% covered 58-44 (56.9%)
  NBA n=174: model 0.7516, worse than a coin flip; CI entirely below zero
Verdict: NO spread desk. NFL looks like its moneyline (signal, not yet outside
noise); rerun once a few weeks of spread PRICES exist. NBA: do not build.

## 2026-11-13 CORRECTION: the NFL desk's CLV was overstated

Earlier today this file (and the report to Brandon) said the NFL desk's 31
forward-test picks "average +1.76 pts (beat the close 52%)" and called it the
first sharp-style sign of signal. Wrong basis: forward_test averaged OPEN picks
too, and an open pick's "close" is just today's line. Split properly:
  played games (18):  avg -0.02 pts vs the DK close, 90% CI [-1.46, +1.30],
                      8 beat / 2 flat / 8 behind, EV at the no-vig close -2.5%
  open picks (13):    avg +4.24 pts vs the CURRENT line, 8 ahead / 2 behind
So on games that have been played the desk has NOT beaten the close; the
positive number is open picks the market has moved toward since (QB news
included), which can still move back. forward_test now computes the headline
CLV on started games only and reports open picks separately; the desk card says
"played games" and lists open picks on their own line; by-version CLV uses
played games only. Rule for any future CLV number: a close is only a close
after the start.

SECOND INDEPENDENT REVIEW (11/13, everything after 3e210a6c): no severe
defects; four smaller ones, all fixed the same day:
 1. A desk pick taken early as a B and later locked as a C-lean Alpha pick
    showed as "B" in the Alpha results and recap (which then dropped the
    "all were leans" caveat). The locked entry's grade and score now travel
    as alpha_grade / alpha_score and always win, like alpha_price.
 2. A spread line and its price could come from different snapshots (close
    line + open price), and a 0 (pick'em) line was dropped. Both now come from
    one snapshot; 0 is kept. Matters for the spread backtest history.
 3. The published board `definition` still said "game-day price"; it now says
    first listing (desk picks when the edge appears, leans on game day).
 4. Desk picks were matched to board cards by matchup; now by event id (the
    same pairing can meet twice inside the 7-day window).
Also re-run: the 137-page runtime crawl, clean.

## 2026-11-13: does the model predict LINE MOVES? (tools/move_study.py) -> forward test

A model can lose to the close and still be worth betting EARLY if it points at the
side the market will move toward. Walk-forward, this season, first vs last pre-start
DraftKings snapshot; rule: model side at the OPEN price when |model - open no-vig|
>= 4 pts (T fixed before looking):
  NFL 101 bets: CLV +0.66 pts, 90% CI [+0.10, +1.23]; EV at the no-vig close -2.33%
  NBA 125 bets: CLV +1.80 pts, CI [+1.26, +2.36]; line moved our way 71%; EV -0.23%
  NHL 119 bets: CLV +0.67 pts, CI [+0.41, +0.94]; EV at the close -2.93%
All pass the CLV gate, but: (1) the NBA backtest knows who actually PLAYED and the
NFL backtest who actually STARTED at QB -- lines move on exactly that news, so those
two are contaminated by hindsight; NHL (projected goalies) is the clean one. (2) Even
the clean +0.67 pts does not cover the ~4.5% hold: EV at the close is still -2.9%.
Verdict: not a strategy; a forward test. game_lines_desk.move_signals records, the
first time the desk sees a game AT ITS OPENING SNAPSHOT, the model's side and price
when |gap| >= 4 pts (data/move_signals.json, append-only, one record per game; games
first met mid-life are counted as seen with no side), and scores it after the start
against the last pre-start price. Shown on each desk card as "line-move signals
(forward test, not picks)". Never picks, never in the ledger. Revisit at ~100 scored.
Hindsight check on the desk verdicts themselves (same day): the NFL desk backtest
prices each game with the ACTUAL starting QB (nfl_qb_model adj = known-starter edge),
and the NBA one with the players who actually appeared. For the desk VERDICT that is
mostly fair, because it is judged against DraftKings' CLOSE, which also knows the
starter / who sits. It is NOT fair for any claim about betting before that news (the
open, early-week desk picks): that is what the forward tests (desk picks' CLV on
played games, line-move signals) are for.

## 2026-11-13: college football on the board (information only)

Saturday's biggest slate was absent from the board. board.build_college adds every
cfb_model-rated, pre-game NCAAF game that has a DraftKings moneyline (68 of 137 this
week; the rest have no DK moneyline posted or a placeholder that espn_odds drops):
moneylines, total, both sides of the spread with prices, hold, fair prices, the college
model's side and fair spread. Every college game is grade D, "for information only":
cfb_model's own benchmark has DraftKings' close sharper than the model, so no college
game is a bet, none is logged, none can be an Alpha pick (bets come from the major-sport
desks only). It has its own chip and is kept out of "All", so ~55 Saturday games never
bury the major sports. board.json grows to ~16 KB gzipped.
College basketball (same day): board.build_odds_only adds every pre-game NCAAB game with a
DraftKings moneyline under its own chip -- prices, spread, total, hold, fair prices, and NO
side (we have no NCAAB model). Never a bet. The page header counts college separately
("11 games today (+37 college)") so it matches the "All" chip.

## 2026-11-13: college basketball desk v1 -- RESEARCH ONLY

data/game_finals_ncaab.json: 6,988 ESPN Division I finals since 2025-11-03
(tools/build_game_finals_seed.py ncaab; groups=50 + limit=400, since the bare college
scoreboard is a curated subset), grown each desk run from the last 3 days
(_grow_finals_espn). Margin Elo with the NBA multiplier, carry 0.5, K/HFA fitted on
last season (K 37.5, HFA 120; prior log loss 0.565). dk_lines_ncaab.json starts today,
so the backtest has 0 DraftKings-priced games. game_lines_desk.RESEARCH_ONLY = {"ncaab"}:
w forced to 0 and no leans whatever the backtest says; verdict "RESEARCH ONLY". The
board shows its side on every NCAAB card it rates, grade D, for information only; never
a pick, never logged, never Alpha. Promotion to a real desk is Brandon's call once a few
hundred DK-priced games exist. Also: a NEW line history's first snapshot is marked
open_late (every listed game is met mid-life), so it never seeds a fake line-move
signal; only games first seen on later runs are true opens.

CLOSE QUALITY (11/13). Our "close" is the last DraftKings snapshot before the start, and
the runs that take it are lossy. Last 21 days, minutes from that snapshot to the start:
NFL median 69 (44% within 60 min, 98% within 3 h), NBA 32 (65% / 94%), NHL 50 (53% / 93%).
The board's six graded bets (11/12) had a median of 180 min -- that night's runs landed
early. Each CLV row now carries close_min_before; the board states the typical gap next
to its CLV figures. A tighter close needs a reliable pre-start trigger (the Worker cron).
Close capture (same day): `.github/workflows/close-capture.yml` fetches ESPN's DraftKings
odds and extends the four line histories every 20 minutes from 12:05 PM to 11:45 PM ET
(no models, no picks, no ledger; on a commit conflict it skips that snapshot rather than
overwrite a newer run). More fire times give GitHub's lossy scheduler more chances to land
a snapshot just before each start.

THIRD INDEPENDENT REVIEW (11/13, everything after 1fa1eee6): bets/ledger/curated clean;
five defects, all fixed the same day:
 1. The research-only NCAAB desk leaked into pre-game alerts through board_prior (its
    "RESEARCH ONLY" verdict was not blocked; the "model %" shown was DraftKings' no-vig).
    board_prior ignores a RESEARCH desk; pregame_alerts blocks the verdict.
 2+4. A move signal required the desk run itself to take the game's opening snapshot, so
    any game whose open was taken by close-capture, or by a run that failed after
    grow_lines, was lost for good (biasing which games count). Now the signal is priced
    at the OPEN snapshot from the line history, against the model on the first desk run
    after it, within 6 h (MOVE_LATE_H); later than that, or open_late, = seen, no side.
 3. Close-capture pushed on every fire (grow_lines restamps close.at) and the other
    workflows' rebase resolver (`checkout --ours`) then kept close-capture's line history
    over the one their own desk was priced from. Close-capture now commits only when a
    price changed or a game was added; the heartbeat / live-games / daily-pipeline
    resolvers keep their own data/dk_lines_*.json (`checkout --theirs` in a rebase).
 5. Eastern dates were a fixed UTC-4h (summer offset); from November an 11 PM ET start
    was dated the next day. game_lines_desk uses zoneinfo (_et_day).


## 2026-11-13 (afternoon) -- three board tools

1. **Moved since your last visit.** The board remembers, on the viewer's device only
   (localStorage, 7 days), the moneylines it last showed for each game, and flags a game
   whose price has changed since. Nothing is sent anywhere.
2. **Playable to.** Every desk pick carries the worst price it is still a bet at: the
   desk's own fair price (expected value zero at the desk's probability). A lean shows its
   break-even instead, DraftKings' no-vig price, which no book posts; that is the plain
   statement of why a lean is not an edge.
3. **Results by price taken.** The board's record split into -200 or shorter, -199 to
   -101, and even or underdog, at the price the board showed (all_picks_tracker
   `_price_bucket`, `by_price`). First read, 11/12 graded: -200 or shorter 2-0 +0.89u,
   -199 to -101 2-2 -0.80u, no underdog graded yet. Six bets is noise; the split is there
   so the favourites question is answered by the record as it grows, not by opinion.

Note on the 11/13 Alpha: OKC -283 and NYR -225 were locked at 12:51 PM ET under the old
-300 lean cap; the -200 cap landed at 1:35 PM ET. Locked days are never edited, so both
are graded at their locked prices, and each card says that at today's rules it is not a bet.

## 2026-11-13 (late afternoon) -- stale prices on the desk pages; results lag

1. **Desk pages up to 7 hours stale.** nhl.html showed VGK -185 (12:41 UTC snapshot) while
   the board showed -162. data/<sport>_state.json is refreshed by live-games, meant to run
   every 15 minutes; GitHub fired it about three times a day (09:52, 02:28, 21:59 UTC...).
   The heartbeat now runs nfl/nba/nhl_pipeline right after the game-lines desk (~1s each,
   ESPN's free scoreboard only). Verified on CI: all three state files at 20:05:47 UTC with
   the board's prices.
2. **Board results one run stale.** board.py ran before all_picks_tracker.py, so board.json
   carried the previous run's ledger summary. `board.py --results-only` now runs right after
   the tracker in every workflow (verified on CI and on betting.bpleone.com).
3. **Deploys behind the HTTP cache.** The service worker's network-first fetch still honoured
   Pages' max-age=600, so a new page could take 10 minutes to show. Page loads now revalidate
   (`cache: 'no-cache'`, a 304 when unchanged).
4. Also shipped: running CLV on open bets (logged price vs DraftKings now, pre-start), start
   and Alpha-lock countdowns, a CSV of the graded bets, and the by-price split on the track
   record.

## 2026-11-13 (evening) -- fourth review; a correction

An independent review of the afternoon's diff found one medium and five low defects, all fixed
(main 944da0a3). **Correction:** "playable to" was first shipped as the desk's zero-EV price
(BUF -766). The desk only bets at 4% EV or better (game_lines_desk.MIN_EDGE), so a card
saying "playable" between -569 and -766 described a bet the desk itself would refuse. It is
now (1 + MIN_EDGE) / p (BUF -569, ATL +108, SF -212), carried in board.json as desk_min_edge.
Also: an ESPN outage no longer blanks the NBA/NHL desk pages (they keep the previous slate,
flagged by data_health after 3h); running CLV is hidden when the snapshot is > 30 min old; the
Alpha lock countdown ticks; the CSV is labelled as the last 60 bets; sw.js lets the browser
follow redirects on a page load.

## 2026-11-13 (evening) -- night-before openers

DraftKings posts the next day's NHL slate the evening before (all 14 of 11/14's games were on
ESPN's dated board by 3 PM ET on 11/13), and the opener is the softest number of a line's
life. espn_odds now fetches tomorrow's ET date for NBA and NHL into a separate key,
`games_next_day`; the ~20 consumers that read `games` as today's slate never see it. Only
game_lines_desk (`_odds_games`: line history, goalie probables, desk rows) and the board's
event-id lookup read it. Leans for tomorrow show on the board and are logged only on game day;
the Play of the Day and the Alpha are unchanged (today only). Verified on CI (main 21bfc58e):
13 of 11/14's NHL games entered dk_lines_nhl at a 20:17 UTC open, and the first six line-move
signals priced at a true open were recorded (DET +185, NJ -120, BUF +120, SJ +170, NYI -115,
CGY +150). The signals are a forward test, never picks.
