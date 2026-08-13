# EdgeStat Daily Brief - 2026-08-13

**Model Confidence: 22.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-13T14:16:27 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ WSN - OVER_9.0**
- Market: -110
- Model probability: 75.2%
- Raw edge: +43.62%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | CLE @ DET | Comerica Park | 88F 7mph | DET_ML +26.42% |
| 1:10p ET | PIT @ MIA | loanDepot park | indoor | OVER_8.0 +21.12% |
| 1:35p ET | SEA @ NYY | Yankee Stadium | 87F 9mph | NYY_ML +26.42% |
| 2:10p ET | CIN @ CHW | Rate Field | 74F 3mph | CHW_ML +24.75% |
| 3:07p ET | BOS @ TOR | Rogers Centre | indoor | BOS_ML +37.39% |
| 4:05p ET | CHC @ WSN | Nationals Park | 86F 4mph | OVER_9.0 +43.62% |
| 7:30p ET | PHI @ MIN | Field of Dreams | 70F 0mph | MIN_ML +22.18% |
| 10:07p ET | TEX @ LAA | Angel Stadium | 69F 4mph | OVER_7.5 +2.58% |
| 10:10p ET | MIL @ LAD | UNIQLO Field at Dodger Stadium | 68F 3mph | MIL_ML +20.39% |

## Parlays - top 5

- **3-leg @ +871 (prob 15.4%, EV +49.87%)**
  - SEA @ NYY OVER_7.5 (-110, model 57.6%)
  - CHC @ WSN WSN_ML (+127, model 49.9%)
  - MIL @ LAD MIL_ML (+124, model 53.8%)
- **2-leg @ +264 (prob 40.9%, EV +49.21%)**
  - BOS @ TOR OVER_8.0 (-110, model 65.4%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
- **2-leg @ +231 (prob 45.0%, EV +48.99%)**
  - CIN @ CHW CHW_ML (-136, model 71.9%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
- **3-leg @ +727 (prob 18.0%, EV +48.66%)**
  - SEA @ NYY OVER_7.5 (-110, model 57.6%)
  - CHC @ WSN WSN_ML (+127, model 49.9%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
- **3-leg @ +596 (prob 21.3%, EV +48.03%)**
  - SEA @ NYY OVER_7.5 (-110, model 57.6%)
  - CIN @ CHW OVER_8.5 (-110, model 61.5%)
  - MIL @ LAD OVER_8.5 (-110, model 60.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8404. Wins: 3291. Hit rate: 39.2%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ TOR | 36.5% | +174 | 5.04 | +1053 | -1053 |
| CHC @ WSN | 46.2% | +117 | 3.78 | +161 | -161 |
| CIN @ CHW | 26.9% | +272 | 6.47 | -151 | +151 |
| CLE @ DET | 49.2% | +103 | 3.61 | +110 | -110 |
| MIL @ LAD | 38.4% | +161 | 4.89 | +196 | -196 |
| PHI @ MIN | 40.1% | +150 | 4.57 | -105 | +105 |
| PIT @ MIA | 43.4% | +130 | 4.17 | +225 | -225 |
| SEA @ NYY | 46.5% | +115 | 3.97 | -172 | +172 |
| TEX @ LAA | 50.4% | -102 | 3.49 | +284 | -284 |

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

- Confidence delta: **+1.2**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-12._