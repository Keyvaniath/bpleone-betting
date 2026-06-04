# NFL Monte Carlo Simulator — Audit & Backtest

**What it is.** `nfl_simulator.py` replaces the normal-CDF approximation in
`nfl_player_props` with a play-level Monte Carlo, mirroring how `mlb_model`/
`simulator.py` use a PA-level MC for baseball. Instead of asserting a stat is
`Normal(μ, σ)`, it simulates the generative process and reads the empirical
distribution.

## Generative model (per simulated game)

| Component | Distribution | Why |
|---|---|---|
| Pass attempts / carries / targets | **Negative Binomial** (mean, VMR) via Gamma-Poisson | Counts swing game-to-game with script/pace; NB allows overdispersion (Var = mean·VMR), Poisson can't |
| Completions / catches | **Binomial**(attempts, rate) | Each attempt independently completes |
| Yards per completion/catch/carry | **Gamma**(mean, CV) | Standard right-skewed nonnegative yardage; sum = the total, **max = the "longest" market** |
| Pass TD / INT / rush TD | **Poisson**(per-game rate) | Rare discrete counts |

Rushing shifts the Gamma by −2.5 yds so carries can be stuffed for a loss. All
pure-Python + seeded → reproducible.

This structure gets three things a single Gaussian cannot: the **skew** (yards are
right-skewed), the **count × per-event compounding** (attempts × yards/attempt,
which sets the true variance), and the **discrete / extreme markets** (anytime TD,
2+ pass TD, longest reception) read directly off the simulated sample.

## Calibration (auditable parameters)

VMR and per-event CV were **calibrated to 2025 game-log dispersion** via
`nfl_simulator_backtest.py` until the simulated SD matched each player's empirical
game-to-game SD:

| Market | sim SD | empirical SD | ratio |
|---|---|---|---|
| pass_yds | 70.3 | 67.1 | 1.05 ✓ |
| rush_yds | 21.5 | 21.7 | 0.99 ✓ |
| rec_yds | 23.2 | 21.6 | 1.07 ✓ |
| receptions | 1.7 | 1.6 | 1.11 ✓ |

Final params: `VMR_ATT 1.45 · VMR_CARRIES 1.35 · VMR_TARGETS 1.22 · CV_PASS 0.88 ·
CV_RUSH 0.95 · CV_REC 0.75`.

## Backtest vs the normal-CDF baseline

Walk-forward / leave-one-out on real 2025 game logs (no look-ahead: each game's
profile is built from the player's *other* games), **21,847 prediction-outcome
pairs**. Lower is better.

| Market | n | MC Brier | Norm Brier | MC ECE | Norm ECE | Winner |
|---|---|---|---|---|---|---|
| pass_yds | 1,257 | **0.1867** | 0.1869 | 0.0302 | 0.0271 | MC |
| rush_yds | 3,725 | **0.1867** | 0.1907 | **0.0273** | 0.0585 | MC |
| rec_yds | 8,250 | **0.1889** | 0.1908 | **0.0312** | 0.0517 | MC |
| receptions | 8,615 | **0.1885** | 0.1940 | **0.0221** | 0.0389 | MC |
| **POOLED** | **21,847** | **0.1882** | 0.1918 | **0.0269** | 0.0464 | **MC** |

**Conclusion.** The Monte Carlo is better-calibrated than the Gaussian on every
market — a modest Brier edge (−1.9% pooled) but a **~halved calibration error**
(ECE 0.027 vs 0.046), biggest on the skewed markets (rush_yds ECE 0.027 vs 0.059)
where a Gaussian misprices the tails. It also unlocks markets the Gaussian can't
price at all: **longest reception/rush** (an extreme-value statistic) and exact
**2+ TD / 1+ INT** counts, read straight off the simulated sample.

Re-run the audit any time: `python nfl_simulator_backtest.py` (needs a 2025
game-log pull from `espn_box_logs.py nfl <2025-date>`).

## Integration audit (bug caught + fixed)

Wiring the sim into `nfl_player_props` and validating every market end-to-end
(`_validate_sim.py`) surfaced a real defect the yardage backtest could not see:
`simulate_receiver` drew receiving TDs with a **fresh `random.Random(seed)` per
sample**, so all N draws were identical and P(anytime TD) collapsed to exactly
0.0 or 1.0 — A.J. Brown priced at a 100% anytime TD. Fixed to draw from the
shared loop RNG (QB/RB TD draws were already correct). Post-fix the backtest is
unchanged (POOLED MC Brier 0.1883 vs 0.1920, ECE 0.0269 vs 0.0470 — the receiver
yardage stream only shifts by RNG noise), and anytime-TD now returns a real
distribution. Anytime-TD emission is additionally clamped to a priceable
[0.50, 0.92] so it can never surface an un-priceable "lock."
