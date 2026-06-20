# EdgeStat Daily Brief - 2026-06-20

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-20T23:09:30 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PIT @ COL - OVER_10.5**
- Market: -110
- Model probability: 82.3%
- Raw edge: +57.15%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | CLE @ HOU | Daikin Park | indoor | HOU_ML +14.26% |
| 7:15p ET | NYM @ PHI | Citizens Bank Park | 71F 7mph | UNDER_7.5 +17.31% |
| 9:10p ET | PIT @ COL | Coors Field | 67F 12mph | OVER_10.5 +57.15% |
| 10:05p ET | LAA @ OAK | Sutter Health Park | 63F 7mph | OVER_9.5 +32.59% |
| 10:10p ET | BAL @ LAD | UNIQLO Field at Dodger Stadium | 59F 3mph | OVER_8.0 +35.06% |
| 10:10p ET | BOS @ SEA | T-Mobile Park | indoor | SEA_ML +12.62% |
| 10:10p ET | MIN @ ARI | Chase Field | indoor | MIN_ML +24.33% |

## Parlays - top 5

- **3-leg @ +317 (prob 35.8%, EV +49.3%)**
  - NYM @ PHI UNDER_7.5 (-110, model 61.9%)
  - NYM @ PHI PHI_ML (-195, model 68.2%)
  - PIT @ COL PIT_ML (-225, model 84.9%)
- **3-leg @ +554 (prob 22.8%, EV +48.76%)**
  - NYM @ PHI UNDER_7.5 (-110, model 61.9%)
  - BOS @ SEA SEA_ML (-126, model 63.2%)
  - MIN @ ARI OVER_9.0 (-110, model 58.2%)
- **3-leg @ +210 (prob 47.9%, EV +48.29%)**
  - NYM @ PHI PHI_ML (-195, model 68.2%)
  - PIT @ COL PIT_ML (-225, model 84.9%)
  - BAL @ LAD LAD_ML (-240, model 82.8%)
- **3-leg @ +385 (prob 30.5%, EV +47.76%)**
  - BAL @ LAD LAD_ML (-240, model 82.8%)
  - BOS @ SEA SEA_ML (-126, model 63.2%)
  - MIN @ ARI OVER_9.0 (-110, model 58.2%)
- **3-leg @ +260 (prob 40.6%, EV +46.23%)**
  - CLE @ HOU HOU_ML (-154, model 70.1%)
  - NYM @ PHI PHI_ML (-195, model 68.2%)
  - PIT @ COL PIT_ML (-225, model 84.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ LAD | 53.7% | -116 | 3.09 | -277 | +277 |
| BOS @ SEA | 32.9% | +204 | 5.56 | +105 | -105 |
| CLE @ HOU | 28.7% | +248 | 6.24 | -136 | +136 |
| LAA @ OAK | 50.3% | -101 | 3.55 | -101 | +101 |
| MIN @ ARI | 24.7% | +304 | 6.99 | +270 | -270 |
| NYM @ PHI | 44.9% | +123 | 4.06 | -116 | +116 |
| PIT @ COL | 31.8% | +214 | 5.26 | +926 | -926 |

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +22), DET 5-5 (W2, +18), NYY 7-3 (L1, +17), MIA 7-3 (W2, +16), LAD 7-3 (W4, +12)

**Cold:** CLE 3-7 (L1, -24), TEX 4-6 (W1, -24), ATL 3-7 (W1, -19), PIT 4-6 (L1, -17), SEA 4-6 (L1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.1 IP across 2 games
- STL: 8.4 IP across 2 games
- TOR: 10.9 IP across 3 games
- CWS: 17.6 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-19._