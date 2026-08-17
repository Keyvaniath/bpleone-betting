# EdgeStat Daily Brief - 2026-08-17

**Model Confidence: 27.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-08-17T22:29:45 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ COL - LAD_ML**
- Market: -174
- Model probability: 94.9%
- Raw edge: +49.38%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | STL @ CIN | Great American Ball Park | 73F 4mph | STL_ML +8.02% |
| 6:40p ET | MIA @ PHI | Citizens Bank Park | 78F 4mph | MIA_ML +20.55% |
| 7:05p ET | DET @ PIT | PNC Park | 71F 4mph | OVER_8.0 +17.93% |
| 7:10p ET | ARI @ BOS | Fenway Park | 70F 3mph | OVER_8.5 +20.01% |
| 7:10p ET | SDP @ NYM | Citi Field | 71F 3mph | UNDER_8.5 +24.13% |
| 7:40p ET | OAK @ KCR | Kauffman Stadium | 78F 6mph | OVER_10.0 +34.4% |
| 7:40p ET | ATL @ MIN | Target Field | 73F 5mph | OVER_8.5 +37.93% |
| 8:05p ET | CHW @ CHC | Wrigley Field | 66F 5mph | OVER_10.0 +9.35% |
| 8:40p ET | LAD @ COL | Coors Field | 79F 2mph | LAD_ML +49.38% |

## Parlays - top 5

- **2-leg @ +492 (prob 25.3%, EV +49.98%)**
  - STL @ CIN OVER_9.0 (-110, model 63.1%)
  - MIA @ PHI MIA_ML (+210, model 40.2%)
- **2-leg @ +264 (prob 41.1%, EV +49.8%)**
  - STL @ CIN OVER_9.0 (-110, model 64.8%)
  - LAD @ COL OVER_11.0 (-110, model 63.4%)
- **2-leg @ +228 (prob 45.2%, EV +48.28%)**
  - ARI @ BOS BOS_ML (-139, model 71.2%)
  - LAD @ COL OVER_11.0 (-110, model 63.4%)
- **2-leg @ +264 (prob 40.6%, EV +47.91%)**
  - STL @ CIN OVER_9.0 (-110, model 64.8%)
  - MIA @ PHI OVER_8.0 (-110, model 62.6%)
- **2-leg @ +228 (prob 44.9%, EV +47.51%)**
  - STL @ CIN OVER_9.0 (-110, model 63.1%)
  - ARI @ BOS BOS_ML (-139, model 71.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 11 | 45.5% | 52.1% | 1.132 | 0.924 |
| batter hits | 34 | 58.8% | 58.3% | 0.991 | 1.008 |

Cumulative graded plays: 8778. Wins: 3300. Hit rate: 37.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ BOS | 65.9% | -193 | 2.05 | -147 | +147 |
| ATL @ MIN | 51.1% | -105 | 3.42 | +281 | -281 |
| CHW @ CHC | 35.6% | +181 | 5.35 | +130 | -130 |
| DET @ PIT | 43.4% | +130 | 4.27 | +154 | -154 |
| LAD @ COL | 31.5% | +217 | 5.76 | +3511 | -3511 |
| MIA @ PHI | 58.4% | -140 | 2.75 | +114 | -114 |
| OAK @ KCR | 31.0% | +223 | 5.72 | -151 | +151 |
| SDP @ NYM | 44.1% | +127 | 4.02 | +145 | -145 |
| STL @ CIN | 45.8% | +119 | 4.02 | +237 | -237 |

## Travel / Rest Flags

- **OAK @ KCR** (home): travel + back-to-back (+2h tz shift)
- **OAK @ KCR** (away): travel + back-to-back (+2h tz shift)

## Team Form (last 10)

**Hot:** SD 8-2 (W1, +20), STL 7-3 (W2, +19), TB 7-3 (L3, +15), DET 5-5 (L3, +14), MIA 6-4 (W2, +12)

**Cold:** CIN 4-6 (L2, -25), SEA 3-7 (W2, -20), ATH 4-6 (W1, -18), SF 3-7 (L1, -17), TEX 4-6 (L1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 10.0 IP across 2 games
- SD: 10.0 IP across 2 games
- TOR: 10.5 IP across 2 games
- ATL: 8.1 IP across 2 games
- COL: 9.1 IP across 2 games
- DET: 8.2 IP across 2 games
- HOU: 9.0 IP across 2 games
- WSH: 9.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-17._