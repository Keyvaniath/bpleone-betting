# EdgeStat Daily Brief - 2026-06-17

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-17T23:27:44 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ CHC - COL_ML**
- Market: +172
- Model probability: 61.4%
- Raw edge: +66.96%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | CLE @ MIL | American Family Field | indoor | OVER_7.5 +22.86% |
| 8:05p ET | COL @ CHC | Wrigley Field | 64F 13mph | COL_ML +66.96% |
| 9:40p ET | PIT @ OAK | Sutter Health Park | 65F 10mph | PIT_ML +27.89% |
| 9:40p ET | BAL @ SEA | T-Mobile Park | indoor | SEA_ML +12.16% |

## Parlays - top 5

- **3-leg @ +463 (prob 26.5%, EV +48.92%)**
  - TOR @ BOS TOR_ML (+104, model 52.6%)
  - CHW @ NYY NYY_ML (-174, model 78.6%)
  - BAL @ SEA SEA_ML (-133, model 64.0%)
- **2-leg @ +201 (prob 49.2%, EV +47.91%)**
  - CHW @ NYY NYY_ML (-174, model 78.6%)
  - COL @ CHC UNDER_10.0 (-110, model 62.6%)
- **3-leg @ +582 (prob 21.7%, EV +47.81%)**
  - TOR @ BOS TOR_ML (+104, model 52.6%)
  - CLE @ MIL OVER_7.5 (-110, model 64.4%)
  - BAL @ SEA SEA_ML (-133, model 64.0%)
- **3-leg @ +538 (prob 23.0%, EV +46.96%)**
  - COL @ CHC UNDER_10.0 (-110, model 62.6%)
  - BAL @ SEA SEA_ML (-133, model 64.0%)
  - BAL @ SEA OVER_7.5 (-110, model 57.4%)
- **2-leg @ +264 (prob 40.3%, EV +46.82%)**
  - CLE @ MIL OVER_7.5 (-110, model 64.4%)
  - COL @ CHC UNDER_10.0 (-110, model 62.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ SEA | 32.9% | +204 | 5.56 | -102 | +102 |
| CLE @ MIL | 35.2% | +184 | 5.22 | +135 | -135 |
| COL @ CHC | 53.1% | -113 | 3.4 | +273 | -273 |
| PIT @ OAK | 25.3% | +295 | 7.23 | +427 | -427 |

## Team Form (last 10)

**Hot:** NYY 8-2 (W3, +25), MIL 7-3 (W2, +24), LAA 6-4 (L1, +20), MIA 7-3 (W1, +18), STL 6-4 (L1, +15)

**Cold:** PIT 3-7 (W1, -28), HOU 5-5 (W2, -17), TEX 4-6 (L2, -16), ATL 4-6 (L3, -12), CLE 3-7 (L1, -11)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 17.5 IP across 3 games
- SF: 14.6 IP across 2 games
- PHI: 11.3 IP across 3 games
- ATL: 14.0 IP across 2 games
- MIA: 10.1 IP across 3 games
- LAA: 8.0 IP across 3 games
- CIN: 11.4 IP across 3 games
- DET: 9.8 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-16._