# EdgeStat Daily Brief - 2026-05-23

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-23T21:09:42 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**STL @ CIN - OVER_10.0**
- Market: -110
- Model probability: 72.6%
- Raw edge: +38.53%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | STL @ CIN | Great American Ball Park | 64F 3mph | OVER_10.0 +38.53% |
| 7:15p ET | LAD @ MIL | American Family Field | indoor | OVER_8.5 +4.02% |
| 9:40p ET | OAK @ SDP | Petco Park | 62F 4mph | UNDER_8.0 +30.54% |
| 10:05p ET | TEX @ LAA | Angel Stadium | 61F 3mph | OVER_7.5 +2.33% |
| 10:10p ET | COL @ ARI | Chase Field | indoor | OVER_9.0 +7.74% |

## Parlays - top 4

- **3-leg @ +573 (prob 19.4%, EV +30.87%)**
  - LAD @ MIL OVER_8.5 (-110, model 54.5%)
  - OAK @ SDP OAK_ML (-118, model 63.2%)
  - COL @ ARI OVER_9.0 (-110, model 56.4%)
- **2-leg @ +253 (prob 35.7%, EV +25.82%)**
  - OAK @ SDP OAK_ML (-118, model 63.2%)
  - COL @ ARI OVER_9.0 (-110, model 56.4%)
- **2-leg @ +253 (prob 34.4%, EV +21.48%)**
  - LAD @ MIL OVER_8.5 (-110, model 54.5%)
  - OAK @ SDP OAK_ML (-118, model 63.2%)
- **2-leg @ +264 (prob 30.7%, EV +12.05%)**
  - LAD @ MIL OVER_8.5 (-110, model 54.5%)
  - COL @ ARI OVER_9.0 (-110, model 56.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter rbis | 9468 | 19.5% | 23.2% | 1.190 | 0.840 |
| batter hits | 9470 | 39.2% | 41.7% | 1.063 | 0.941 |
| pitcher strikeouts | 2056 | 33.9% | 38.6% | 1.140 | 0.878 |
| batter total bases | 9470 | 25.9% | 31.9% | 1.231 | 0.812 |
| batter singles | 4734 | 43.2% | 44.5% | 1.031 | 0.970 |
| batter doubles | 4734 | 14.3% | 15.9% | 1.111 | 0.900 |
| batter home runs | 4734 | 11.0% | 12.9% | 1.171 | 0.854 |
| batter runs scored | 4734 | 36.3% | 38.8% | 1.067 | 0.938 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ ARI | 21.0% | +376 | 7.8 | -115 | +115 |
| LAD @ MIL | 36.9% | +171 | 4.99 | +176 | -176 |
| OAK @ SDP | 47.7% | +110 | 3.64 | +324 | -324 |
| STL @ CIN | 41.8% | +139 | 4.44 | +414 | -414 |
| TEX @ LAA | 66.1% | -195 | 2.11 | +237 | -237 |

## Team Form (last 10)

**Hot:** LAD 7-3 (L1, +31), MIL 8-2 (W4, +25), CLE 9-1 (W7, +23), TB 8-2 (W5, +22), AZ 6-4 (L1, +19)

**Cold:** LAA 2-8 (W1, -37), DET 1-9 (L7, -22), CHC 2-8 (L7, -21), KC 1-9 (L4, -18), COL 4-6 (W1, -17)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TOR: 9.3 IP across 2 games
- WSH: 11.2 IP across 2 games
- NYM: 10.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-22._