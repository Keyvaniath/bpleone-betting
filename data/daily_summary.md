# EdgeStat Daily Brief - 2026-07-30

**Model Confidence: 22.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-07-30T07:28:32 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ ATL - OVER_9.5**
- Market: -110
- Model probability: 73.2%
- Raw edge: +39.75%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:10p ET | TEX @ TBR | Tropicana Field | indoor | OVER_7.5 +16.39% |
| 1:40p ET | KCR @ MIN | Target Field | 88F 8mph | OVER_9.5 +31.64% |
| 2:10p ET | NYY @ CHW | Rate Field | 77F 8mph | OVER_7.5 +33.62% |
| 2:15p ET | CHC @ STL | Busch Stadium | 91F 5mph | OVER_8.5 +36.28% |
| 7:10p ET | PIT @ CIN | Great American Ball Park | 75F 4mph | PIT_ML +35.39% |
| 7:10p ET | MIA @ NYM | Citi Field | 71F 4mph | MIA_ML +14.87% |
| 7:15p ET | WSN @ ATL | Truist Park | 75F 4mph | OVER_9.5 +39.75% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 75F 6mph | BOS_ML +16.64% |
| 9:40p ET | SFG @ SDP | Petco Park | 68F 2mph | SFG_ML +30.42% |
| 10:10p ET | SEA @ LAD | UNIQLO Field at Dodger Stadium | 66F 2mph | -- |

## Parlays - top 5

- **3-leg @ +492 (prob 25.2%, EV +49.5%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - MIA @ NYM OVER_7.0 (-110, model 57.7%)
  - BOS @ OAK BOS_ML (-160, model 71.8%)
- **3-leg @ +413 (prob 29.1%, EV +49.45%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - TEX @ TBR TBR_ML (-153, model 66.6%)
  - BOS @ OAK BOS_ML (-160, model 71.8%)
- **3-leg @ +539 (prob 23.1%, EV +47.54%)**
  - MIA @ NYM MIA_ML (+106, model 55.8%)
  - MIA @ NYM OVER_7.0 (-110, model 57.7%)
  - BOS @ OAK BOS_ML (-160, model 71.8%)
- **3-leg @ +454 (prob 26.6%, EV +47.49%)**
  - TEX @ TBR TBR_ML (-153, model 66.6%)
  - MIA @ NYM MIA_ML (+106, model 55.8%)
  - BOS @ OAK BOS_ML (-160, model 71.8%)
- **3-leg @ +651 (prob 19.6%, EV +47.23%)**
  - TEX @ TBR OVER_7.5 (-110, model 61.0%)
  - MIA @ NYM MIA_ML (+106, model 55.8%)
  - MIA @ NYM OVER_7.0 (-110, model 57.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6706. Wins: 2788. Hit rate: 41.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ OAK | 45.5% | +120 | 4.01 | +426 | -426 |
| CHC @ STL | 47.8% | +109 | 3.66 | +221 | -221 |
| KCR @ MIN | 33.3% | +200 | 5.67 | +144 | -144 |
| MIA @ NYM | 60.4% | -153 | 2.56 | +226 | -226 |
| NYY @ CHW | 47.9% | +109 | 3.65 | +179 | -179 |
| PIT @ CIN | 32.6% | +206 | 5.66 | +450 | -450 |
| SEA @ LAD | 41.7% | +140 | 4.43 | +114 | -114 |
| SFG @ SDP | 47.2% | +112 | 3.76 | +292 | -292 |
| TEX @ TBR | 23.5% | +325 | 7.23 | -114 | +114 |
| WSN @ ATL | 36.4% | +175 | 4.96 | +251 | -251 |

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