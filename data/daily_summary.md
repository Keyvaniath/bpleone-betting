# EdgeStat Daily Brief - 2026-07-25

**Model Confidence: 23.2/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-25T23:02:57 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ MIL - OVER_9.0**
- Market: -110
- Model probability: 83.9%
- Raw edge: +60.21%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | ATL @ BAL | Oriole Park at Camden Yards | 70F 4mph | OVER_9.0 +13.92% |
| 7:10p ET | OAK @ MIN | Target Field | 77F 4mph | OAK_ML +33.75% |
| 7:10p ET | HOU @ CHW | Rate Field | 71F 6mph | OVER_8.5 +39.24% |
| 7:10p ET | COL @ MIL | American Family Field | indoor | OVER_9.0 +60.21% |
| 7:15p ET | LAD @ NYM | Citi Field | 67F 3mph | LAD_ML +18.46% |
| 7:15p ET | CIN @ STL | Busch Stadium | 81F 4mph | OVER_7.5 +11.95% |
| 7:15p ET | SEA @ TEX | Globe Life Field | indoor | OVER_7.0 +21.99% |

## Parlays - top 5

- **3-leg @ +497 (prob 24.4%, EV +45.77%)**
  - NYY @ PHI UNDER_9.0 (-110, model 57.2%)
  - ATL @ BAL OVER_9.0 (-110, model 58.6%)
  - LAD @ NYM LAD_ML (-157, model 72.8%)
- **3-leg @ +497 (prob 24.4%, EV +45.42%)**
  - ATL @ BAL OVER_9.0 (-110, model 58.6%)
  - LAD @ NYM LAD_ML (-157, model 72.8%)
  - SEA @ TEX OVER_7.5 (-110, model 57.1%)
- **3-leg @ +558 (prob 21.9%, EV +43.95%)**
  - NYY @ PHI UNDER_9.0 (-110, model 57.2%)
  - ATL @ BAL OVER_9.0 (-110, model 58.6%)
  - HOU @ CHW CHW_ML (-124, model 65.2%)
- **3-leg @ +558 (prob 21.8%, EV +43.59%)**
  - ATL @ BAL OVER_9.0 (-110, model 58.6%)
  - HOU @ CHW CHW_ML (-124, model 65.2%)
  - SEA @ TEX OVER_7.5 (-110, model 57.1%)
- **3-leg @ +497 (prob 23.9%, EV +42.74%)**
  - ATL @ BAL OVER_9.0 (-110, model 58.6%)
  - LAD @ NYM LAD_ML (-157, model 72.8%)
  - CIN @ STL UNDER_8.0 (-110, model 56.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6542. Wins: 2687. Hit rate: 41.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ BAL | 35.1% | +185 | 5.13 | +185 | -185 |
| CIN @ STL | 30.5% | +228 | 5.8 | +209 | -209 |
| COL @ MIL | 31.3% | +220 | 5.81 | -144 | +144 |
| HOU @ CHW | 38.2% | +162 | 4.99 | -115 | +115 |
| LAD @ NYM | 58.9% | -143 | 2.66 | +501 | -501 |
| OAK @ MIN | 40.9% | +145 | 4.44 | +233 | -233 |
| SEA @ TEX | 34.7% | +188 | 5.29 | +183 | -183 |

## Team Form (last 10)

**Hot:** CWS 7-3 (L1, +27), BOS 9-1 (W2, +25), AZ 8-2 (W4, +24), BAL 7-3 (L2, +18), PIT 6-4 (L1, +17)

**Cold:** ATH 3-7 (W1, -36), TOR 2-8 (L1, -30), MIA 0-10 (L10, -22), KC 6-4 (W1, -15), TEX 5-5 (W1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 11.8 IP across 2 games
- TB: 10.0 IP across 2 games
- MIN: 8.0 IP across 2 games
- HOU: 8.0 IP across 1 games
- KC: 12.0 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-24._