# EdgeStat Daily Brief - 2026-08-03

**Model Confidence: 21.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-03T16:37:51 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ PHI - WSN_ML**
- Market: +138
- Model probability: 79.9%
- Raw edge: +90.1%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | WSN @ PHI | Citizens Bank Park | 74F 3mph | WSN_ML +90.1% |
| 7:05p ET | STL @ NYY | Yankee Stadium | 69F 4mph | NYY_ML +13.23% |
| 7:40p ET | PIT @ MIL | American Family Field | indoor | OVER_8.5 +45.55% |
| 8:05p ET | LAD @ CHC | Wrigley Field | 67F 6mph | OVER_8.0 +46.07% |
| 8:05p ET | SFG @ TEX | Globe Life Field | indoor | OVER_8.0 +24.2% |
| 8:10p ET | TOR @ HOU | Daikin Park | indoor | OVER_9.0 +38.27% |
| 8:40p ET | TBR @ COL | Coors Field | 82F 20mph | OVER_11.5 +59.06% |
| 9:40p ET | SDP @ ARI | Chase Field | indoor | UNDER_9.0 +17.31% |

## Parlays - top 5

- **3-leg @ +333 (prob 34.4%, EV +48.81%)**
  - STL @ NYY NYY_ML (-230, model 78.9%)
  - SFG @ TEX OVER_8.0 (-110, model 65.1%)
  - TBR @ COL TBR_ML (-172, model 66.9%)
- **2-leg @ +330 (prob 34.1%, EV +46.61%)**
  - PIT @ MIL PIT_ML (+125, model 52.5%)
  - SFG @ TEX OVER_8.0 (-110, model 65.1%)
- **3-leg @ +579 (prob 21.6%, EV +46.52%)**
  - PIT @ MIL PIT_ML (+125, model 52.5%)
  - TBR @ COL TBR_ML (-172, model 66.9%)
  - SDP @ ARI UNDER_9.0 (-110, model 61.5%)
- **2-leg @ +264 (prob 40.0%, EV +45.71%)**
  - SFG @ TEX OVER_8.0 (-110, model 65.1%)
  - SDP @ ARI UNDER_9.0 (-110, model 61.5%)
- **3-leg @ +622 (prob 20.0%, EV +44.19%)**
  - PIT @ MIL PIT_ML (+125, model 52.5%)
  - SFG @ TEX SFG_ML (+103, model 56.9%)
  - TBR @ COL TBR_ML (-172, model 66.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 7108. Wins: 2943. Hit rate: 41.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAD @ CHC | 51.3% | -105 | 3.35 | +174 | -174 |
| PIT @ MIL | 37.0% | +170 | 4.97 | +179 | -179 |
| SDP @ ARI | 50.3% | -101 | 3.43 | +162 | -162 |
| SFG @ TEX | 38.1% | +162 | 4.82 | +224 | -224 |
| STL @ NYY | 53.2% | -114 | 3.23 | -207 | +207 |
| TBR @ COL | 23.6% | +324 | 6.52 | +310 | -310 |
| TOR @ HOU | 31.0% | +223 | 5.86 | -174 | +174 |
| WSN @ PHI | 29.1% | +243 | 6.05 | +678 | -678 |

## Travel / Rest Flags

- **PIT @ MIL** (home): travel + back-to-back (+2h tz shift)
- **LAD @ CHC** (away): travel + back-to-back (+2h tz shift)
- **SFG @ TEX** (away): travel + back-to-back (+2h tz shift)
- **TBR @ COL** (away): travel + back-to-back (-2h tz shift)
- **SDP @ ARI** (home): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** DET 6-4 (W3, +35), CHC 6-4 (L1, +24), HOU 9-1 (W6, +21), SD 8-2 (W3, +17), BOS 8-2 (W5, +15)

**Cold:** ATH 2-8 (L5, -32), PIT 3-7 (L1, -21), LAA 2-8 (W1, -17), SEA 4-6 (W2, -14), KC 3-7 (L4, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.3 IP across 2 games
- PIT: 10.0 IP across 2 games
- SD: 8.8 IP across 2 games
- CWS: 9.2 IP across 2 games
- LAA: 9.3 IP across 2 games
- KC: 8.1 IP across 2 games
- NYM: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.7**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-02._