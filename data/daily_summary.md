# EdgeStat Daily Brief - 2026-07-29

**Model Confidence: 22.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-29T23:02:27 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ STL - CHC_ML**
- Market: +101
- Model probability: 62.6%
- Raw edge: +25.77%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | ATL @ NYM | Citi Field | 69F 5mph | ATL_ML +10.1% |
| 7:10p ET | CLE @ CIN | Great American Ball Park | 70F 6mph | OVER_8.5 +17.47% |
| 7:40p ET | KCR @ MIN | Target Field | 81F 5mph | MIN_ML +24.3% |
| 7:40p ET | NYY @ CHW | Rate Field | 68F 6mph | NYY_ML +13.18% |
| 7:45p ET | CHC @ STL | Busch Stadium | 75F 4mph | CHC_ML +25.77% |
| 9:38p ET | HOU @ LAA | Angel Stadium | 69F 5mph | OVER_9.5 +17.25% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 75F 7mph | BOS_ML +24.34% |
| 10:10p ET | SEA @ LAD | UNIQLO Field at Dodger Stadium | 67F 3mph | OVER_8.5 +8.18% |

## Parlays - top 5

- **2-leg @ +227 (prob 45.2%, EV +48.09%)**
  - ARI @ PIT PIT_ML (-140, model 72.2%)
  - COL @ SDP UNDER_8.5 (-110, model 62.7%)
- **2-leg @ +226 (prob 45.2%, EV +47.29%)**
  - ARI @ PIT PIT_ML (-140, model 72.2%)
  - CHC @ STL CHC_ML (-111, model 62.6%)
- **2-leg @ +278 (prob 38.9%, EV +47.19%)**
  - TOR @ WSN WSN_ML (-102, model 62.1%)
  - COL @ SDP UNDER_8.5 (-110, model 62.7%)
- **2-leg @ +276 (prob 38.9%, EV +46.39%)**
  - TOR @ WSN WSN_ML (-102, model 62.1%)
  - CHC @ STL CHC_ML (-111, model 62.6%)
- **2-leg @ +183 (prob 51.4%, EV +45.7%)**
  - ARI @ PIT PIT_ML (-140, model 72.2%)
  - ATL @ NYM ATL_ML (-153, model 71.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6696. Wins: 2782. Hit rate: 41.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ NYM | 63.2% | -172 | 2.35 | +467 | -467 |
| BOS @ OAK | 37.4% | +168 | 5.0 | +557 | -557 |
| CHC @ STL | 42.1% | +137 | 4.25 | +294 | -294 |
| CLE @ CIN | 32.2% | +211 | 5.84 | +188 | -188 |
| HOU @ LAA | 22.8% | +338 | 7.57 | +329 | -329 |
| KCR @ MIN | 54.4% | -120 | 3.1 | -157 | +157 |
| NYY @ CHW | 42.0% | +138 | 4.17 | +249 | -249 |
| SEA @ LAD | 47.8% | +109 | 3.76 | +121 | -121 |

## Team Form (last 10)

**Hot:** CHC 7-3 (W2, +39), SD 6-4 (W4, +24), TB 6-4 (L1, +19), MIL 7-3 (W1, +18), NYM 5-5 (W2, +14)

**Cold:** COL 3-7 (L3, -22), TOR 3-7 (L1, -21), MIA 2-8 (W2, -19), STL 2-8 (L3, -18), MIN 5-5 (W3, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 11.5 IP across 2 games
- SEA: 8.0 IP across 2 games
- SF: 8.1 IP across 2 games
- STL: 12.2 IP across 2 games
- TOR: 11.8 IP across 2 games
- CWS: 8.4 IP across 2 games
- CIN: 10.4 IP across 2 games
- HOU: 12.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-29._