# EdgeStat Daily Brief - 2026-05-31

**Model Confidence: 73.8/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-31T21:12:09 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ STL - OVER_8.5**
- Market: -110
- Model probability: 61.8%
- Raw edge: +18.03%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | CHC @ STL | Busch Stadium | 72F 4mph | OVER_8.5 +18.03% |

## Parlays - top 1

- **2-leg (SGP) @ +276 (prob 31.1%, EV +17.14%)**
  - CHC @ STL OVER_8.5 (-110, model 61.8%)
  - CHC @ STL CHC_ML (-103, model 58.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter doubles | 3069 | 14.6% | 16.0% | 1.096 | 0.913 |
| batter home runs | 3069 | 10.0% | 13.0% | 1.294 | 0.774 |
| batter singles | 3069 | 42.4% | 44.5% | 1.049 | 0.953 |
| batter runs scored | 3069 | 35.5% | 38.8% | 1.093 | 0.915 |
| pitcher strikeouts | 1284 | 34.5% | 38.6% | 1.120 | 0.894 |
| batter total bases | 6140 | 24.9% | 32.0% | 1.284 | 0.779 |
| batter hits | 6140 | 38.3% | 41.8% | 1.091 | 0.917 |
| batter rbis | 6138 | 18.9% | 23.3% | 1.231 | 0.812 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHC @ STL | 33.0% | +203 | 12.58 | +238 | -238 |

## Team Form (last 10)

**Hot:** LAD 8-2 (L1, +28), NYY 6-4 (L1, +24), HOU 7-3 (L1, +23), BAL 7-3 (W2, +21), CWS 7-3 (W5, +20)

**Cold:** KC 2-8 (L5, -33), ATH 4-6 (W1, -23), CLE 5-5 (L2, -20), MIN 4-6 (L5, -20), DET 2-8 (L4, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.6 IP across 2 games
- PIT: 10.8 IP across 3 games
- SD: 9.7 IP across 3 games
- STL: 9.5 IP across 2 games
- TB: 9.6 IP across 3 games
- TOR: 14.5 IP across 3 games
- MIN: 9.0 IP across 3 games
- ATL: 11.1 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-30._