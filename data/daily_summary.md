# EdgeStat Daily Brief - 2026-07-10

**Model Confidence: 22.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-10T23:04:19 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ CIN - OVER_9.5**
- Market: -110
- Model probability: 88.6%
- Raw edge: +69.21%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (11 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | KCR @ BAL | Oriole Park at Camden Yards | 75F 4mph | -- |
| 7:10p ET | CHC @ CIN | Great American Ball Park | 77F 3mph | OVER_9.5 +69.21% |
| 7:10p ET | SEA @ TBR | Tropicana Field | indoor | UNDER_8.5 +34.51% |
| 7:10p ET | CLE @ MIA | loanDepot park | indoor | MIA_ML +10.74% |
| 7:40p ET | OAK @ CHW | Rate Field | 70F 10mph | OVER_8.5 +67.48% |
| 8:05p ET | HOU @ TEX | Globe Life Field | indoor | OVER_8.5 +24.73% |
| 8:10p ET | LAA @ MIN | Target Field | 75F 2mph | OVER_9.5 +34.92% |
| 8:15p ET | ATL @ STL | Busch Stadium | 75F 10mph | ATL_ML +12.29% |
| 9:40p ET | TOR @ SDP | Petco Park | 64F 4mph | OVER_8.5 +26.21% |
| 10:10p ET | ARI @ LAD | UNIQLO Field at Dodger Stadium | 64F 3mph | LAD_ML +20.51% |
| 10:15p ET | COL @ SFG | Oracle Park | 55F 12mph | OVER_8.5 +50.8% |

## Parlays - top 5

- **2-leg @ +250 (prob 42.7%, EV +49.44%)**
  - PHI @ DET DET_ML (-120, model 65.8%)
  - TOR @ SDP OVER_8.5 (-110, model 64.9%)
- **2-leg @ +207 (prob 48.7%, EV +49.19%)**
  - NYY @ WSN UNDER_10.0 (-110, model 62.7%)
  - OAK @ CHW CHW_ML (-165, model 77.5%)
- **2-leg @ +121 (prob 67.3%, EV +48.83%)**
  - OAK @ CHW CHW_ML (-165, model 77.5%)
  - ARI @ LAD LAD_ML (-265, model 86.8%)
- **2-leg @ +264 (prob 40.8%, EV +48.52%)**
  - NYY @ WSN UNDER_10.0 (-110, model 62.7%)
  - TOR @ SDP OVER_8.5 (-110, model 64.9%)
- **2-leg @ +163 (prob 56.4%, EV +48.17%)**
  - TOR @ SDP OVER_8.5 (-110, model 64.9%)
  - ARI @ LAD LAD_ML (-265, model 86.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6741. Wins: 2813. Hit rate: 41.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ LAD | 31.7% | +215 | 5.81 | -259 | +259 |
| ATL @ STL | 63.8% | -177 | 2.19 | +393 | -393 |
| CHC @ CIN | 34.2% | +192 | 16.52 | +729 | -729 |
| CLE @ MIA | 49.6% | +102 | 3.51 | +111 | -111 |
| COL @ SFG | 34.7% | +188 | 5.7 | +137 | -137 |
| HOU @ TEX | 42.9% | +133 | 4.24 | +148 | -148 |
| KCR @ BAL | 38.7% | +158 | 4.62 | +113 | -113 |
| LAA @ MIN | 28.6% | +249 | 6.34 | +104 | -104 |
| OAK @ CHW | 31.2% | +220 | 5.46 | -220 | +220 |
| SEA @ TBR | 48.6% | +106 | 3.61 | +123 | -123 |
| TOR @ SDP | 23.8% | +320 | 7.32 | +101 | -101 |

## Team Form (last 10)

**Hot:** DET 8-2 (W5, +24), MIA 8-2 (W6, +21), SEA 5-5 (L3, +15), MIN 7-3 (L1, +14), BOS 8-2 (W6, +14)

**Cold:** ATH 1-9 (L6, -33), SD 3-7 (L1, -29), SF 4-6 (W1, -17), NYY 3-7 (W1, -16), LAA 2-8 (L1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.4 IP across 2 games
- PIT: 8.3 IP across 2 games
- TB: 8.4 IP across 2 games
- ATL: 8.3 IP across 2 games
- CWS: 8.2 IP across 2 games
- LAA: 9.1 IP across 2 games
- KC: 8.7 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-10._