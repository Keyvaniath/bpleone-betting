# EdgeStat Daily Brief - 2026-08-20

**Model Confidence: 18.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-20T05:18:16 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ TEX - WSN_ML**
- Market: +137
- Model probability: 63.0%
- Raw edge: +49.28%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:40p ET | STL @ CIN | Great American Ball Park | 81F 5mph | OVER_9.0 +28.64% |
| 1:10p ET | SFG @ CLE | Progressive Field | 77F 6mph | SFG_ML +40.28% |
| 1:10p ET | TOR @ TBR | Tropicana Field | indoor | TBR_ML +26.82% |
| 2:10p ET | OAK @ KCR | Kauffman Stadium | 85F 5mph | OVER_8.5 +29.25% |
| 2:10p ET | ATL @ CHW | Rate Field | 74F 8mph | OVER_8.5 +43.59% |
| 2:10p ET | SEA @ MIL | American Family Field | indoor | MIL_ML +11.38% |
| 6:35p ET | NYY @ BAL | Oriole Park at Camden Yards | 71F 7mph | OVER_8.0 +10.13% |
| 8:05p ET | WSN @ TEX | Globe Life Field | indoor | WSN_ML +49.28% |
| 8:10p ET | LAA @ HOU | Daikin Park | indoor | HOU_ML +11.19% |

## Parlays - top 5

- **3-leg @ +504 (prob 24.8%, EV +49.51%)**
  - TOR @ TBR OVER_7.5 (-110, model 65.1%)
  - SEA @ MIL MIL_ML (-131, model 63.2%)
  - NYY @ BAL NYY_ML (-126, model 60.2%)
- **3-leg @ +520 (prob 24.1%, EV +49.45%)**
  - STL @ CIN STL_ML (-119, model 58.7%)
  - TOR @ TBR OVER_7.5 (-110, model 65.1%)
  - SEA @ MIL MIL_ML (-131, model 63.2%)
- **3-leg @ +423 (prob 28.6%, EV +49.27%)**
  - TOR @ TBR OVER_7.5 (-110, model 65.1%)
  - NYY @ BAL NYY_ML (-126, model 60.2%)
  - LAA @ HOU HOU_ML (-190, model 72.9%)
- **3-leg @ +436 (prob 27.8%, EV +49.21%)**
  - STL @ CIN STL_ML (-119, model 58.7%)
  - TOR @ TBR OVER_7.5 (-110, model 65.1%)
  - LAA @ HOU HOU_ML (-190, model 72.9%)
- **3-leg @ +543 (prob 23.1%, EV +48.46%)**
  - TOR @ TBR OVER_7.5 (-110, model 65.1%)
  - SEA @ MIL MIL_ML (-131, model 63.2%)
  - LAA @ HOU OVER_8.5 (-110, model 56.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |

Cumulative graded plays: 9166. Wins: 3418. Hit rate: 37.3%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHW | 45.7% | +119 | 3.72 | +137 | -137 |
| LAA @ HOU | 35.9% | +178 | 5.12 | -156 | +156 |
| NYY @ BAL | 51.5% | -106 | 3.18 | +263 | -263 |
| OAK @ KCR | 40.0% | +150 | 4.45 | +152 | -152 |
| SEA @ MIL | 40.4% | +147 | 4.53 | +101 | -101 |
| SFG @ CLE | 35.0% | +186 | 5.32 | +216 | -216 |
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

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-20._