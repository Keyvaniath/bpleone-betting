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
2. Remaining -110 assumptions in secondary boards: `mlb_model.py:184-185`
   (unposted totals juice), `book_vs_model_team.py:198` (totals -110/-110 --
   now re-priced before the Alpha uses it, but the board itself still shows
   it), `slate_roi_projector.py`, `sharpe_ranking.py`.
3. (merged c413a65fd9) per-record `price_provenance`.
   NFL feed (branch `integrity/nfl-feed`): `espn_odds.fetch_sport` also
   requests the NEXT week for NFL / NCAAF (`week=N+1&seasontype=T` from the
   bare board, postseason week 1 after the regular season), merged by event
   id. 11/3: the bare board held 14 Week-9 finals and 0 upcoming games; with
   the fix 15 upcoming NFL games carry DraftKings lines -> desk board 15 rows,
   4 picks, 4 games held as QB-uncertain. Remaining follow-up: `ml_reprice` pending_priced reads
   `by_matchup`, which is not status-filtered (could stamp an in-play price).
4. Alpha record (locked days) is 70 props at the model's own price (+13.36u) +
   35 DK game lines (-0.78u): counting rule is Brandon's call.
5. `param_recommender` auto-applied thresholds tuned on 0.909-payout units --
   scope of affected parameters not yet traced.

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

Still open after this pass: golf_round_score_props + the other tennis prop
modules (assumed -120 STRONG rule); *_pot_history settle projections at fair
odds; validate_curation_oos / self_train / odds_key_preflight / clv_by_source
producer wording; dow_pl includes MLB-PP; sport_coverage IN-SEASON keyed on a
props refresh; nba_player_pra_props `_abbr`; docs/ is publicly served.
