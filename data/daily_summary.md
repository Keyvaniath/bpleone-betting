# EdgeStat Daily Brief - 2026-06-07

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-07T23:12:36 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**SFG @ CHC - OVER_8.0**
- Market: -110
- Model probability: 81.0%
- Raw edge: +54.62%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:30p ET | SFG @ CHC | Wrigley Field | 67F 8mph | OVER_8.0 +54.62% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter home runs | 1478 | 9.9% | 13.1% | 1.329 | 0.754 |
| batter rbis | 2956 | 18.4% | 23.6% | 1.281 | 0.781 |
| batter doubles | 1478 | 14.5% | 16.2% | 1.111 | 0.901 |
| batter runs scored | 1478 | 34.4% | 39.0% | 1.133 | 0.883 |
| batter total bases | 2958 | 24.5% | 32.4% | 1.324 | 0.756 |
| batter singles | 1478 | 40.9% | 44.6% | 1.093 | 0.916 |
| pitcher strikeouts | 605 | 40.0% | 40.6% | 1.014 | 0.986 |
| batter hits | 3003 | 37.5% | 41.9% | 1.120 | 0.893 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| SFG @ CHC | 26.6% | +276 | 6.25 | +405 | -405 |

## Team Form (last 10)

**Hot:** NYY 6-4 (W1, +28), LAD 7-3 (W2, +24), ATL 8-2 (W3, +21), MIL 7-3 (W2, +20), NYM 6-4 (L1, +17)

**Cold:** CIN 2-8 (L4, -27), AZ 3-7 (L2, -27), COL 4-6 (L3, -26), TB 3-7 (L2, -26), ATH 4-6 (W1, -26)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 10.2 IP across 3 games
- PIT: 12.4 IP across 3 games
- STL: 10.8 IP across 3 games
- TB: 8.0 IP across 3 games
- TEX: 10.4 IP across 3 games
- TOR: 13.0 IP across 3 games
- MIN: 8.5 IP across 3 games
- PHI: 11.3 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-06._