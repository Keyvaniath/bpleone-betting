# EdgeStat Daily Brief - 2026-06-13

**Model Confidence: 68.5/100 [YELLOW]** -- Still learning. Small flat plays only; treat anything >+10% edge as suspect.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-13T23:03:48 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ OAK - UNDER_14.5**
- Market: -110
- Model probability: 80.3%
- Raw edge: +53.25%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | HOU @ KCR | Kauffman Stadium | 76F 5mph | KCR_ML +6.66% |
| 7:10p ET | PHI @ MIL | American Family Field | indoor | MIL_ML +25.33% |
| 10:05p ET | COL @ OAK | Las Vegas Ballpark | 70F 0mph | UNDER_14.5 +53.25% |
| 10:05p ET | CHC @ SFG | Oracle Park | 57F 13mph | UNDER_8.0 +21.0% |
| 10:07p ET | TBR @ LAA | Angel Stadium | 67F 4mph | OVER_8.0 +27.41% |

## Parlays - top 5

- **2-leg @ +187 (prob 52.2%, EV +49.61%)**
  - SDP @ BAL BAL_ML (-122, model 66.5%)
  - PHI @ MIL MIL_ML (-174, model 78.6%)
- **2-leg @ +247 (prob 42.8%, EV +48.82%)**
  - SDP @ BAL BAL_ML (-122, model 66.5%)
  - TBR @ LAA OVER_8.0 (-110, model 64.5%)
- **2-leg @ +201 (prob 47.0%, EV +41.33%)**
  - ATL @ NYM UNDER_8.5 (-110, model 59.8%)
  - PHI @ MIL MIL_ML (-174, model 78.6%)
- **2-leg @ +264 (prob 38.6%, EV +40.58%)**
  - ATL @ NYM UNDER_8.5 (-110, model 59.8%)
  - TBR @ LAA OVER_8.0 (-110, model 64.5%)
- **2-leg @ +201 (prob 46.0%, EV +38.42%)**
  - MIA @ PIT OVER_9.0 (-110, model 58.6%)
  - PHI @ MIL MIL_ML (-174, model 78.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 407 | 40.8% | 42.0% | 1.029 | 0.972 |
| batter home runs | 180 | 11.1% | 12.8% | 1.150 | 0.878 |
| batter singles | 180 | 40.0% | 45.5% | 1.137 | 0.883 |
| batter runs scored | 180 | 36.1% | 38.8% | 1.073 | 0.935 |
| pitcher strikeouts | 73 | 38.4% | 47.4% | 1.232 | 0.835 |
| batter rbis | 360 | 19.4% | 23.0% | 1.183 | 0.849 |
| batter total bases | 362 | 25.7% | 32.5% | 1.262 | 0.795 |
| batter doubles | 180 | 16.1% | 16.0% | 0.991 | 1.009 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHC @ SFG | 61.2% | -158 | 2.66 | +267 | -267 |
| COL @ OAK | 22.8% | +339 | 7.39 | -196 | +196 |
| HOU @ KCR | 40.8% | +145 | 4.51 | +102 | -102 |
| PHI @ MIL | 32.6% | +206 | 5.6 | -201 | +201 |
| TBR @ LAA | 37.9% | +164 | 4.93 | +173 | -173 |

## Team Form (last 10)

**Hot:** DET 7-3 (L1, +29), MIA 9-1 (W6, +28), MIL 6-4 (W1, +21), STL 6-4 (L2, +20), BAL 5-5 (W3, +12)

**Cold:** AZ 3-7 (W1, -32), CIN 2-8 (L2, -25), MIN 4-6 (W1, -22), COL 4-6 (L2, -19), PIT 3-7 (L2, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- AZ: 8.1 IP across 2 games
- BAL: 8.3 IP across 2 games
- KC: 10.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-12._