# EdgeStat Daily Brief - 2026-07-11

**Model Confidence: 21.7/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-11T22:50:31 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ CIN - OVER_9.0**
- Market: -110
- Model probability: 81.3%
- Raw edge: +55.29%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | KCR @ BAL | Oriole Park at Camden Yards | 73F 4mph | KCR_ML +10.02% |
| 7:05p ET | HOU @ TEX | Globe Life Field | indoor | OVER_9.0 +8.5% |
| 7:10p ET | CHC @ CIN | Great American Ball Park | 71F 4mph | OVER_9.0 +55.29% |
| 7:15p ET | ATL @ STL | Busch Stadium | 73F 4mph | ATL_ML +31.22% |
| 8:40p ET | TOR @ SDP | Petco Park | 67F 3mph | UNDER_8.5 +49.96% |
| 9:10p ET | ARI @ LAD | UNIQLO Field at Dodger Stadium | 66F 4mph | LAD_ML +30.0% |

## Parlays - top 5

- **3-leg @ +669 (prob 18.3%, EV +40.42%)**
  - KCR @ BAL KCR_ML (+126, model 48.7%)
  - CHC @ CIN CHC_ML (-128, model 61.3%)
  - ATL @ STL OVER_8.5 (-110, model 61.2%)
- **3-leg @ +710 (prob 17.3%, EV +40.17%)**
  - PHI @ DET DET_ML (-114, model 58.1%)
  - KCR @ BAL KCR_ML (+126, model 48.7%)
  - ATL @ STL OVER_8.5 (-110, model 61.2%)
- **3-leg @ +724 (prob 16.9%, EV +39.46%)**
  - KCR @ BAL KCR_ML (+126, model 48.7%)
  - HOU @ TEX OVER_9.0 (-110, model 56.8%)
  - ATL @ STL OVER_8.5 (-110, model 61.2%)
- **3-leg @ +538 (prob 21.8%, EV +39.18%)**
  - PHI @ DET DET_ML (-114, model 58.1%)
  - CHC @ CIN CHC_ML (-128, model 61.3%)
  - ATL @ STL OVER_8.5 (-110, model 61.2%)
- **3-leg @ +549 (prob 21.3%, EV +38.48%)**
  - HOU @ TEX OVER_9.0 (-110, model 56.8%)
  - CHC @ CIN CHC_ML (-128, model 61.3%)
  - ATL @ STL OVER_8.5 (-110, model 61.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6803. Wins: 2851. Hit rate: 41.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ LAD | 60.1% | -151 | 2.61 | -400 | +400 |
| ATL @ STL | 40.8% | +145 | 4.45 | +288 | -288 |
| CHC @ CIN | 48.8% | +105 | 3.61 | +254 | -254 |
| HOU @ TEX | 45.1% | +122 | 3.98 | +132 | -132 |
| KCR @ BAL | 31.5% | +218 | 5.69 | +157 | -157 |
| TOR @ SDP | 32.5% | +207 | 5.52 | +241 | -241 |

## Team Form (last 10)

**Hot:** DET 9-1 (W6, +34), COL 6-4 (W1, +18), MIA 7-3 (L1, +17), BOS 8-2 (W7, +17), STL 5-5 (W1, +14)

**Cold:** ATH 1-9 (L8, -39), SD 3-7 (L2, -29), SF 4-6 (L1, -17), PHI 5-5 (L1, -15), NYM 5-5 (L1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 14.4 IP across 3 games
- PIT: 9.3 IP across 2 games
- SD: 8.3 IP across 2 games
- STL: 9.3 IP across 2 games
- TB: 9.4 IP across 2 games
- MIN: 10.0 IP across 3 games
- ATL: 9.3 IP across 2 games
- CWS: 12.5 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-11._