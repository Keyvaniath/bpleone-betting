# EdgeStat Daily Brief - 2026-07-15

**Model Confidence: 22.2/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-07-15T21:50:45 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CIN @ COL - CIN_ML**
- Market: -110
- Model probability: 73.7%
- Raw edge: +40.74%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | SDP @ LAD | Petco Park | 62F -6mph | LAD_ML +25.43% |
| 6:45p ET | BOS @ NYY | Yankee Stadium | 71F 12mph | OVER_9.0 +30.97% |
| 9:40p ET | CIN @ COL | Coors Field | 74F 4mph | CIN_ML +40.74% |

## Parlays - top 5

- **2-leg @ +284 (prob 38.1%, EV +46.11%)**
  - Juan Soto OVER 1.5 batter_total_bases (+101, model 61.0%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **2-leg @ +354 (prob 30.7%, EV +39.49%)**
  - Carson Benge OVER 1.5 batter_total_bases (+138, model 49.2%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **2-leg @ +289 (prob 35.5%, EV +38.3%)**
  - Kyle Schwarber OVER 1.5 batter_total_bases (+104, model 56.9%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **2-leg @ +373 (prob 28.8%, EV +36.48%)**
  - Jorge Polanco UNDER 0.5 batter_hits (+148, model 46.2%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **2-leg @ +301 (prob 33.6%, EV +34.69%)**
  - Brandon Marsh OVER 1.5 batter_total_bases (+110, model 53.8%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6251. Wins: 2506. Hit rate: 40.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | -- | -- | -- | +115 | -115 |
| CIN @ COL | -- | -- | -- | +465 | -465 |
| SDP @ LAD | -- | -- | -- | -166 | +166 |

## Team Form (last 10)

**Hot:** BOS 9-1 (W9, +26), PIT 7-3 (W3, +24), BAL 7-3 (W4, +19), MIN 7-3 (W2, +17), DET 7-3 (L2, +17)

**Cold:** ATH 1-9 (L9, -41), PHI 5-5 (W2, -20), NYM 4-6 (L3, -16), TEX 5-5 (W1, -12), LAA 2-8 (L2, -10)

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-14._