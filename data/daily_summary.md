# EdgeStat Daily Brief - 2026-07-30

**Model Confidence: 22.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-07-30T23:07:11 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PIT @ CIN - OVER_7.5**
- Market: -110
- Model probability: 88.5%
- Raw edge: +68.96%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | PIT @ CIN | Great American Ball Park | 74F 5mph | OVER_7.5 +68.96% |
| 7:15p ET | WSN @ ATL | Truist Park | 75F 4mph | OVER_9.0 +48.68% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 74F 6mph | OVER_10.0 +14.47% |
| 9:40p ET | SFG @ SDP | Petco Park | 68F 4mph | SFG_ML +51.25% |
| 10:10p ET | SEA @ LAD | UNIQLO Field at Dodger Stadium | 67F 2mph | -- |

## Parlays - top 5

- **3-leg @ +679 (prob 19.1%, EV +48.98%)**
  - CHC @ STL CHC_ML (-103, model 57.3%)
  - MIA @ NYM MIA_ML (+107, model 55.7%)
  - SEA @ LAD UNDER_9.0 (-110, model 59.9%)
- **3-leg @ +512 (prob 23.8%, EV +45.46%)**
  - MIA @ NYM MIA_ML (+107, model 55.7%)
  - BOS @ OAK BOS_ML (-182, model 71.1%)
  - SEA @ LAD UNDER_9.0 (-110, model 59.9%)
- **3-leg @ +532 (prob 22.7%, EV +43.58%)**
  - CHC @ STL CHC_ML (-103, model 57.3%)
  - MIA @ NYM MIA_ML (+107, model 55.7%)
  - BOS @ OAK BOS_ML (-182, model 71.1%)
- **3-leg @ +654 (prob 19.0%, EV +43.45%)**
  - MIA @ NYM MIA_ML (+107, model 55.7%)
  - MIA @ NYM OVER_7.0 (-110, model 56.9%)
  - SEA @ LAD UNDER_9.0 (-110, model 59.9%)
- **3-leg @ +483 (prob 24.4%, EV +42.32%)**
  - CHC @ STL CHC_ML (-103, model 57.3%)
  - BOS @ OAK BOS_ML (-182, model 71.1%)
  - SEA @ LAD UNDER_9.0 (-110, model 59.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6709. Wins: 2790. Hit rate: 41.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ OAK | 45.5% | +120 | 4.0 | +425 | -425 |
| PIT @ CIN | 32.6% | +206 | 5.72 | +451 | -451 |
| SEA @ LAD | 41.7% | +140 | 4.43 | +114 | -114 |
| SFG @ SDP | 47.2% | +112 | 3.7 | +292 | -292 |
| WSN @ ATL | 36.4% | +175 | 5.01 | +251 | -251 |

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