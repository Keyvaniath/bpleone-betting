# EdgeStat Daily Brief - 2026-08-20

**Model Confidence: 18.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-20T22:33:28 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ TEX - WSN_ML**
- Market: +156
- Model probability: 63.0%
- Raw edge: +61.25%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (2 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:05p ET | WSN @ TEX | Globe Life Field | indoor | WSN_ML +61.25% |
| 8:10p ET | LAA @ HOU | Daikin Park | indoor | OVER_8.0 +19.63% |

## Parlays - top 5

- **2-leg @ +264 (prob 39.6%, EV +44.42%)**
  - NYY @ BAL OVER_7.5 (-110, model 63.2%)
  - LAA @ HOU OVER_8.0 (-110, model 62.7%)
- **2-leg @ +263 (prob 37.7%, EV +36.8%)**
  - NYY @ BAL NYY_ML (-111, model 60.2%)
  - LAA @ HOU OVER_8.0 (-110, model 62.7%)
- **2-leg @ +188 (prob 46.1%, EV +32.6%)**
  - NYY @ BAL OVER_7.5 (-110, model 63.2%)
  - LAA @ HOU HOU_ML (-197, model 72.9%)
- **2-leg @ +187 (prob 43.8%, EV +25.6%)**
  - NYY @ BAL NYY_ML (-111, model 60.2%)
  - LAA @ HOU HOU_ML (-197, model 72.9%)
- **2-leg (SGP) @ +263 (prob 33.1%, EV +19.92%)**
  - NYY @ BAL OVER_7.5 (-110, model 63.2%)
  - NYY @ BAL NYY_ML (-111, model 60.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |

Cumulative graded plays: 9318. Wins: 3460. Hit rate: 37.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAA @ HOU | 35.9% | +178 | 5.12 | -156 | +156 |
| WSN @ TEX | 41.6% | +141 | 4.39 | +292 | -292 |

## Team Form (last 10)

**Hot:** STL 7-3 (W1, +19), SD 7-3 (L1, +18), MIL 5-5 (W1, +18), PHI 8-2 (W6, +16), BOS 4-6 (L1, +11)

**Cold:** SEA 4-6 (L1, -30), TEX 3-7 (L1, -20), CIN 4-6 (L1, -16), ATH 3-7 (L3, -16), COL 4-6 (L3, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SEA: 9.2 IP across 3 games
- SF: 13.2 IP across 3 games
- STL: 8.5 IP across 3 games
- TB: 12.4 IP across 3 games
- TOR: 8.4 IP across 3 games
- CWS: 15.8 IP across 3 games
- NYY: 8.6 IP across 2 games
- MIL: 16.1 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-20._