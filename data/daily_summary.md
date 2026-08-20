# EdgeStat Daily Brief - 2026-08-20

**Model Confidence: 18.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-20T13:50:20 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ TEX - WSN_ML**
- Market: +139
- Model probability: 63.0%
- Raw edge: +50.54%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:40p ET | STL @ CIN | Great American Ball Park | 80F 5mph | OVER_9.0 +27.91% |
| 1:10p ET | SFG @ CLE | Progressive Field | 79F 13mph | SFG_ML +49.45% |
| 1:10p ET | TOR @ TBR | Tropicana Field | indoor | OVER_7.0 +35.96% |
| 2:10p ET | OAK @ KCR | Kauffman Stadium | 85F 5mph | OVER_8.0 +39.81% |
| 2:10p ET | ATL @ CHW | Rate Field | 73F 8mph | OVER_8.5 +42.92% |
| 2:10p ET | SEA @ MIL | American Family Field | indoor | MIL_ML +9.6% |
| 6:35p ET | NYY @ BAL | Oriole Park at Camden Yards | 73F 3mph | NYY_ML +8.95% |
| 8:05p ET | WSN @ TEX | Globe Life Field | indoor | WSN_ML +50.54% |
| 8:10p ET | LAA @ HOU | Daikin Park | indoor | HOU_ML +12.44% |

## Parlays - top 5

- **3-leg @ +664 (prob 19.6%, EV +49.88%)**
  - STL @ CIN STL_ML (+100, model 58.7%)
  - NYY @ BAL NYY_ML (+100, model 59.9%)
  - NYY @ BAL UNDER_8.5 (-110, model 55.8%)
- **3-leg @ +629 (prob 20.5%, EV +49.44%)**
  - SFG @ CLE SFG_ML (+100, model 54.9%)
  - SEA @ MIL MIL_ML (-110, model 63.2%)
  - WSN @ TEX OVER_8.5 (-110, model 59.1%)
- **3-leg @ +629 (prob 20.5%, EV +49.41%)**
  - ATL @ CHW CHW_ML (-110, model 54.2%)
  - SEA @ MIL MIL_ML (-110, model 63.2%)
  - NYY @ BAL NYY_ML (+100, model 59.9%)
- **3-leg @ +664 (prob 19.4%, EV +48.52%)**
  - SFG @ CLE SFG_ML (+100, model 54.9%)
  - NYY @ BAL NYY_ML (+100, model 59.9%)
  - WSN @ TEX OVER_8.5 (-110, model 59.1%)
- **3-leg @ +629 (prob 20.2%, EV +47.48%)**
  - STL @ CIN STL_ML (+100, model 58.7%)
  - SFG @ CLE UNDER_8.5 (-110, model 54.6%)
  - SEA @ MIL MIL_ML (-110, model 63.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |

Cumulative graded plays: 9316. Wins: 3458. Hit rate: 37.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHW | 45.7% | +119 | 3.71 | +137 | -137 |
| LAA @ HOU | 35.9% | +178 | 5.12 | -156 | +156 |
| NYY @ BAL | 51.5% | -106 | 3.26 | +264 | -264 |
| OAK @ KCR | 40.0% | +150 | 4.45 | +152 | -152 |
| SEA @ MIL | 40.4% | +147 | 4.53 | +101 | -101 |
| SFG @ CLE | 35.0% | +186 | 4.82 | +214 | -214 |
| STL @ CIN | 38.3% | +161 | 4.96 | +234 | -234 |
| TOR @ TBR | 44.9% | +123 | 4.0 | -233 | +233 |
| WSN @ TEX | 41.6% | +141 | 4.39 | +292 | -292 |

## Team Form (last 10)

**Hot:** SD 7-3 (L1, +18), STL 6-4 (L1, +17), PHI 8-2 (W6, +16), MIL 5-5 (L1, +16), CWS 6-4 (W1, +12)

**Cold:** SEA 4-6 (W1, -28), TEX 3-7 (L1, -20), SF 3-7 (W1, -20), ATH 3-7 (L3, -16), COL 4-6 (L3, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 11.0 IP across 2 games
- TB: 8.4 IP across 2 games
- CWS: 13.5 IP across 2 games
- NYY: 8.6 IP across 2 games
- MIL: 11.0 IP across 2 games
- BOS: 8.2 IP across 2 games
- COL: 9.4 IP across 2 games
- HOU: 9.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.1**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-20._