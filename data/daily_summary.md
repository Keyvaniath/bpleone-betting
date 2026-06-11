# EdgeStat Daily Brief - 2026-06-11

**Model Confidence: 72.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-11T12:43:13 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ COL - OVER_11.0**
- Market: -110
- Model probability: 78.2%
- Raw edge: +49.36%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | STL @ NYM | Citi Field | 98F 10mph | UNDER_9.0 +47.92% |
| 1:10p ET | MIN @ DET | Comerica Park | 87F 10mph | -- |
| 1:10p ET | ARI @ MIA | loanDepot park | indoor | MIA_ML +33.85% |
| 2:10p ET | TEX @ KCR | Kauffman Stadium | 79F 19mph | UNDER_10.5 +33.81% |
| 3:10p ET | CHC @ COL | Coors Field | 79F 8mph | OVER_11.0 +49.36% |
| 6:40p ET | LAD @ PIT | PNC Park | 76F 4mph | LAD_ML +13.94% |
| 7:05p ET | SEA @ BAL | Oriole Park at Camden Yards | 82F 14mph | OVER_8.5 +25.89% |
| 7:40p ET | ATL @ CHW | Rate Field | 71F 12mph | OVER_8.5 +46.43% |

## Parlays - top 5

- **3-leg @ +491 (prob 25.2%, EV +48.91%)**
  - TEX @ KCR TEX_ML (-103, model 54.5%)
  - LAD @ PIT LAD_ML (-164, model 70.8%)
  - SEA @ BAL SEA_ML (-116, model 65.3%)
- **3-leg @ +484 (prob 24.4%, EV +42.51%)**
  - TEX @ KCR TEX_ML (-103, model 54.5%)
  - LAD @ PIT LAD_ML (-164, model 70.8%)
  - ATL @ CHW ATL_ML (-119, model 63.2%)
- **2-leg @ +243 (prob 41.3%, EV +41.58%)**
  - SEA @ BAL SEA_ML (-116, model 65.3%)
  - ATL @ CHW ATL_ML (-119, model 63.2%)
- **2-leg @ +200 (prob 46.2%, EV +38.58%)**
  - LAD @ PIT LAD_ML (-164, model 70.8%)
  - SEA @ BAL SEA_ML (-116, model 65.3%)
- **2-leg @ +196 (prob 44.8%, EV +32.63%)**
  - LAD @ PIT LAD_ML (-164, model 70.8%)
  - ATL @ CHW ATL_ML (-119, model 63.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter singles | 669 | 41.5% | 44.8% | 1.077 | 0.929 |
| batter rbis | 1338 | 20.0% | 23.8% | 1.190 | 0.841 |
| batter total bases | 1340 | 25.9% | 32.5% | 1.253 | 0.799 |
| batter home runs | 669 | 11.5% | 13.2% | 1.142 | 0.878 |
| pitcher strikeouts | 289 | 36.0% | 38.9% | 1.081 | 0.927 |
| batter doubles | 669 | 14.1% | 16.0% | 1.140 | 0.879 |
| batter hits | 1385 | 39.3% | 41.9% | 1.068 | 0.936 |
| batter runs scored | 669 | 38.0% | 38.9% | 1.023 | 0.978 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ MIA | 38.3% | +161 | 4.8 | -149 | +149 |
| ATL @ CHW | 42.7% | +134 | 4.56 | +283 | -283 |
| CHC @ COL | 23.5% | +325 | 7.21 | +234 | -234 |
| LAD @ PIT | 34.5% | +190 | 5.47 | +422 | -422 |
| MIN @ DET | 35.2% | +184 | 5.38 | +138 | -138 |
| SEA @ BAL | 40.8% | +145 | 4.32 | +319 | -319 |
| STL @ NYM | 64.1% | -179 | 2.28 | +281 | -281 |
| TEX @ KCR | 39.2% | +155 | 4.58 | +205 | -205 |

## Team Form (last 10)

**Hot:** MIL 6-4 (L2, +29), STL 7-3 (W6, +21), LAD 6-4 (L1, +20), BAL 5-5 (W1, +12), DET 6-4 (L1, +12)

**Cold:** AZ 3-7 (L2, -31), CIN 3-7 (L1, -20), CHC 3-7 (L3, -20), COL 5-5 (W2, -19), MIN 4-6 (W1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 8.4 IP across 2 games
- MIN: 8.5 IP across 2 games
- CWS: 12.1 IP across 2 games
- COL: 8.0 IP across 2 games
- KC: 8.8 IP across 2 games
- NYM: 10.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-0.4**

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↓ 5 -> **3**
  - _1 market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-10._