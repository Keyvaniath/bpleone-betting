# EdgeStat Daily Brief - 2026-07-09

**Model Confidence: 22.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-09T15:56:49 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ SFG - OVER_8.5**
- Market: -110
- Model probability: 71.6%
- Raw edge: +36.66%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (13 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | ATL @ PIT | PNC Park | 84F 7mph | PIT_ML +6.27% |
| 1:10p ET | KCR @ NYM | Citi Field | 75F 11mph | KCR_ML +16.42% |
| 1:10p ET | NYY @ TBR | Tropicana Field | indoor | NYY_ML +11.93% |
| 1:35p ET | CHC @ BAL | Oriole Park at Camden Yards | 85F 4mph | CHC_ML +24.08% |
| 1:40p ET | CLE @ MIN | Target Field | 86F 6mph | OVER_8.5 +23.09% |
| 2:10p ET | BOS @ CHW | Rate Field | 83F 6mph | OVER_9.0 +17.13% |
| 6:40p ET | OAK @ DET | Comerica Park | 79F 6mph | OVER_9.0 +5.84% |
| 6:40p ET | SEA @ MIA | loanDepot park | indoor | UNDER_8.0 +21.39% |
| 7:10p ET | PHI @ CIN | Great American Ball Park | 76F 2mph | PHI_ML +20.23% |
| 7:45p ET | MIL @ STL | Busch Stadium | 76F 6mph | MIL_ML +22.35% |
| 8:05p ET | LAA @ TEX | Globe Life Field | indoor | OVER_7.0 +29.44% |
| 9:40p ET | ARI @ SDP | Petco Park | 65F 2mph | UNDER_9.0 +23.66% |
| 9:45p ET | COL @ SFG | Oracle Park | 57F 10mph | OVER_8.5 +36.66% |

## Parlays - top 5

- **2-leg @ +207 (prob 48.8%, EV +49.68%)**
  - PHI @ CIN PHI_ML (-165, model 75.4%)
  - ARI @ SDP UNDER_9.0 (-110, model 64.8%)
- **2-leg @ +264 (prob 41.0%, EV +49.44%)**
  - CLE @ MIN OVER_8.5 (-110, model 64.5%)
  - SEA @ MIA UNDER_8.0 (-110, model 63.6%)
- **2-leg @ +207 (prob 48.6%, EV +49.01%)**
  - CLE @ MIN OVER_8.5 (-110, model 64.5%)
  - PHI @ CIN PHI_ML (-165, model 75.4%)
- **2-leg @ +231 (prob 44.8%, EV +48.54%)**
  - SEA @ MIA UNDER_8.0 (-110, model 63.6%)
  - MIL @ STL MIL_ML (-136, model 70.5%)
- **2-leg @ +179 (prob 53.1%, EV +48.11%)**
  - PHI @ CIN PHI_ML (-165, model 75.4%)
  - MIL @ STL MIL_ML (-136, model 70.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6681. Wins: 2785. Hit rate: 41.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SDP | 36.7% | +172 | 5.07 | +159 | -159 |
| ATL @ PIT | 22.2% | +349 | 7.84 | +138 | -138 |
| BOS @ CHW | 42.6% | +135 | 4.17 | +145 | -145 |
| CHC @ BAL | 25.4% | +293 | 7.01 | +241 | -241 |
| CLE @ MIN | 28.2% | +254 | 6.14 | +132 | -132 |
| COL @ SFG | 48.5% | +106 | 3.87 | +142 | -142 |
| KCR @ NYM | 42.3% | +137 | 4.55 | +207 | -207 |
| LAA @ TEX | 35.1% | +185 | 5.24 | +196 | -196 |
| MIL @ STL | 55.1% | -123 | 2.95 | +436 | -436 |
| NYY @ TBR | 56.3% | -129 | 2.87 | +172 | -172 |
| OAK @ DET | 24.9% | +302 | 6.93 | +156 | -156 |
| PHI @ CIN | 42.9% | +133 | 4.17 | +527 | -527 |
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