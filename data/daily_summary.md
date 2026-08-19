# EdgeStat Daily Brief - 2026-08-19

**Model Confidence: 18.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-19T21:12:01 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ COL - OVER_11.5**
- Market: -110
- Model probability: 86.7%
- Raw edge: +65.43%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:05p ET | MIA @ PHI | Citizens Bank Park | 78F 4mph | MIA_ML +44.22% |
| 6:35p ET | NYY @ BAL | Oriole Park at Camden Yards | 79F 4mph | OVER_8.0 +30.4% |
| 6:40p ET | SFG @ CLE | Progressive Field | 72F 4mph | SFG_ML +23.94% |
| 6:40p ET | STL @ CIN | Great American Ball Park | 73F 2mph | CIN_ML +10.88% |
| 6:40p ET | TOR @ TBR | Tropicana Field | indoor | TBR_ML +36.99% |
| 7:40p ET | OAK @ KCR | Kauffman Stadium | 73F 3mph | OVER_8.5 +51.99% |
| 7:40p ET | SEA @ MIL | American Family Field | indoor | MIL_ML +23.42% |
| 8:05p ET | WSN @ TEX | Globe Life Field | indoor | OVER_7.5 +53.71% |
| 8:10p ET | LAA @ HOU | Daikin Park | indoor | LAA_ML +6.59% |
| 8:40p ET | LAD @ COL | Coors Field | 77F 7mph | OVER_11.5 +65.43% |

## Parlays - top 5

- **3-leg @ +602 (prob 21.4%, EV +49.98%)**
  - STL @ CIN CIN_ML (-108, model 57.6%)
  - TOR @ TBR OVER_7.5 (-110, model 64.0%)
  - SEA @ MIL UNDER_8.0 (-110, model 58.0%)
- **3-leg @ +1207 (prob 11.2%, EV +46.5%)**
  - SFG @ CLE SFG_ML (+164, model 46.9%)
  - STL @ CIN CIN_ML (-108, model 57.6%)
  - LAA @ HOU LAA_ML (+157, model 41.5%)
- **3-leg @ +1195 (prob 11.3%, EV +46.28%)**
  - SFG @ CLE SFG_ML (+164, model 46.9%)
  - SEA @ MIL UNDER_8.0 (-110, model 58.0%)
  - LAA @ HOU LAA_ML (+157, model 41.5%)
- **3-leg @ +782 (prob 16.6%, EV +45.88%)**
  - STL @ CIN CIN_ML (-108, model 57.6%)
  - SEA @ MIL MIL_ML (-128, model 69.3%)
  - LAA @ HOU LAA_ML (+157, model 41.5%)
- **3-leg @ +774 (prob 16.7%, EV +45.66%)**
  - SEA @ MIL MIL_ML (-128, model 69.3%)
  - SEA @ MIL UNDER_8.0 (-110, model 58.0%)
  - LAA @ HOU LAA_ML (+157, model 41.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |

Cumulative graded plays: 9110. Wins: 3391. Hit rate: 37.2%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAA @ HOU | 54.1% | -118 | 3.07 | +122 | -122 |
| LAD @ COL | 39.6% | +153 | 4.82 | +350 | -350 |
| MIA @ PHI | 50.5% | -102 | 3.49 | +341 | -341 |
| NYY @ BAL | 35.6% | +181 | 5.19 | +227 | -227 |
| OAK @ KCR | 24.2% | +314 | 6.99 | -127 | +127 |
| SEA @ MIL | 54.4% | -119 | 3.04 | -125 | +125 |
| SFG @ CLE | 47.4% | +111 | 3.71 | +157 | -157 |
| STL @ CIN | 41.1% | +143 | 4.42 | +126 | -126 |
| TOR @ TBR | 55.5% | -125 | 2.94 | -364 | +364 |
| WSN @ TEX | 33.6% | +198 | 5.45 | +372 | -372 |

## Team Form (last 10)

**Hot:** STL 7-3 (W2, +21), MIL 6-4 (W3, +19), SD 7-3 (L1, +18), MIA 6-4 (L2, +18), CWS 6-4 (W1, +12)

**Cold:** SEA 3-7 (L1, -31), CIN 4-6 (L2, -21), SF 3-7 (L2, -18), COL 5-5 (L2, -11), TEX 4-6 (W1, -10)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.8 IP across 2 games
- PIT: 11.2 IP across 3 games
- STL: 12.0 IP across 3 games
- TB: 9.6 IP across 2 games
- MIN: 10.6 IP across 3 games
- CWS: 16.9 IP across 3 games
- MIA: 8.5 IP across 2 games
- AZ: 8.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-19._