# EdgeStat Daily Brief - 2026-08-01

**Model Confidence: 22.2/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-01T22:58:28 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ ATL - OVER_8.5**
- Market: -110
- Model probability: 91.5%
- Raw edge: +74.68%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | PHI @ BAL | Oriole Park at Camden Yards | 77F 4mph | OVER_7.5 +7.96% |
| 7:10p ET | TEX @ HOU | Daikin Park | indoor | TEX_ML +63.19% |
| 7:15p ET | ARI @ CLE | Progressive Field | 76F 3mph | CLE_ML +9.34% |
| 7:15p ET | WSN @ ATL | Truist Park | 79F 7mph | OVER_8.5 +74.68% |
| 7:15p ET | NYY @ CHC | Wrigley Field | 69F 14mph | OVER_6.5 +55.85% |
| 8:10p ET | KCR @ COL | Coors Field | 78F 6mph | OVER_12.5 +38.34% |
| 8:40p ET | SFG @ SDP | Petco Park | 70F 2mph | SFG_ML +22.12% |
| 9:10p ET | BOS @ LAD | UNIQLO Field at Dodger Stadium | 68F 3mph | UNDER_9.0 +15.36% |
| 9:38p ET | MIL @ LAA | Angel Stadium | 72F 3mph | OVER_7.5 +31.13% |
| 9:40p ET | DET @ OAK | Sutter Health Park | 80F 5mph | DET_ML +20.31% |

## Parlays - top 5

- **3-leg @ +625 (prob 20.6%, EV +49.59%)**
  - ARI @ CLE CLE_ML (-147, model 65.1%)
  - KCR @ COL KCR_ML (-105, model 57.4%)
  - SFG @ SDP SFG_ML (+121, model 55.3%)
- **3-leg @ +507 (prob 24.6%, EV +49.59%)**
  - ARI @ CLE CLE_ML (-147, model 65.1%)
  - BOS @ LAD UNDER_9.0 (-110, model 60.0%)
  - DET @ OAK DET_ML (-112, model 63.1%)
- **3-leg @ +934 (prob 14.4%, EV +49.07%)**
  - SFG @ SDP SFG_ML (+121, model 55.3%)
  - BOS @ LAD LAD_ML (-163, model 66.8%)
  - MIL @ LAA LAA_ML (+190, model 39.0%)
- **3-leg @ +724 (prob 18.1%, EV +48.98%)**
  - PHI @ BAL OVER_7.5 (-110, model 57.0%)
  - KCR @ COL KCR_ML (-105, model 57.4%)
  - SFG @ SDP SFG_ML (+121, model 55.3%)
- **3-leg @ +590 (prob 21.6%, EV +48.98%)**
  - PHI @ BAL OVER_7.5 (-110, model 57.0%)
  - BOS @ LAD UNDER_9.0 (-110, model 60.0%)
  - DET @ OAK DET_ML (-112, model 63.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6839. Wins: 2842. Hit rate: 41.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ CLE | 46.7% | +114 | 3.78 | -107 | +107 |
| BOS @ LAD | 44.8% | +123 | 4.08 | -115 | +115 |
| DET @ OAK | 30.4% | +229 | 6.05 | +289 | -289 |
| KCR @ COL | 22.9% | +336 | 7.64 | +205 | -205 |
| MIL @ LAA | 41.0% | +144 | 4.51 | +269 | -269 |
| NYY @ CHC | 43.2% | +131 | 3.79 | +289 | -289 |
| PHI @ BAL | 48.4% | +107 | 3.68 | +189 | -189 |
| SFG @ SDP | 39.8% | +151 | 4.6 | +217 | -217 |
| TEX @ HOU | 23.3% | +329 | 7.28 | +628 | -628 |
| WSN @ ATL | 34.3% | +191 | 5.51 | +115 | -115 |

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +27), HOU 9-1 (W4, +21), SD 7-3 (W1, +19), TB 7-3 (L1, +18), AZ 7-3 (W3, +17)

**Cold:** ATH 2-8 (L3, -30), COL 3-7 (W1, -24), SEA 2-8 (L3, -20), PIT 3-7 (L4, -16), STL 3-7 (L2, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.0 IP across 2 games
- PIT: 9.5 IP across 2 games
- SD: 12.4 IP across 2 games
- TEX: 9.3 IP across 2 games
- CWS: 9.0 IP across 2 games
- LAD: 10.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-01._