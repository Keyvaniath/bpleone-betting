# EdgeStat Daily Brief - 2026-08-13

**Model Confidence: 21.7/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-13T06:15:58 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**BOS @ TOR - BOS_ML**
- Market: +100
- Model probability: 85.0%
- Raw edge: +69.91%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | CLE @ DET | Comerica Park | 85F 7mph | DET_ML +17.62% |
| 1:10p ET | PIT @ MIA | loanDepot park | indoor | PIT_ML +13.65% |
| 1:35p ET | SEA @ NYY | Yankee Stadium | 86F 12mph | NYY_ML +44.43% |
| 2:10p ET | CIN @ CHW | Rate Field | 75F 2mph | CHW_ML +37.15% |
| 3:07p ET | BOS @ TOR | Rogers Centre | indoor | BOS_ML +69.91% |
| 4:05p ET | CHC @ WSN | Nationals Park | 86F 4mph | OVER_8.5 +53.18% |
| 7:30p ET | PHI @ MIN | Field of Dreams | 70F 0mph | MIN_ML +21.65% |
| 10:07p ET | TEX @ LAA | Angel Stadium | 69F 4mph | TEX_ML +22.62% |
| 10:10p ET | MIL @ LAD | UNIQLO Field at Dodger Stadium | 68F 3mph | OVER_8.5 +14.74% |

## Parlays - top 5

- **2-leg @ +288 (prob 38.6%, EV +49.63%)**
  - CIN @ CHW CHW_ML (-137, model 71.8%)
  - MIL @ LAD MIL_ML (+124, model 53.8%)
- **2-leg @ +258 (prob 41.7%, EV +49.44%)**
  - BOS @ TOR OVER_8.0 (-110, model 65.4%)
  - PHI @ MIN MIN_ML (-114, model 63.7%)
- **2-leg @ +230 (prob 45.3%, EV +49.37%)**
  - Taj Bradley OVER 5.5 pitcher_strikeouts (-132, model 71.0%)
  - PHI @ MIN MIN_ML (-114, model 63.7%)
- **2-leg @ +264 (prob 40.9%, EV +49.21%)**
  - BOS @ TOR OVER_8.0 (-110, model 65.4%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
- **2-leg @ +236 (prob 44.5%, EV +49.14%)**
  - Taj Bradley OVER 5.5 pitcher_strikeouts (-132, model 71.0%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8245. Wins: 3247. Hit rate: 39.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ TOR | 36.5% | +174 | 5.04 | +1053 | -1053 |
| CHC @ WSN | 46.2% | +117 | 3.77 | +161 | -161 |
| CIN @ CHW | 26.9% | +272 | 6.52 | -150 | +150 |
| CLE @ DET | 49.2% | +103 | 3.38 | +110 | -110 |
| MIL @ LAD | 38.4% | +161 | 4.86 | +196 | -196 |
| PHI @ MIN | 40.1% | +150 | 4.57 | -105 | +105 |
| PIT @ MIA | 43.4% | +130 | 4.17 | +225 | -225 |
| SEA @ NYY | 46.5% | +115 | 4.03 | -175 | +175 |
| TEX @ LAA | 50.4% | -102 | 3.52 | +284 | -284 |

## Team Form (last 10)

**Hot:** DET 7-3 (L1, +37), CHC 8-2 (W3, +25), TB 9-1 (W9, +23), BOS 5-5 (L5, +23), STL 7-3 (W2, +19)

**Cold:** ATH 2-8 (L3, -37), SEA 3-7 (L6, -28), PIT 2-8 (L3, -25), LAA 5-5 (W2, -13), LAD 4-6 (W3, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.0 IP across 2 games
- PIT: 8.2 IP across 2 games
- SD: 10.0 IP across 2 games
- CIN: 8.2 IP across 2 games
- HOU: 9.7 IP across 2 games
- WSH: 9.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.1**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-12._