# EdgeStat Daily Brief - 2026-05-27

**Model Confidence: 73.9/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-27T23:18:58 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**HOU @ TEX - OVER_7.5**
- Market: -110
- Model probability: 77.8%
- Raw edge: +48.47%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | MIN @ CHW | Rate Field | 61F 9mph | OVER_8.0 +28.69% |
| 7:40p ET | NYY @ KCR | Kauffman Stadium | 74F 5mph | NYY_ML +26.63% |
| 8:05p ET | HOU @ TEX | Globe Life Field | indoor | OVER_7.5 +48.47% |
| 10:10p ET | COL @ LAD | UNIQLO Field at Dodger Stadium | 54F 1mph | OVER_8.0 +27.66% |

## Parlays - top 5

- **3-leg @ +613 (prob 20.9%, EV +49.29%)**
  - LAA @ DET DET_ML (-114, model 57.0%)
  - ATL @ BOS OVER_8.0 (-110, model 65.0%)
  - CIN @ NYM CIN_ML (-101, model 56.5%)
- **3-leg @ +321 (prob 35.4%, EV +48.99%)**
  - LAA @ DET DET_ML (-114, model 57.0%)
  - CHC @ PIT PIT_ML (-121, model 65.2%)
  - COL @ LAD LAD_ML (-440, model 95.2%)
- **2-leg @ +249 (prob 42.4%, EV +47.91%)**
  - CHC @ PIT PIT_ML (-121, model 65.2%)
  - ATL @ BOS OVER_8.0 (-110, model 65.0%)
- **3-leg @ +613 (prob 20.7%, EV +47.36%)**
  - LAA @ DET UNDER_7.5 (-110, model 64.2%)
  - LAA @ DET DET_ML (-114, model 57.0%)
  - CIN @ NYM CIN_ML (-101, model 56.5%)
- **2-leg @ +249 (prob 41.9%, EV +46.0%)**
  - LAA @ DET UNDER_7.5 (-110, model 64.2%)
  - CHC @ PIT PIT_ML (-121, model 65.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 7690 | 38.6% | 41.8% | 1.082 | 0.924 |
| batter rbis | 7688 | 19.1% | 23.3% | 1.217 | 0.822 |
| batter home runs | 3844 | 10.2% | 12.9% | 1.264 | 0.792 |
| pitcher strikeouts | 1640 | 34.3% | 38.5% | 1.120 | 0.893 |
| batter total bases | 7690 | 25.2% | 31.9% | 1.267 | 0.789 |
| batter singles | 3844 | 42.9% | 44.5% | 1.038 | 0.963 |
| batter runs scored | 3844 | 35.6% | 38.7% | 1.089 | 0.918 |
| batter doubles | 3844 | 14.4% | 16.0% | 1.105 | 0.905 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ LAD | 56.2% | -128 | 2.91 | -930 | +930 |
| HOU @ TEX | 29.8% | +236 | 6.06 | +137 | -137 |
| MIN @ CHW | 39.0% | +157 | 4.44 | +162 | -162 |
| NYY @ KCR | 41.8% | +139 | 4.25 | +591 | -591 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W4, +45), AZ 9-1 (W4, +32), MIL 7-3 (W3, +16), SEA 6-4 (W3, +13), TB 6-4 (L3, +11)

**Cold:** CHC 0-10 (L10, -40), COL 2-8 (L4, -32), DET 1-9 (L2, -20), LAA 5-5 (W4, -20), KC 3-7 (L2, -19)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.6 IP across 3 games
- SEA: 11.0 IP across 3 games
- STL: 8.0 IP across 3 games
- TB: 12.3 IP across 2 games
- TOR: 12.0 IP across 3 games
- MIA: 8.7 IP across 3 games
- MIL: 10.0 IP across 3 games
- BAL: 8.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-26._