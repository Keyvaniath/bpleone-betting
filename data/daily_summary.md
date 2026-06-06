# EdgeStat Daily Brief - 2026-06-06

**Model Confidence: 73.9/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-06T21:25:17 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYM @ SDP - UNDER_7.5**
- Market: -110
- Model probability: 80.3%
- Raw edge: +53.32%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:35p ET | CLE @ TEX | Globe Life Field | indoor | OVER_7.5 +4.35% |
| 7:35p ET | BOS @ NYY | Yankee Stadium | 71F 7mph | NYY_ML +10.51% |
| 9:10p ET | MIL @ COL | Coors Field | 71F 12mph | MIL_ML +38.45% |
| 10:10p ET | LAA @ LAD | UNIQLO Field at Dodger Stadium | 62F 3mph | LAD_ML +30.2% |
| 10:10p ET | NYM @ SDP | Petco Park | 63F 3mph | UNDER_7.5 +53.32% |

## Parlays - top 4

- **3-leg @ +474 (prob 24.4%, EV +39.87%)**
  - CLE @ TEX OVER_7.5 (-110, model 54.7%)
  - BOS @ NYY NYY_ML (-174, model 70.2%)
  - LAA @ LAD OVER_8.5 (-110, model 63.5%)
- **2-leg @ +201 (prob 44.6%, EV +34.04%)**
  - BOS @ NYY NYY_ML (-174, model 70.2%)
  - LAA @ LAD OVER_8.5 (-110, model 63.5%)
- **2-leg @ +264 (prob 34.7%, EV +26.56%)**
  - CLE @ TEX OVER_7.5 (-110, model 54.7%)
  - LAA @ LAD OVER_8.5 (-110, model 63.5%)
- **2-leg @ +201 (prob 38.4%, EV +15.32%)**
  - CLE @ TEX OVER_7.5 (-110, model 54.7%)
  - BOS @ NYY NYY_ML (-174, model 70.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter runs scored | 1643 | 34.9% | 39.0% | 1.117 | 0.896 |
| batter total bases | 3288 | 24.4% | 32.3% | 1.324 | 0.756 |
| batter home runs | 1643 | 10.0% | 13.1% | 1.303 | 0.769 |
| batter rbis | 3286 | 18.8% | 23.6% | 1.255 | 0.797 |
| batter singles | 1643 | 41.5% | 44.5% | 1.073 | 0.932 |
| batter hits | 3333 | 37.7% | 41.9% | 1.111 | 0.900 |
| pitcher strikeouts | 677 | 38.3% | 39.5% | 1.033 | 0.968 |
| batter doubles | 1643 | 14.3% | 16.1% | 1.127 | 0.888 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | 38.0% | +163 | 4.93 | -136 | +136 |
| CLE @ TEX | 32.5% | +207 | 5.62 | +130 | -130 |
| LAA @ LAD | 40.3% | +148 | 4.62 | -397 | +397 |
| MIL @ COL | 44.3% | +126 | 4.37 | +1247 | -1247 |
| NYM @ SDP | 26.2% | +281 | 6.75 | +390 | -390 |

## Team Form (last 10)

**Hot:** BAL 7-3 (W2, +28), LAD 7-3 (W1, +26), CWS 6-4 (L1, +24), NYY 6-4 (L1, +24), MIL 7-3 (W1, +20)

**Cold:** ATH 3-7 (L2, -30), TB 3-7 (W1, -29), COL 4-6 (L2, -22), SD 1-9 (L6, -21), CIN 3-7 (L3, -20)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 8.2 IP across 2 games
- STL: 9.2 IP across 2 games
- TOR: 8.9 IP across 2 games
- MIN: 9.2 IP across 3 games
- MIL: 11.2 IP across 2 games
- KC: 10.1 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-05._