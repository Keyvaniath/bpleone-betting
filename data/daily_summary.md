# EdgeStat Daily Brief - 2026-07-30

**Model Confidence: 22.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-07-30T15:10:29 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ STL - OVER_8.0**
- Market: -110
- Model probability: 77.9%
- Raw edge: +48.77%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:10p ET | TEX @ TBR | Tropicana Field | indoor | OVER_7.5 +16.39% |
| 1:40p ET | KCR @ MIN | Target Field | 91F 9mph | OVER_9.0 +44.84% |
| 2:10p ET | NYY @ CHW | Rate Field | 77F 8mph | OVER_7.5 +33.62% |
| 2:15p ET | CHC @ STL | Busch Stadium | 91F 7mph | OVER_8.0 +48.77% |
| 7:10p ET | PIT @ CIN | Great American Ball Park | 75F 5mph | OVER_9.5 +36.09% |
| 7:10p ET | MIA @ NYM | Citi Field | 70F 4mph | MIA_ML +15.97% |
| 7:15p ET | WSN @ ATL | Truist Park | 74F 4mph | WSN_ML +36.94% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 80F 7mph | OVER_10.0 +21.14% |
| 9:40p ET | SFG @ SDP | Petco Park | 69F 3mph | SFG_ML +43.69% |
| 10:10p ET | SEA @ LAD | UNIQLO Field at Dodger Stadium | 67F 2mph | -- |

## Parlays - top 5

- **3-leg @ +518 (prob 24.2%, EV +49.37%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - MIA @ NYM MIA_ML (+108, model 55.8%)
  - BOS @ OAK BOS_ML (-180, model 71.1%)
- **3-leg @ +658 (prob 19.5%, EV +47.68%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - MIA @ NYM MIA_ML (+108, model 55.8%)
  - MIA @ NYM OVER_7.0 (-110, model 57.3%)
- **3-leg @ +488 (prob 24.9%, EV +46.19%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - CHC @ STL CHC_ML (-102, model 57.3%)
  - BOS @ OAK BOS_ML (-180, model 71.1%)
- **3-leg @ +541 (prob 22.7%, EV +45.64%)**
  - CHC @ STL CHC_ML (-102, model 57.3%)
  - MIA @ NYM MIA_ML (+108, model 55.8%)
  - BOS @ OAK BOS_ML (-180, model 71.1%)
- **3-leg @ +622 (prob 20.0%, EV +44.54%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - CHC @ STL CHC_ML (-102, model 57.3%)
  - MIA @ NYM OVER_7.0 (-110, model 57.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6707. Wins: 2788. Hit rate: 41.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ OAK | 45.5% | +120 | 4.07 | +428 | -428 |
| CHC @ STL | 47.8% | +109 | 3.57 | +221 | -221 |
| KCR @ MIN | 33.3% | +200 | 5.65 | +144 | -144 |
| MIA @ NYM | 60.4% | -153 | 2.51 | +226 | -226 |
| NYY @ CHW | 47.9% | +109 | 3.64 | +179 | -179 |
| PIT @ CIN | 32.6% | +206 | 5.76 | +451 | -451 |
| SEA @ LAD | 41.7% | +140 | 4.42 | +114 | -114 |
| SFG @ SDP | 47.2% | +112 | 3.71 | +292 | -292 |
| TEX @ TBR | 23.5% | +325 | 7.23 | -114 | +114 |
| WSN @ ATL | 36.4% | +175 | 5.0 | +251 | -251 |

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +34), SD 7-3 (W5, +31), TB 7-3 (W1, +23), WSH 6-4 (L1, +16), NYM 5-5 (W1, +16)

**Cold:** COL 3-7 (L4, -19), ATH 3-7 (L1, -17), STL 3-7 (W1, -16), MIA 3-7 (W3, -15), MIN 5-5 (L1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 10.3 IP across 2 games
- SD: 8.4 IP across 2 games
- SF: 8.1 IP across 2 games
- STL: 12.1 IP across 2 games
- TB: 9.5 IP across 2 games
- TOR: 8.5 IP across 2 games
- CWS: 8.5 IP across 2 games
- BAL: 8.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-30._