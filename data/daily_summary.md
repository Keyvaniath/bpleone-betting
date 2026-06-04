# EdgeStat Daily Brief - 2026-06-04

**Model Confidence: 73.6/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-04T23:15:30 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PIT @ HOU - OVER_8.5**
- Market: -110
- Model probability: 90.0%
- Raw edge: +71.75%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | KCR @ MIN | Target Field | 73F 8mph | UNDER_8.5 +23.77% |
| 8:05p ET | OAK @ CHC | Wrigley Field | 75F 7mph | OAK_ML +10.95% |
| 8:10p ET | PIT @ HOU | Daikin Park | indoor | OVER_8.5 +71.75% |
| 9:40p ET | LAD @ ARI | Chase Field | indoor | LAD_ML +52.79% |

## Parlays - top 5

- **3-leg @ +709 (prob 18.1%, EV +46.11%)**
  - TOR @ ATL UNDER_7.5 (-110, model 57.7%)
  - KCR @ MIN UNDER_8.5 (-110, model 62.9%)
  - OAK @ CHC OAK_ML (+122, model 49.8%)
- **3-leg @ +709 (prob 18.1%, EV +46.06%)**
  - KCR @ MIN UNDER_8.5 (-110, model 62.9%)
  - OAK @ CHC OAK_ML (+122, model 49.8%)
  - OAK @ CHC UNDER_10.5 (-110, model 57.6%)
- **3-leg @ +596 (prob 20.9%, EV +45.6%)**
  - TOR @ ATL UNDER_7.5 (-110, model 57.7%)
  - KCR @ MIN UNDER_8.5 (-110, model 62.9%)
  - OAK @ CHC UNDER_10.5 (-110, model 57.6%)
- **3-leg @ +709 (prob 16.5%, EV +33.83%)**
  - TOR @ ATL UNDER_7.5 (-110, model 57.7%)
  - OAK @ CHC OAK_ML (+122, model 49.8%)
  - OAK @ CHC UNDER_10.5 (-110, model 57.6%)
- **2-leg @ +324 (prob 31.3%, EV +32.71%)**
  - KCR @ MIN UNDER_8.5 (-110, model 62.9%)
  - OAK @ CHC OAK_ML (+122, model 49.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter singles | 2107 | 41.3% | 44.5% | 1.078 | 0.928 |
| batter total bases | 4216 | 24.7% | 32.2% | 1.302 | 0.768 |
| batter home runs | 2107 | 10.4% | 13.0% | 1.253 | 0.799 |
| batter rbis | 4214 | 19.1% | 23.5% | 1.229 | 0.814 |
| pitcher strikeouts | 881 | 36.1% | 39.1% | 1.082 | 0.925 |
| batter runs scored | 2107 | 35.7% | 39.0% | 1.090 | 0.918 |
| batter doubles | 2107 | 14.3% | 16.2% | 1.130 | 0.885 |
| batter hits | 4261 | 37.6% | 41.9% | 1.113 | 0.899 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| KCR @ MIN | 48.1% | +108 | 3.62 | +149 | -149 |
| LAD @ ARI | 42.1% | +137 | 4.32 | +1526 | -1526 |
| OAK @ CHC | 31.0% | +223 | 6.14 | +164 | -164 |
| PIT @ HOU | 24.8% | +303 | 6.97 | -141 | +141 |
| TOR @ ATL | 68.9% | -221 | 1.87 | -- | -- |

## Team Form (last 10)

**Hot:** LAD 8-2 (W2, +32), CWS 7-3 (W1, +28), NYY 7-3 (W1, +28), SEA 8-2 (L1, +22), MIL 7-3 (L2, +22)

**Cold:** TB 2-8 (L3, -37), COL 4-6 (L1, -28), MIN 3-7 (L1, -28), ATH 4-6 (W2, -24), KC 3-7 (W1, -23)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SEA: 8.2 IP across 2 games
- TB: 12.1 IP across 2 games
- PHI: 8.0 IP across 3 games
- NYY: 9.7 IP across 3 games
- MIL: 13.3 IP across 3 games
- LAA: 8.1 IP across 2 games
- BAL: 10.1 IP across 3 games
- BOS: 10.2 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-03._