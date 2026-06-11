# EdgeStat Daily Brief - 2026-06-11

**Model Confidence: 72.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-11T22:43:59 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ATL @ CHW - OVER_8.5**
- Market: -110
- Model probability: 84.9%
- Raw edge: +62.17%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (2 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | SEA @ BAL | Oriole Park at Camden Yards | 78F 4mph | SEA_ML +21.41% |
| 7:40p ET | ATL @ CHW | Rate Field | 73F 15mph | OVER_8.5 +62.17% |

## Parlays - top 3

- **3-leg @ +451 (prob 24.9%, EV +36.96%)**
  - LAD @ PIT LAD_ML (-186, model 70.6%)
  - LAD @ PIT UNDER_9.5 (-110, model 54.4%)
  - SEA @ BAL SEA_ML (-114, model 64.7%)
- **2-leg @ +189 (prob 45.7%, EV +31.88%)**
  - LAD @ PIT LAD_ML (-186, model 70.6%)
  - SEA @ BAL SEA_ML (-114, model 64.7%)
- **2-leg @ +258 (prob 35.2%, EV +26.1%)**
  - LAD @ PIT UNDER_9.5 (-110, model 54.4%)
  - SEA @ BAL SEA_ML (-114, model 64.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 1340 | 25.9% | 32.5% | 1.253 | 0.799 |
| batter rbis | 1338 | 20.0% | 23.8% | 1.190 | 0.841 |
| batter runs scored | 669 | 38.0% | 38.9% | 1.023 | 0.978 |
| batter home runs | 669 | 11.5% | 13.2% | 1.142 | 0.878 |
| batter singles | 669 | 41.5% | 44.8% | 1.077 | 0.929 |
| pitcher strikeouts | 289 | 36.0% | 38.9% | 1.081 | 0.927 |
| batter hits | 1385 | 39.3% | 41.9% | 1.068 | 0.936 |
| batter doubles | 669 | 14.1% | 16.0% | 1.140 | 0.879 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHW | 40.1% | +149 | 4.88 | +398 | -398 |
| LAD @ PIT | 34.5% | +190 | 5.33 | -- | -- |
| SEA @ BAL | 40.8% | +145 | 4.6 | +318 | -318 |

## Team Form (last 10)

**Hot:** MIL 6-4 (L2, +29), DET 7-3 (W1, +29), STL 7-3 (L1, +25), LAD 6-4 (L1, +20), MIA 8-2 (W5, +14)

**Cold:** AZ 3-7 (L3, -32), COL 4-6 (L1, -30), CIN 3-7 (L1, -20), MIN 4-6 (L1, -20), CHC 3-7 (W1, -19)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 8.4 IP across 2 games
- STL: 8.5 IP across 3 games
- MIN: 10.5 IP across 3 games
- CWS: 12.1 IP across 2 games
- MIA: 11.5 IP across 3 games
- CHC: 8.6 IP across 3 games
- COL: 12.2 IP across 3 games
- KC: 8.8 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↓ 5 -> **3**
  - _1 market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-10._