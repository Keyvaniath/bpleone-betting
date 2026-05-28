# EdgeStat Daily Brief - 2026-05-28

**Model Confidence: 74.1/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-28T08:08:53 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**HOU @ TEX - HOU_ML**
- Market: +122
- Model probability: 60.2%
- Raw edge: +33.69%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | LAA @ DET | Comerica Park | 71F 10mph | -- |
| 2:10p ET | MIN @ CHW | Rate Field | 63F 15mph | CHW_ML +15.1% |
| 4:10p ET | ATL @ BOS | Fenway Park | 63F 11mph | ATL_ML +18.04% |
| 6:35p ET | TOR @ BAL | Oriole Park at Camden Yards | 59F 6mph | UNDER_8.5 +7.86% |
| 6:40p ET | CHC @ PIT | PNC Park | 59F 4mph | PIT_ML +5.78% |
| 8:05p ET | HOU @ TEX | Globe Life Field | indoor | HOU_ML +33.69% |

## Parlays - top 5

- **3-leg @ +455 (prob 26.9%, EV +48.98%)**
  - MIN @ CHW CHW_ML (-140, model 67.1%)
  - ATL @ BOS ATL_ML (-144, model 69.7%)
  - ATL @ BOS OVER_7.0 (-110, model 57.4%)
- **3-leg @ +455 (prob 26.4%, EV +46.54%)**
  - MIN @ CHW CHW_ML (-140, model 67.1%)
  - ATL @ BOS ATL_ML (-144, model 69.7%)
  - TOR @ BAL UNDER_8.5 (-110, model 56.5%)
- **3-leg @ +359 (prob 31.3%, EV +43.71%)**
  - MIN @ CHW CHW_ML (-140, model 67.1%)
  - ATL @ BOS ATL_ML (-144, model 69.7%)
  - CHC @ PIT PIT_ML (-172, model 66.9%)
- **3-leg @ +455 (prob 25.6%, EV +41.97%)**
  - MIN @ CHW CHW_ML (-140, model 67.1%)
  - ATL @ BOS ATL_ML (-144, model 69.7%)
  - CHC @ PIT OVER_7.5 (-110, model 54.7%)
- **3-leg @ +455 (prob 25.3%, EV +40.18%)**
  - MIN @ CHW CHW_ML (-140, model 67.1%)
  - MIN @ CHW OVER_8.0 (-110, model 54.0%)
  - ATL @ BOS ATL_ML (-144, model 69.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter singles | 3711 | 42.7% | 44.5% | 1.042 | 0.960 |
| batter rbis | 7422 | 19.0% | 23.3% | 1.223 | 0.818 |
| batter runs scored | 3711 | 35.3% | 38.8% | 1.098 | 0.911 |
| batter total bases | 7424 | 25.1% | 31.9% | 1.271 | 0.787 |
| batter hits | 7424 | 38.5% | 41.8% | 1.084 | 0.923 |
| batter doubles | 3711 | 14.6% | 16.0% | 1.097 | 0.911 |
| pitcher strikeouts | 1576 | 35.0% | 38.4% | 1.098 | 0.912 |
| batter home runs | 3711 | 10.1% | 12.9% | 1.283 | 0.780 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ BOS | 60.9% | -156 | 2.45 | +425 | -425 |
| CHC @ PIT | 34.5% | +189 | 5.27 | -114 | +114 |
| HOU @ TEX | 68.4% | -217 | 1.9 | +263 | -263 |
| LAA @ DET | 14.2% | +602 | 10.11 | +144 | -144 |
| MIN @ CHW | 65.2% | -187 | 1.94 | -117 | +117 |
| TOR @ BAL | 34.2% | +193 | 5.19 | +172 | -172 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W5, +35), AZ 9-1 (W5, +31), NYY 6-4 (W4, +20), MIL 7-3 (W3, +16), SEA 6-4 (W3, +13)

**Cold:** COL 2-8 (L5, -33), CHC 1-9 (W1, -29), KC 3-7 (L3, -24), DET 2-8 (W1, -15), NYM 3-7 (W1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 11.0 IP across 2 games
- TOR: 10.6 IP across 2 games
- MIL: 8.0 IP across 2 games
- CLE: 9.0 IP across 2 games
- KC: 9.5 IP across 2 games
- WSH: 9.3 IP across 2 games
- NYM: 10.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.2**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-27._