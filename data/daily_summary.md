# EdgeStat Daily Brief - 2026-09-14

**Model Confidence: 20.3/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-14T00:03:28 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ CIN - LAD_ML**
- Market: +100
- Model probability: 89.7%
- Raw edge: +79.39%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | LAD @ CIN | Great American Ball Park | 66F 6mph | LAD_ML +79.39% |
| 6:40p ET | CHW @ CLE | Progressive Field | 59F 3mph | CHW_ML +34.1% |
| 7:07p ET | DET @ TOR | Rogers Centre | indoor | DET_ML +10.81% |
| 7:10p ET | BAL @ NYM | Citi Field | 58F 7mph | BAL_ML +2.22% |
| 7:40p ET | ATL @ CHC | Wrigley Field | 66F 15mph | OVER_8.5 +49.21% |
| 7:40p ET | NYY @ MIN | Target Field | 59F 6mph | NYY_ML +33.64% |
| 7:45p ET | SFG @ STL | Busch Stadium | 78F 10mph | SFG_ML +10.01% |
| 8:40p ET | SDP @ COL | Coors Field | 70F 0mph | OVER_8.5 +66.15% |
| 9:38p ET | SEA @ LAA | Angel Stadium | 70F 0mph | UNDER_8.5 +23.51% |
| 9:40p ET | MIA @ ARI | Chase Field | indoor | MIA_ML +5.9% |

## Parlays - top 5

- **2-leg @ +454 (prob 26.0%, EV +44.14%)**
  - Gleyber Torres UNDER 0.5 batter_hits (+190, model 40.0%)
  - CHW @ STL OVER_8.5 (-110, model 65.1%)
- **2-leg @ +456 (prob 25.9%, EV +44.13%)**
  - Ronald Acuna Jr. UNDER 0.5 batter_hits (+191, model 39.8%)
  - CHW @ STL OVER_8.5 (-110, model 65.1%)
- **2-leg @ +264 (prob 39.0%, EV +42.17%)**
  - CIN @ MIL OVER_8.5 (-110, model 59.9%)
  - CHW @ STL OVER_8.5 (-110, model 65.1%)
- **2-leg @ +264 (prob 39.0%, EV +42.14%)**
  - CHW @ STL OVER_8.5 (-110, model 65.1%)
  - PIT @ CHC CHC_ML (-110, model 59.9%)
- **2-leg @ +454 (prob 25.7%, EV +42.01%)**
  - Gleyber Torres UNDER 0.5 batter_hits (+190, model 40.0%)
  - CIN @ MIL MIL_ML (-110, model 64.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 229 | 55.9% | 56.3% | 1.007 | 0.993 |
| batter total bases | 109 | 45.0% | 47.6% | 1.058 | 0.948 |

Cumulative graded plays: 11014. Wins: 4128. Hit rate: 37.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHC | -- | -- | -- | -107 | +107 |
| BAL @ NYM | -- | -- | -- | +180 | -180 |
| CHW @ CLE | -- | -- | -- | +380 | -380 |
| DET @ TOR | -- | -- | -- | +219 | -219 |
| LAD @ CIN | -- | -- | -- | +1583 | -1583 |
| MIA @ ARI | -- | -- | -- | +193 | -193 |
| NYY @ MIN | -- | -- | -- | +344 | -344 |
| SDP @ COL | -- | -- | -- | +342 | -342 |
| SEA @ LAA | -- | -- | -- | +103 | -103 |
| SFG @ STL | -- | -- | -- | +208 | -208 |

## Team Form (last 10)

**Hot:** MIL 7-3 (W5, +28), LAD 8-2 (L1, +24), DET 6-4 (W3, +21), NYM 7-3 (W1, +20), TOR 6-4 (W1, +17)

**Cold:** CIN 4-6 (L5, -33), COL 3-7 (L6, -19), WSH 3-7 (W2, -17), MIA 3-7 (W1, -11), PHI 3-7 (L3, -11)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.3 IP across 2 games
- SF: 10.1 IP across 2 games
- STL: 9.5 IP across 2 games
- TOR: 9.6 IP across 2 games
- CWS: 10.5 IP across 2 games
- MIL: 8.1 IP across 2 games
- CIN: 8.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-13._