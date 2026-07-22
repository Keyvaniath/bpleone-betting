# EdgeStat Daily Brief - 2026-07-22

**Model Confidence: 22.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-22T23:03:58 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PIT @ NYY - OVER_9.0**
- Market: -110
- Model probability: 72.3%
- Raw edge: +38.06%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | PIT @ NYY | Yankee Stadium | 74F 10mph | OVER_9.0 +38.06% |
| 7:10p ET | BAL @ BOS | Fenway Park | 68F 5mph | -- |
| 7:07p ET | TBR @ TOR | Rogers Centre | indoor | TBR_ML +24.34% |
| 7:15p ET | SDP @ ATL | Truist Park | 77F 6mph | OVER_8.0 +22.94% |
| 8:05p ET | CHW @ TEX | Globe Life Field | indoor | TEX_ML +30.57% |
| 8:10p ET | DET @ CHC | Wrigley Field | 64F 3mph | OVER_8.0 +26.9% |
| 8:10p ET | MIA @ HOU | Daikin Park | indoor | OVER_8.0 +31.04% |

## Parlays - top 5

- **2-leg @ +261 (prob 41.4%, EV +49.74%)**
  - TBR @ TOR TBR_ML (-112, model 65.7%)
  - SDP @ ATL OVER_8.0 (-110, model 63.1%)
- **3-leg @ +665 (prob 19.5%, EV +49.16%)**
  - MIN @ CLE MIN_ML (+109, model 51.3%)
  - TBR @ TOR TBR_ML (-112, model 65.7%)
  - MIA @ HOU MIA_ML (-107, model 57.8%)
- **3-leg @ +562 (prob 22.4%, EV +48.43%)**
  - LAD @ PHI LAD_ML (-126, model 67.8%)
  - CHW @ TEX OVER_8.5 (-110, model 57.1%)
  - MIA @ HOU MIA_ML (-107, model 57.8%)
- **3-leg @ +605 (prob 20.8%, EV +46.92%)**
  - SDP @ ATL OVER_8.0 (-110, model 63.1%)
  - CHW @ TEX OVER_8.5 (-110, model 57.1%)
  - MIA @ HOU MIA_ML (-107, model 57.8%)
- **2-leg @ +242 (prob 42.8%, EV +46.51%)**
  - LAD @ PHI LAD_ML (-126, model 67.8%)
  - SDP @ ATL OVER_8.0 (-110, model 63.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6464. Wins: 2635. Hit rate: 40.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ BOS | 57.3% | -134 | 2.84 | +143 | -143 |
| CHW @ TEX | 24.3% | +311 | 7.07 | -103 | +103 |
| DET @ CHC | 42.8% | +134 | 4.19 | +173 | -173 |
| MIA @ HOU | 59.1% | -145 | 2.63 | +231 | -231 |
| PIT @ NYY | 25.0% | +300 | 7.06 | -122 | +122 |
| SDP @ ATL | 37.9% | +164 | 4.99 | -109 | +109 |
| TBR @ TOR | 18.4% | +442 | 8.45 | +334 | -334 |

## Team Form (last 10)

**Hot:** BOS 10-0 (W10, +32), CWS 6-4 (L1, +23), CHC 6-4 (W1, +20), SD 5-5 (W1, +19), ATL 6-4 (L1, +17)

**Cold:** ATH 2-8 (L1, -36), KC 5-5 (W3, -25), TEX 5-5 (W1, -25), MIN 4-6 (L4, -21), COL 3-7 (W1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.3 IP across 2 games
- MIN: 9.2 IP across 2 games
- MIL: 13.1 IP across 3 games
- AZ: 9.1 IP across 2 games
- COL: 8.1 IP across 2 games
- DET: 12.4 IP across 2 games
- WSH: 9.6 IP across 2 games
- NYM: 8.6 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-22._