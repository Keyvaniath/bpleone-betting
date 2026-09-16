# EdgeStat Daily Brief - 2026-09-16

**Model Confidence: 21.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-16T18:09:51 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ATL @ CHC - OVER_7.5**
- Market: -110
- Model probability: 87.5%
- Raw edge: +67.09%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (12 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 3:07p ET | DET @ TOR | Rogers Centre | indoor | DET_ML +43.4% |
| 6:40p ET | LAD @ CIN | Great American Ball Park | 79F 4mph | OVER_8.0 +53.72% |
| 6:40p ET | OAK @ TBR | Tropicana Field | indoor | OVER_8.0 +6.46% |
| 6:40p ET | MIL @ PIT | PNC Park | 77F 5mph | OVER_7.5 +27.26% |
| 6:45p ET | PHI @ WSN | Nationals Park | 74F 7mph | WSN_ML +55.07% |
| 7:10p ET | BAL @ NYM | Citi Field | 69F 4mph | UNDER_9.0 +22.15% |
| 7:40p ET | ATL @ CHC | Wrigley Field | 66F 5mph | OVER_7.5 +67.09% |
| 8:05p ET | BOS @ TEX | Globe Life Field | indoor | OVER_8.0 +8.37% |
| 8:10p ET | KCR @ HOU | Daikin Park | indoor | KCR_ML +22.28% |
| 8:40p ET | SDP @ COL | Coors Field | 70F 2mph | OVER_11.0 +51.46% |
| 9:38p ET | SEA @ LAA | Angel Stadium | 70F 4mph | UNDER_8.0 +7.2% |
| 9:40p ET | MIA @ ARI | Chase Field | indoor | MIA_ML +40.15% |

## Parlays - top 5

- **2-leg @ +356 (prob 32.7%, EV +49.37%)**
  - BAL @ NYM UNDER_9.0 (-110, model 64.0%)
  - KCR @ HOU KCR_ML (+139, model 51.2%)
- **2-leg @ +356 (prob 32.4%, EV +47.67%)**
  - DET @ TOR OVER_8.0 (-110, model 63.3%)
  - KCR @ HOU KCR_ML (+139, model 51.2%)
- **2-leg @ +264 (prob 40.5%, EV +47.53%)**
  - DET @ TOR OVER_8.0 (-110, model 63.3%)
  - BAL @ NYM UNDER_9.0 (-110, model 64.0%)
- **2-leg @ +543 (prob 22.5%, EV +44.49%)**
  - Jonah Cox UNDER 0.5 batter_hits (+169, model 43.9%)
  - KCR @ HOU KCR_ML (+139, model 51.2%)
- **2-leg @ +414 (prob 28.1%, EV +44.36%)**
  - Jonah Cox UNDER 0.5 batter_hits (+169, model 43.9%)
  - BAL @ NYM UNDER_9.0 (-110, model 64.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 113 | 44.2% | 47.0% | 1.063 | 0.944 |
| batter hits | 253 | 53.0% | 56.1% | 1.058 | 0.946 |

Cumulative graded plays: 11150. Wins: 4182. Hit rate: 37.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHC | 36.5% | +174 | 4.87 | -111 | +111 |
| BAL @ NYM | 28.3% | +253 | 6.46 | +140 | -140 |
| BOS @ TEX | 29.3% | +242 | 6.14 | +234 | -234 |
| DET @ TOR | 30.0% | +233 | 6.01 | +382 | -382 |
| KCR @ HOU | 36.0% | +178 | 5.11 | +175 | -175 |
| LAD @ CIN | 35.5% | +182 | 5.15 | +2370 | -2370 |
| MIA @ ARI | 40.7% | +146 | 4.49 | +317 | -317 |
| MIL @ PIT | 63.0% | -171 | 2.37 | +286 | -286 |
| OAK @ TBR | 62.8% | -169 | 2.32 | +110 | -110 |
| PHI @ WSN | 37.7% | +165 | 5.01 | +120 | -120 |
| SDP @ COL | 35.6% | +181 | 5.09 | +217 | -217 |
| SEA @ LAA | 39.7% | +152 | 4.74 | +218 | -218 |

## Team Form (last 10)

**Hot:** DET 8-2 (W6, +35), MIL 7-3 (W1, +28), LAD 8-2 (W2, +28), TB 8-2 (W4, +25), NYY 8-2 (W3, +23)

**Cold:** CIN 3-7 (L2, -41), MIN 3-7 (L3, -33), COL 2-8 (W1, -23), HOU 4-6 (W1, -13), ATH 6-4 (L1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TOR: 8.7 IP across 2 games
- ATL: 8.0 IP across 2 games
- CWS: 15.3 IP across 2 games
- MIA: 10.4 IP across 2 games
- AZ: 10.1 IP across 2 games
- BAL: 9.6 IP across 2 games
- COL: 8.3 IP across 2 games
- DET: 9.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-15._