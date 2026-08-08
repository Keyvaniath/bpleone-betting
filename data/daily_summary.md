# EdgeStat Daily Brief - 2026-08-08

**Model Confidence: 21.2/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-08T21:24:35 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**TOR @ PHI - OVER_8.0**
- Market: -110
- Model probability: 82.9%
- Raw edge: +58.2%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (12 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:05p ET | TOR @ PHI | Citizens Bank Park | 77F 3mph | OVER_8.0 +58.2% |
| 6:40p ET | NYM @ PIT | PNC Park | 74F 6mph | OVER_8.0 +23.21% |
| 6:45p ET | CIN @ WSN | Nationals Park | 85F 1mph | WSN_ML +45.58% |
| 7:10p ET | CHC @ KCR | Kauffman Stadium | 80F 8mph | CHC_ML +21.48% |
| 7:10p ET | MIN @ MIL | American Family Field | indoor | OVER_7.5 +45.47% |
| 7:15p ET | HOU @ SDP | Petco Park | 74F 6mph | HOU_ML +26.37% |
| 7:15p ET | DET @ SFG | Oracle Park | 59F 9mph | OVER_7.5 +4.7% |
| 7:15p ET | COL @ STL | Busch Stadium | 80F 5mph | OVER_9.0 +32.99% |
| 7:15p ET | BAL @ TEX | Globe Life Field | indoor | TEX_ML +4.52% |
| 7:15p ET | CLE @ CHW | Rate Field | 69F 5mph | -- |
| 8:10p ET | LAD @ ARI | Chase Field | indoor | LAD_ML +19.75% |
| 9:50p ET | TBR @ SEA | T-Mobile Park | indoor | TBR_ML +20.5% |

## Parlays - top 5

- **3-leg @ +469 (prob 26.4%, EV +49.93%)**
  - TOR @ PHI PHI_ML (-204, model 71.8%)
  - LAD @ ARI OVER_8.5 (-110, model 60.9%)
  - TBR @ SEA TBR_ML (+100, model 60.2%)
- **3-leg @ +554 (prob 22.9%, EV +49.77%)**
  - NYM @ PIT OVER_8.0 (-110, model 64.5%)
  - BAL @ TEX TEX_ML (-126, model 58.3%)
  - LAD @ ARI OVER_8.5 (-110, model 60.9%)
- **2-leg @ +209 (prob 48.5%, EV +49.67%)**
  - NYM @ PIT OVER_8.0 (-110, model 64.5%)
  - CHC @ KCR CHC_ML (-162, model 75.1%)
- **3-leg @ +475 (prob 25.9%, EV +49.3%)**
  - COL @ STL OVER_9.0 (-110, model 61.2%)
  - BAL @ TEX TEX_ML (-126, model 58.3%)
  - LAD @ ARI LAD_ML (-147, model 72.8%)
- **3-leg @ +518 (prob 24.2%, EV +49.24%)**
  - NYM @ PIT PIT_ML (-144, model 64.8%)
  - COL @ STL OVER_9.0 (-110, model 61.2%)
  - LAD @ ARI OVER_8.5 (-110, model 60.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 7284. Wins: 2989. Hit rate: 41.0%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ TEX | 27.4% | +265 | 6.47 | +123 | -123 |
| CHC @ KCR | 42.5% | +135 | 4.19 | +521 | -521 |
| CIN @ WSN | 54.9% | -122 | 3.0 | -120 | +120 |
| CLE @ CHW | 54.8% | -121 | 3.05 | +154 | -154 |
| COL @ STL | 32.2% | +211 | 5.69 | +204 | -204 |
| DET @ SFG | 36.2% | +176 | 5.38 | +193 | -193 |
| HOU @ SDP | 48.5% | +106 | 3.51 | +297 | -297 |
| LAD @ ARI | 59.8% | -149 | 2.57 | +468 | -468 |
| MIN @ MIL | 48.2% | +108 | 3.65 | +115 | -115 |
| NYM @ PIT | 56.8% | -131 | 2.94 | -109 | +109 |
| TBR @ SEA | 53.1% | -113 | 3.16 | +281 | -281 |
| TOR @ PHI | 26.6% | +275 | 6.75 | -156 | +156 |

## Team Form (last 10)

**Hot:** DET 6-4 (L1, +49), BOS 9-1 (W9, +41), HOU 8-2 (W1, +25), ATL 8-2 (L1, +24), CHC 7-3 (W5, +14)

**Cold:** ATH 1-9 (L9, -42), SEA 4-6 (L2, -23), WSH 2-8 (W1, -19), PIT 2-8 (L4, -18), LAD 2-8 (L7, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 8.3 IP across 2 games
- SD: 9.0 IP across 2 games
- CWS: 14.9 IP across 2 games
- MIA: 8.6 IP across 2 games
- BOS: 13.0 IP across 2 games
- KC: 9.5 IP across 2 games
- NYM: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-08._