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
