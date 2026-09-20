# EdgeStat Daily Brief - 2026-09-20

**Model Confidence: 21.3/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-20T23:56:56 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

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

- **2-leg @ +402 (prob 29.9%, EV +49.92%)**
  - Carter Jensen UNDER 0.5 batter_hits (+151, model 47.8%)
  - MIN @ LAA MIN_ML (+100, model 62.5%)
- **2-leg @ +282 (prob 39.1%, EV +49.17%)**
  - MIN @ LAA MIN_ML (+100, model 62.5%)
  - NYY @ ARI OVER_8.5 (-110, model 62.5%)
- **2-leg @ +442 (prob 27.5%, EV +49.12%)**
  - Trea Turner UNDER 0.5 batter_hits (+184, model 42.9%)
  - DET @ CHW OVER_8.5 (-110, model 64.1%)
- **2-leg @ +264 (prob 40.5%, EV +47.46%)**
  - OAK @ CLE CLE_ML (-110, model 63.1%)
  - DET @ CHW OVER_8.5 (-110, model 64.1%)
- **2-leg @ +422 (prob 28.2%, EV +47.05%)**
  - Francisco Lindor UNDER 0.5 batter_hits (+161, model 45.1%)
  - MIN @ LAA MIN_ML (+100, model 62.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 298 | 52.0% | 55.4% | 1.065 | 0.940 |
| batter total bases | 129 | 45.0% | 47.2% | 1.049 | 0.955 |

Cumulative graded plays: 11898. Wins: 4603. Hit rate: 38.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | -- | -- | -- | +115 | -115 |
| CIN @ COL | -- | -- | -- | +465 | -465 |
| SDP @ LAD | -- | -- | -- | -166 | +166 |

## Team Form (last 10)

**Hot:** LAD 7-3 (W3, +35), MIL 8-2 (W2, +30), SD 9-1 (W4, +27), TB 8-2 (W1, +26), DET 7-3 (L1, +25)

**Cold:** CIN 3-7 (L1, -46), ATH 3-7 (L5, -35), COL 2-8 (W1, -29), MIN 3-7 (L1, -24), HOU 3-7 (L2, -20)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.3 IP across 2 games
- SD: 8.9 IP across 2 games
- STL: 11.6 IP across 2 games
- TEX: 11.4 IP across 2 games
- PHI: 9.4 IP across 2 games
- MIA: 8.3 IP across 2 games
- MIL: 9.2 IP across 2 games
- LAA: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-20._