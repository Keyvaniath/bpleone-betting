# EdgeStat Daily Brief - 2026-06-18

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-18T17:16:56 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHW @ NYY - OVER_9.5**
- Market: -110
- Model probability: 82.0%
- Raw edge: +56.53%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:35p ET | TOR @ BOS | Fenway Park | 85F 21mph | TOR_ML +11.82% |
| 2:10p ET | CLE @ MIL | American Family Field | indoor | MIL_ML +20.77% |
| 2:35p ET | MIN @ TEX | Globe Life Field | indoor | OVER_7.5 +16.43% |
| 4:10p ET | BAL @ SEA | T-Mobile Park | indoor | SEA_ML +2.05% |
| 6:40p ET | NYM @ PHI | Citizens Bank Park | 79F 11mph | UNDER_9.5 +28.26% |
| 7:05p ET | CHW @ NYY | Yankee Stadium | 80F 11mph | OVER_9.5 +56.53% |
| 7:15p ET | SFG @ ATL | Truist Park | 71F 9mph | OVER_8.0 +26.51% |
| 7:40p ET | STL @ KCR | Kauffman Stadium | 69F 3mph | -- |
| 9:40p ET | LAA @ OAK | Sutter Health Park | 64F 11mph | OAK_ML +23.01% |

## Parlays - top 5

- **3-leg @ +485 (prob 25.5%, EV +49.48%)**
  - TOR @ BOS UNDER_9.5 (-110, model 55.3%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)
- **3-leg @ +599 (prob 21.4%, EV +49.35%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - CLE @ MIL MIL_ML (-147, model 71.9%)
  - CLE @ MIL UNDER_7.5 (-110, model 58.7%)
- **3-leg @ +655 (prob 19.8%, EV +49.24%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - MIN @ TEX MIN_ML (-123, model 64.1%)
- **3-leg @ +456 (prob 26.8%, EV +49.17%)**
  - TOR @ BOS UNDER_9.5 (-110, model 55.3%)
  - MIN @ TEX MIN_ML (-123, model 64.1%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)
- **3-leg @ +568 (prob 22.3%, EV +48.88%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - SFG @ ATL OVER_8.0 (-110, model 58.1%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)

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
| CHW @ NYY | 23.8% | +321 | 7.68 | -134 | +134 |
| CLE @ MIL | 37.3% | +168 | 4.93 | -138 | +138 |
| LAA @ OAK | 46.7% | +114 | 4.03 | -185 | +185 |
| MIN @ TEX | 35.4% | +183 | 5.19 | +316 | -316 |
| NYM @ PHI | 30.4% | +229 | 6.25 | +176 | -176 |
| SFG @ ATL | 31.3% | +219 | 5.97 | +134 | -134 |
| STL @ KCR | 42.1% | +138 | 4.35 | +147 | -147 |
| TOR @ BOS | 37.2% | +169 | 5.56 | +174 | -174 |

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