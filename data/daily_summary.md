# EdgeStat Daily Brief - 2026-07-04

**Model Confidence: 7.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-04T21:52:36 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**SFG @ COL - OVER_12.0**
- Market: -110
- Model probability: 88.0%
- Raw edge: +68.04%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (11 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | BAL @ CIN | Great American Ball Park | 80F 3mph | OVER_9.0 +22.08% |
| 7:10p ET | TBR @ HOU | Daikin Park | indoor | OVER_7.0 +25.37% |
| 7:10p ET | CHW @ CLE | Progressive Field | 76F 2mph | CHW_ML +24.7% |
| 8:08p ET | STL @ CHC | Wrigley Field | 68F 6mph | OVER_8.0 +51.88% |
| 8:08p ET | NYM @ ATL | Truist Park | 79F 1mph | UNDER_8.0 +30.47% |
| 8:10p ET | SFG @ COL | Coors Field | 76F 5mph | OVER_12.0 +68.04% |
| 8:10p ET | PHI @ KCR | Kauffman Stadium | 69F 2mph | UNDER_9.0 +30.17% |
| 9:38p ET | BOS @ LAA | Angel Stadium | 69F 4mph | -- |
| 9:40p ET | MIA @ OAK | Sutter Health Park | 70F 10mph | OVER_11.0 +20.74% |
| 9:40p ET | MIL @ ARI | Chase Field | indoor | MIL_ML +38.98% |
| 10:10p ET | SDP @ LAD | UNIQLO Field at Dodger Stadium | 63F 3mph | LAD_ML +18.51% |

## Parlays - top 5

- **3-leg @ +529 (prob 23.8%, EV +49.95%)**
  - BAL @ CIN BAL_ML (+108, model 58.4%)
  - SFG @ COL SFG_ML (-132, model 62.7%)
  - MIA @ OAK MIA_ML (-139, model 65.1%)
- **2-leg @ +310 (prob 36.5%, EV +49.84%)**
  - BAL @ CIN BAL_ML (+108, model 58.4%)
  - TBR @ HOU TBR_ML (-103, model 62.6%)
- **3-leg @ +728 (prob 18.1%, EV +49.67%)**
  - TBR @ HOU TBR_ML (-103, model 62.6%)
  - STL @ CHC STL_ML (+139, model 46.0%)
  - SFG @ COL SFG_ML (-132, model 62.7%)
- **3-leg @ +755 (prob 17.5%, EV +49.47%)**
  - BAL @ CIN BAL_ML (+108, model 58.4%)
  - STL @ CHC STL_ML (+139, model 46.0%)
  - MIA @ OAK MIA_ML (-139, model 65.1%)
- **3-leg @ +702 (prob 18.5%, EV +48.01%)**
  - BAL @ CIN OVER_9.0 (-110, model 63.9%)
  - STL @ CHC STL_ML (+139, model 46.0%)
  - SFG @ COL SFG_ML (-132, model 62.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ CIN | 40.0% | +150 | 4.68 | +233 | -233 |
| BOS @ LAA | 35.4% | +183 | 5.32 | +281 | -281 |
| CHW @ CLE | 51.5% | -106 | 3.35 | +243 | -243 |
| MIA @ OAK | 27.5% | +264 | 6.85 | +308 | -308 |
| MIL @ ARI | 36.9% | +171 | 4.98 | +1102 | -1102 |
| NYM @ ATL | 47.6% | +110 | 3.75 | -156 | +156 |
| PHI @ KCR | 55.5% | -125 | 2.99 | +266 | -266 |
| SDP @ LAD | 39.2% | +155 | 4.73 | -326 | +326 |
| SFG @ COL | 22.0% | +355 | 7.7 | +239 | -239 |
| STL @ CHC | 46.3% | +116 | 3.7 | +139 | -139 |
| TBR @ HOU | 63.3% | -173 | 2.28 | +297 | -297 |

## Team Form (last 10)

**Hot:** TB 9-1 (W9, +32), LAD 8-2 (W2, +29), CWS 5-5 (L3, +26), CHC 8-2 (L1, +23), MIA 7-3 (W1, +19)

**Cold:** KC 3-7 (L3, -39), SD 3-7 (L7, -33), NYY 2-8 (L1, -28), NYM 2-8 (L2, -17), LAA 4-6 (L4, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.4 IP across 3 games
- STL: 10.5 IP across 2 games
- CWS: 8.6 IP across 2 games
- MIA: 9.5 IP across 2 games
- NYY: 8.4 IP across 2 games
- MIL: 11.4 IP across 2 games
- CLE: 8.4 IP across 2 games
- LAD: 8.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-03._