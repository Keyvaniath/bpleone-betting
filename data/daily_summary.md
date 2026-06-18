# EdgeStat Daily Brief - 2026-06-18

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-18T05:36:41 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHW @ NYY - OVER_9.5**
- Market: -110
- Model probability: 81.7%
- Raw edge: +55.95%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:35p ET | TOR @ BOS | Fenway Park | 78F 17mph | TOR_ML +4.72% |
| 2:10p ET | CLE @ MIL | American Family Field | indoor | MIL_ML +20.86% |
| 2:35p ET | MIN @ TEX | Globe Life Field | indoor | OVER_7.5 +16.43% |
| 4:10p ET | BAL @ SEA | T-Mobile Park | indoor | -- |
| 6:40p ET | NYM @ PHI | Citizens Bank Park | 83F 9mph | UNDER_9.5 +28.53% |
| 7:05p ET | CHW @ NYY | Yankee Stadium | 79F 11mph | OVER_9.5 +55.95% |
| 7:15p ET | SFG @ ATL | Truist Park | 72F 10mph | OVER_8.0 +28.76% |
| 7:40p ET | STL @ KCR | Kauffman Stadium | 68F 4mph | -- |
| 9:40p ET | LAA @ OAK | Sutter Health Park | 63F 11mph | OAK_ML +44.44% |

## Parlays - top 5

- **3-leg @ +474 (prob 25.9%, EV +48.89%)**
  - CLE @ MIL MIL_ML (-148, model 72.1%)
  - CLE @ MIL UNDER_7.5 (-110, model 56.1%)
  - MIN @ TEX MIN_ML (-126, model 64.1%)
- **3-leg @ +461 (prob 26.5%, EV +48.38%)**
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - MIN @ TEX MIN_ML (-126, model 64.1%)
  - CHW @ NYY NYY_ML (-157, model 67.7%)
- **3-leg @ +511 (prob 24.2%, EV +48.09%)**
  - CLE @ MIL MIL_ML (-148, model 72.1%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - STL @ KCR UNDER_9.0 (-110, model 55.1%)
- **3-leg @ +562 (prob 22.3%, EV +47.38%)**
  - TOR @ BOS TOR_ML (+107, model 50.6%)
  - CLE @ MIL MIL_ML (-148, model 72.1%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
- **3-leg @ +562 (prob 22.1%, EV +46.44%)**
  - CLE @ MIL MIL_ML (-148, model 72.1%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - NYM @ PHI NYM_ML (+107, model 50.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ SEA | 42.0% | +138 | 4.34 | +121 | -121 |
| CHW @ NYY | 23.8% | +321 | 7.71 | -133 | +133 |
| CLE @ MIL | 37.3% | +168 | 4.93 | -141 | +141 |
| LAA @ OAK | 46.7% | +114 | 4.01 | -185 | +185 |
| MIN @ TEX | 35.4% | +183 | 5.19 | +316 | -316 |
| NYM @ PHI | 30.4% | +229 | 6.09 | +176 | -176 |
| SFG @ ATL | 31.3% | +219 | 6.04 | +134 | -134 |
| STL @ KCR | 42.1% | +138 | 4.45 | +147 | -147 |
| TOR @ BOS | 37.2% | +169 | 5.3 | +175 | -175 |

## Team Form (last 10)

**Hot:** NYY 8-2 (W4, +29), MIL 7-3 (W3, +27), LAA 6-4 (L1, +20), MIA 7-3 (W1, +18), STL 6-4 (L1, +15)

**Cold:** HOU 5-5 (W2, -17), ATL 3-7 (L4, -17), PIT 4-6 (W2, -17), TEX 4-6 (L2, -16), CLE 3-7 (L2, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.3 IP across 2 games
- SD: 10.5 IP across 2 games
- SF: 17.9 IP across 3 games
- TOR: 10.5 IP across 2 games
- PHI: 8.3 IP across 2 games
- ATL: 18.0 IP across 3 games
- MIL: 8.2 IP across 2 games
- CIN: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-17._