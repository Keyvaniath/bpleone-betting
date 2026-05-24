# EdgeStat Daily Brief - 2026-05-24

**Model Confidence: 73.8/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-24T22:58:09 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | TEX @ LAA | Angel Stadium | 64F 6mph | -- |

## Parlays - top 1

- **2-leg @ +264 (prob 33.5%, EV +21.95%)**
  - DET @ BAL OVER_8.0 (-110, model 57.0%)
  - TEX @ LAA UNDER_8.0 (-110, model 58.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter doubles | 4580 | 14.4% | 15.9% | 1.108 | 0.903 |
| batter hits | 9162 | 39.1% | 41.7% | 1.067 | 0.937 |
| batter rbis | 9160 | 19.5% | 23.2% | 1.193 | 0.838 |
| pitcher strikeouts | 1984 | 33.6% | 38.2% | 1.138 | 0.879 |
| batter total bases | 9162 | 25.7% | 31.9% | 1.240 | 0.806 |
| batter home runs | 4580 | 10.8% | 12.9% | 1.186 | 0.844 |
| batter singles | 4580 | 43.0% | 44.5% | 1.034 | 0.967 |
| batter runs scored | 4580 | 36.3% | 38.8% | 1.067 | 0.938 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| TEX @ LAA | 27.3% | +266 | 6.71 | +177 | -177 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W2, +43), AZ 7-3 (W1, +23), CLE 8-2 (W1, +19), TB 7-3 (L1, +17), MIL 7-3 (L2, +13)

**Cold:** LAA 3-7 (W2, -33), COL 3-7 (L1, -24), DET 1-9 (L8, -23), CHC 2-8 (L7, -21), BAL 4-6 (W2, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SEA: 8.2 IP across 3 games
- SF: 9.2 IP across 2 games
- ATL: 9.0 IP across 2 games
- CWS: 9.3 IP across 2 games
- MIL: 11.8 IP across 3 games
- BAL: 9.4 IP across 2 games
- BOS: 10.3 IP across 2 games
- CIN: 9.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-23._