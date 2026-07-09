# EdgeStat Daily Brief - 2026-07-09

**Model Confidence: 22.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-07-09T16:36:27 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ SFG - OVER_8.5**
- Market: -110
- Model probability: 71.6%
- Raw edge: +36.66%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (12 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | KCR @ NYM | Citi Field | 75F 10mph | KCR_ML +18.56% |
| 1:10p ET | NYY @ TBR | Tropicana Field | indoor | NYY_ML +11.44% |
| 1:35p ET | CHC @ BAL | Oriole Park at Camden Yards | 85F 4mph | CHC_ML +22.89% |
| 1:40p ET | CLE @ MIN | Target Field | 86F 1mph | OVER_8.5 +14.47% |
| 2:10p ET | BOS @ CHW | Rate Field | 83F 6mph | OVER_9.0 +17.13% |
| 6:40p ET | OAK @ DET | Comerica Park | 79F 5mph | OVER_9.0 +4.08% |
| 6:40p ET | SEA @ MIA | loanDepot park | indoor | UNDER_8.0 +21.39% |
| 7:10p ET | PHI @ CIN | Great American Ball Park | 76F 4mph | PHI_ML +20.51% |
| 7:45p ET | MIL @ STL | Busch Stadium | 76F 4mph | MIL_ML +20.98% |
| 8:05p ET | LAA @ TEX | Globe Life Field | indoor | OVER_7.0 +29.44% |
| 9:40p ET | ARI @ SDP | Petco Park | 65F 3mph | UNDER_9.0 +22.05% |
| 9:45p ET | COL @ SFG | Oracle Park | 57F 10mph | OVER_8.5 +36.66% |

## Parlays - top 5

- **2-leg @ +293 (prob 38.1%, EV +49.97%)**
  - CHC @ BAL CHC_ML (+106, model 59.7%)
  - ARI @ SDP UNDER_9.0 (-110, model 63.9%)
- **2-leg @ +293 (prob 37.9%, EV +49.17%)**
  - CHC @ BAL CHC_ML (+106, model 59.7%)
  - SEA @ MIA UNDER_8.0 (-110, model 63.6%)
- **2-leg @ +254 (prob 42.0%, EV +48.66%)**
  - CHC @ BAL CHC_ML (+106, model 59.7%)
  - MIL @ STL MIL_ML (-139, model 70.4%)
- **2-leg @ +264 (prob 40.6%, EV +48.17%)**
  - SEA @ MIA UNDER_8.0 (-110, model 63.6%)
  - ARI @ SDP UNDER_9.0 (-110, model 63.9%)
- **2-leg @ +229 (prob 45.1%, EV +48.07%)**
  - CHC @ BAL CHC_ML (+106, model 59.7%)
  - PHI @ CIN PHI_ML (-168, model 75.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6681. Wins: 2785. Hit rate: 41.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SDP | 36.7% | +172 | 5.09 | +158 | -158 |
| ATL @ PIT | 22.2% | +349 | 7.51 | -- | -- |
| BOS @ CHW | 42.6% | +135 | 4.18 | +145 | -145 |
| CHC @ BAL | 25.4% | +293 | 7.05 | +241 | -241 |
| CLE @ MIN | 28.2% | +254 | 6.27 | +134 | -134 |
| COL @ SFG | 48.5% | +106 | 3.87 | +142 | -142 |
| KCR @ NYM | 42.3% | +137 | 4.53 | +207 | -207 |
| LAA @ TEX | 35.1% | +185 | 5.24 | +196 | -196 |
| MIL @ STL | 55.1% | -123 | 2.9 | +435 | -435 |
| NYY @ TBR | 56.3% | -129 | 2.87 | +172 | -172 |
| OAK @ DET | 24.9% | +302 | 7.0 | +157 | -157 |
| PHI @ CIN | 42.9% | +133 | 4.14 | +530 | -530 |
| SEA @ MIA | 36.9% | +171 | 4.98 | +172 | -172 |

## Team Form (last 10)

**Hot:** DET 7-3 (W4, +19), SEA 5-5 (L2, +18), CHC 8-2 (W3, +18), TB 7-3 (W2, +16), MIA 7-3 (W5, +16)

**Cold:** ATH 1-9 (L5, -33), SD 3-7 (W2, -28), NYY 2-8 (L2, -25), SF 4-6 (L2, -22), NYM 4-6 (W1, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 8.2 IP across 2 games
- STL: 13.5 IP across 3 games
- TEX: 8.0 IP across 2 games
- ATL: 8.2 IP across 2 games
- CWS: 8.3 IP across 2 games
- MIA: 9.0 IP across 2 games
- HOU: 8.4 IP across 2 games
- KC: 9.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-09._