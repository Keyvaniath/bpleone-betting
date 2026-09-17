# EdgeStat Daily Brief - 2026-09-17

**Model Confidence: 21.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-17T00:12:11 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**SDP @ COL - OVER_8.5**
- Market: -110
- Model probability: 93.5%
- Raw edge: +78.57%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | MIL @ PIT | PNC Park | 82F 9mph | OVER_8.5 +31.82% |
| 12:40p ET | LAD @ CIN | Great American Ball Park | 93F 9mph | OVER_8.5 +77.96% |
| 1:10p ET | OAK @ TBR | Tropicana Field | indoor | TBR_ML +64.35% |
| 3:10p ET | SDP @ COL | Coors Field | 82F 11mph | OVER_8.5 +78.57% |
| 7:15p ET | KCR @ HOU | Daikin Park | indoor | OVER_8.5 +19.83% |
| 7:15p ET | PHI @ NYM | Citi Field | 74F 8mph | NYM_ML +12.29% |
| 7:40p ET | DET @ CHW | Rate Field | 68F 7mph | OVER_8.5 +27.59% |
| 8:05p ET | BOS @ TEX | Globe Life Field | indoor | BOS_ML +25.2% |
| 9:38p ET | MIN @ LAA | Angel Stadium | 72F 6mph | MIN_ML +10.15% |

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

Cumulative graded plays: 11151. Wins: 4184. Hit rate: 37.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ TEX | 46.1% | +117 | 3.87 | +291 | -291 |
| DET @ CHW | 53.5% | -115 | 2.99 | +251 | -251 |
| KCR @ HOU | 26.5% | +277 | 6.64 | +140 | -140 |
| LAD @ CIN | 18.2% | +448 | 8.99 | +826 | -826 |
| MIL @ PIT | 27.2% | +267 | 6.78 | +249 | -249 |
| MIN @ LAA | 53.0% | -113 | 3.26 | +214 | -214 |
| OAK @ TBR | 45.7% | +119 | 3.91 | -352 | +352 |
| PHI @ NYM | 50.5% | -102 | 3.57 | +120 | -120 |
| SDP @ COL | 32.7% | +206 | 5.94 | +175 | -175 |

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
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-16._