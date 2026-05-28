# EdgeStat Daily Brief - 2026-05-28

**Model Confidence: 74.1/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-28T22:04:36 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**HOU @ TEX - HOU_ML**
- Market: +126
- Model probability: 60.2%
- Raw edge: +36.1%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:35p ET | TOR @ BAL | Oriole Park at Camden Yards | 60F 7mph | UNDER_8.5 +5.4% |
| 6:40p ET | CHC @ PIT | PNC Park | 60F 4mph | PIT_ML +6.76% |
| 8:05p ET | HOU @ TEX | Globe Life Field | indoor | HOU_ML +36.1% |

## Parlays - top 3

- **3-leg @ +481 (prob 20.4%, EV +18.47%)**
  - TOR @ BAL UNDER_8.5 (-110, model 55.2%)
  - CHC @ PIT PIT_ML (-168, model 66.9%)
  - CHC @ PIT OVER_7.5 (-110, model 55.1%)
- **2-leg @ +205 (prob 37.0%, EV +12.52%)**
  - TOR @ BAL UNDER_8.5 (-110, model 55.2%)
  - CHC @ PIT PIT_ML (-168, model 66.9%)
- **2-leg @ +264 (prob 30.4%, EV +10.97%)**
  - TOR @ BAL UNDER_8.5 (-110, model 55.2%)
  - CHC @ PIT OVER_7.5 (-110, model 55.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1576 | 35.0% | 38.4% | 1.098 | 0.912 |
| batter doubles | 3711 | 14.6% | 16.0% | 1.097 | 0.911 |
| batter rbis | 7422 | 19.0% | 23.3% | 1.223 | 0.818 |
| batter home runs | 3711 | 10.1% | 12.9% | 1.283 | 0.780 |
| batter total bases | 7424 | 25.1% | 31.9% | 1.271 | 0.787 |
| batter hits | 7424 | 38.5% | 41.8% | 1.084 | 0.923 |
| batter runs scored | 3711 | 35.3% | 38.8% | 1.098 | 0.911 |
| batter singles | 3711 | 42.7% | 44.5% | 1.042 | 0.960 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHC @ PIT | 34.5% | +189 | 5.25 | -114 | +114 |
| HOU @ TEX | 68.4% | -217 | 1.9 | +263 | -263 |
| TOR @ BAL | 34.2% | +193 | 5.13 | +172 | -172 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W5, +35), AZ 9-1 (W5, +31), NYY 6-4 (W4, +20), MIL 7-3 (W3, +16), SEA 6-4 (W3, +13)

**Cold:** COL 2-8 (L5, -33), CHC 1-9 (W1, -29), KC 3-7 (L3, -24), DET 2-8 (L1, -18), NYM 3-7 (W1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 11.0 IP across 2 games
- TOR: 10.6 IP across 2 games
- MIN: 10.7 IP across 3 games
- CWS: 10.0 IP across 3 games
- MIL: 8.0 IP across 2 games
- LAA: 11.3 IP across 3 games
- CLE: 9.0 IP across 2 games
- DET: 9.8 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-27._