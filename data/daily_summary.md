# EdgeStat Daily Brief - 2026-09-14

**Model Confidence: 20.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-14T19:14:06 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ CIN - OVER_7.5**
- Market: -110
- Model probability: 88.1%
- Raw edge: +68.16%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | LAD @ CIN | Great American Ball Park | 66F 5mph | OVER_7.5 +68.16% |
| 6:40p ET | CHW @ CLE | Progressive Field | 59F 4mph | CHW_ML +45.88% |
| 7:07p ET | DET @ TOR | Rogers Centre | indoor | DET_ML +19.68% |
| 7:10p ET | BAL @ NYM | Citi Field | 61F 6mph | OVER_8.0 +9.26% |
| 7:40p ET | ATL @ CHC | Wrigley Field | 65F 10mph | OVER_9.5 +19.95% |
| 7:40p ET | NYY @ MIN | Target Field | 61F 4mph | OVER_8.0 +31.81% |
| 7:45p ET | SFG @ STL | Busch Stadium | 76F 9mph | SFG_ML +22.34% |
| 8:40p ET | SDP @ COL | Coors Field | 71F 5mph | OVER_11.0 +31.1% |
| 9:38p ET | SEA @ LAA | Angel Stadium | 68F 5mph | LAA_ML +22.05% |
| 9:40p ET | MIA @ ARI | Chase Field | indoor | MIA_ML +12.26% |

## Parlays - top 5

- **2-leg @ +326 (prob 35.1%, EV +49.31%)**
  - SFG @ STL SFG_ML (+122, model 55.1%)
  - SEA @ LAA LAA_ML (-109, model 63.6%)
- **2-leg @ +382 (prob 30.5%, EV +47.11%)**
  - DET @ TOR DET_ML (+117, model 55.4%)
  - SFG @ STL SFG_ML (+122, model 55.1%)
- **2-leg @ +316 (prob 35.3%, EV +46.75%)**
  - DET @ TOR DET_ML (+117, model 55.4%)
  - SEA @ LAA LAA_ML (-109, model 63.6%)
- **2-leg @ +324 (prob 34.6%, EV +46.75%)**
  - ATL @ CHC OVER_9.5 (-110, model 62.8%)
  - SFG @ STL SFG_ML (+122, model 55.1%)
- **2-leg @ +266 (prob 40.0%, EV +46.39%)**
  - ATL @ CHC OVER_9.5 (-110, model 62.8%)
  - SEA @ LAA LAA_ML (-109, model 63.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 114 | 46.5% | 47.7% | 1.027 | 0.975 |
| batter hits | 247 | 56.3% | 56.4% | 1.002 | 0.998 |

Cumulative graded plays: 11105. Wins: 4167. Hit rate: 37.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHC | 26.0% | +284 | 6.97 | -105 | +105 |
| BAL @ NYM | 32.9% | +204 | 5.34 | +180 | -180 |
| CHW @ CLE | 65.8% | -192 | 2.09 | +307 | -307 |
| DET @ TOR | 37.9% | +164 | 4.85 | +219 | -219 |
| LAD @ CIN | 36.6% | +173 | 5.01 | +1570 | -1570 |
| MIA @ ARI | 29.9% | +234 | 6.03 | +193 | -193 |
| NYY @ MIN | 34.2% | +192 | 5.44 | +344 | -344 |
| SDP @ COL | 20.9% | +379 | 7.99 | +332 | -332 |
| SEA @ LAA | 50.7% | -103 | 3.47 | +101 | -101 |
| SFG @ STL | 56.5% | -130 | 2.83 | +210 | -210 |

## Travel / Rest Flags

- **SFG @ STL** (away): travel + back-to-back (+2h tz shift)
- **SDP @ COL** (home): travel + back-to-back (-2h tz shift)
- **SEA @ LAA** (home): travel + back-to-back (-3h tz shift)
- **MIA @ ARI** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** LAD 8-2 (L2, +24), MIL 6-4 (L1, +23), DET 6-4 (W4, +23), NYM 7-3 (L1, +22), TB 7-3 (W3, +18)

**Cold:** CIN 4-6 (W1, -33), MIN 3-7 (L1, -29), COL 2-8 (L7, -28), WSH 3-7 (W3, -20), BAL 3-7 (L2, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 10.7 IP across 2 games
- SF: 8.1 IP across 2 games
- STL: 8.3 IP across 2 games
- TOR: 8.9 IP across 2 games
- MIN: 8.2 IP across 2 games
- CWS: 8.6 IP across 2 games
- MIA: 8.4 IP across 2 games
- MIL: 8.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.3**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-14._