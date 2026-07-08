# EdgeStat Daily Brief - 2026-07-08

**Model Confidence: 22.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-08T23:12:10 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CLE @ MIN - MIN_ML**
- Market: +107
- Model probability: 70.3%
- Raw edge: +45.5%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | CLE @ MIN | Target Field | 73F 4mph | MIN_ML +45.5% |
| 7:40p ET | BOS @ CHW | Rate Field | 75F 4mph | UNDER_9.0 +20.82% |
| 7:45p ET | MIL @ STL | Busch Stadium | 78F 6mph | MIL_ML +28.6% |
| 8:05p ET | LAA @ TEX | Globe Life Field | indoor | OVER_7.0 +26.35% |
| 10:10p ET | COL @ LAD | UNIQLO Field at Dodger Stadium | 65F 3mph | OVER_9.5 +40.67% |
| 10:10p ET | ARI @ SDP | Petco Park | 64F 2mph | UNDER_8.5 +31.29% |

## Parlays - top 5

- **3-leg @ +565 (prob 22.5%, EV +49.66%)**
  - ATL @ PIT PIT_ML (-118, model 63.1%)
  - NYY @ TBR OVER_7.0 (-110, model 62.1%)
  - BOS @ CHW CHW_ML (-113, model 57.4%)
- **3-leg @ +543 (prob 23.3%, EV +49.56%)**
  - ATL @ PIT PIT_ML (-118, model 63.1%)
  - SEA @ MIA MIA_ML (+107, model 51.3%)
  - MIL @ STL MIL_ML (-147, model 71.9%)
- **3-leg @ +1326 (prob 10.5%, EV +49.44%)**
  - KCR @ NYM KCR_ML (+149, model 43.1%)
  - LAA @ TEX OVER_7.5 (-110, model 59.6%)
  - COL @ LAD COL_ML (+200, model 40.8%)
- **3-leg @ +529 (prob 23.8%, EV +49.38%)**
  - OAK @ DET DET_ML (-138, model 65.1%)
  - SEA @ MIA UNDER_8.5 (-110, model 61.3%)
  - LAA @ TEX OVER_7.5 (-110, model 59.6%)
- **3-leg @ +1049 (prob 13.0%, EV +49.22%)**
  - OAK @ DET DET_ML (-138, model 65.1%)
  - PHI @ CIN PHI_ML (+122, model 49.0%)
  - COL @ LAD COL_ML (+200, model 40.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6648. Wins: 2770. Hit rate: 41.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SDP | 44.2% | +126 | 4.06 | +134 | -134 |
| BOS @ CHW | 60.1% | -150 | 2.62 | +130 | -130 |
| CLE @ MIN | 38.1% | +163 | 4.74 | -136 | +136 |
| COL @ LAD | 29.1% | +244 | 6.26 | +110 | -110 |
| KCR @ NYM | 45.9% | +118 | 3.9 | -- | -- |
| LAA @ TEX | 36.8% | +172 | 5.0 | +113 | -113 |
| MIL @ STL | 52.8% | -112 | 3.21 | +475 | -475 |
| PHI @ CIN | 42.2% | +137 | 4.31 | -- | -- |

## Team Form (last 10)

**Hot:** SEA 6-4 (L1, +22), DET 7-3 (W3, +22), MIA 7-3 (W4, +18), MIL 8-2 (W4, +17), PIT 6-4 (W3, +16)

**Cold:** SD 2-8 (W1, -36), LAA 2-8 (L7, -27), NYY 2-8 (L1, -25), ATH 2-8 (L4, -22), KC 4-6 (W3, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- STL: 15.4 IP across 3 games
- ATL: 9.2 IP across 2 games
- COL: 8.1 IP across 2 games
- NYM: 12.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-08._