# EdgeStat Daily Brief - 2026-05-30

**Model Confidence: 73.8/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-30T21:17:59 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ATL @ CIN - ATL_ML**
- Market: -124
- Model probability: 90.2%
- Raw edge: +63.02%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | CHC @ STL | Busch Stadium | 73F 5mph | CHC_ML +31.79% |
| 7:15p ET | ATL @ CIN | Great American Ball Park | 64F 8mph | ATL_ML +63.02% |
| 9:10p ET | SFG @ COL | Coors Field | 58F 5mph | SFG_ML +12.48% |
| 10:05p ET | NYY @ OAK | Sutter Health Park | 64F 6mph | NYY_ML +27.47% |
| 10:10p ET | ARI @ SEA | T-Mobile Park | indoor | OVER_7.0 +8.83% |
| 10:10p ET | PHI @ LAD | UNIQLO Field at Dodger Stadium | 60F 3mph | LAD_ML +19.56% |

## Parlays - top 5

- **3-leg @ +545 (prob 23.2%, EV +49.88%)**
  - ARI @ SEA OVER_7.0 (-110, model 57.0%)
  - PHI @ LAD LAD_ML (-130, model 67.6%)
  - PHI @ LAD UNDER_8.5 (-110, model 60.3%)
- **3-leg @ +545 (prob 22.8%, EV +47.28%)**
  - CHC @ STL OVER_8.0 (-110, model 56.0%)
  - PHI @ LAD LAD_ML (-130, model 67.6%)
  - PHI @ LAD UNDER_8.5 (-110, model 60.3%)
- **3-leg @ +534 (prob 23.1%, EV +46.55%)**
  - SFG @ COL SFG_ML (-114, model 59.9%)
  - NYY @ OAK OVER_9.5 (-110, model 57.1%)
  - PHI @ LAD LAD_ML (-130, model 67.6%)
- **3-leg @ +534 (prob 23.1%, EV +46.37%)**
  - SFG @ COL SFG_ML (-114, model 59.9%)
  - ARI @ SEA OVER_7.0 (-110, model 57.0%)
  - PHI @ LAD LAD_ML (-130, model 67.6%)
- **3-leg @ +457 (prob 26.0%, EV +44.84%)**
  - ARI @ SEA SEA_ML (-154, model 63.8%)
  - PHI @ LAD LAD_ML (-130, model 67.6%)
  - PHI @ LAD UNDER_8.5 (-110, model 60.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter singles | 3232 | 42.5% | 44.5% | 1.047 | 0.955 |
| batter rbis | 6464 | 19.1% | 23.3% | 1.223 | 0.818 |
| batter doubles | 3232 | 14.6% | 16.0% | 1.096 | 0.912 |
| batter home runs | 3232 | 10.1% | 12.9% | 1.286 | 0.778 |
| pitcher strikeouts | 1364 | 34.4% | 38.4% | 1.116 | 0.897 |
| batter runs scored | 3232 | 35.7% | 38.8% | 1.085 | 0.921 |
| batter total bases | 6466 | 25.1% | 32.0% | 1.277 | 0.783 |
| batter hits | 6466 | 38.5% | 41.8% | 1.086 | 0.921 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SEA | 48.4% | +107 | 3.63 | +101 | -101 |
| ATL @ CIN | 25.6% | +290 | 6.78 | +1624 | -1624 |
| CHC @ STL | 51.8% | -107 | 3.24 | +530 | -530 |
| NYY @ OAK | 53.6% | -115 | 3.23 | +600 | -600 |
| PHI @ LAD | 51.4% | -106 | 3.33 | -117 | +117 |
| SFG @ COL | 22.2% | +350 | 7.76 | +242 | -242 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W6, +28), NYY 7-3 (W5, +27), ATL 7-3 (W2, +22), AZ 8-2 (L1, +20), SEA 7-3 (W4, +19)

**Cold:** KC 2-8 (L4, -34), COL 2-8 (W1, -32), NYM 3-7 (W2, -20), SF 2-8 (L4, -19), DET 2-8 (L3, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TOR: 9.7 IP across 2 games
- ATL: 8.1 IP across 2 games
- CWS: 15.2 IP across 3 games
- BOS: 11.1 IP across 2 games
- WSH: 8.0 IP across 1 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-29._