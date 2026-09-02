# EdgeStat Daily Brief - 2026-09-02

**Model Confidence: 21.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-02T20:57:07 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**DET @ MIN - OVER_8.5**
- Market: -110
- Model probability: 71.8%
- Raw edge: +37.11%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | SFG @ PIT | PNC Park | 82F 6mph | OVER_8.5 +17.91% |
| 6:40p ET | NYM @ TBR | Tropicana Field | indoor | -- |
| 6:40p ET | TOR @ CLE | Progressive Field | 84F 7mph | UNDER_8.0 +26.81% |
| 7:40p ET | DET @ MIN | Target Field | 78F 4mph | OVER_8.5 +37.11% |
| 7:40p ET | MIA @ KCR | Kauffman Stadium | 88F 6mph | MIA_ML +7.18% |
| 7:40p ET | MIL @ CHC | Wrigley Field | 80F 6mph | MIL_ML +22.81% |
| 8:10p ET | CHW @ HOU | Daikin Park | indoor | CHW_ML +23.05% |
| 9:38p ET | NYY @ LAA | Angel Stadium | 67F 3mph | NYY_ML +12.31% |
| 10:10p ET | STL @ LAD | UNIQLO Field at Dodger Stadium | 63F 4mph | OVER_7.5 +19.18% |

## Parlays - top 5

- **2-leg @ +356 (prob 31.8%, EV +45.1%)**
  - SFG @ PIT OVER_8.5 (-110, model 61.8%)
  - CHW @ HOU CHW_ML (+139, model 51.5%)
- **2-leg @ +356 (prob 31.8%, EV +44.95%)**
  - CHW @ HOU CHW_ML (+139, model 51.5%)
  - STL @ LAD OVER_7.5 (-110, model 61.7%)
- **2-leg @ +264 (prob 39.7%, EV +44.8%)**
  - SFG @ PIT OVER_8.5 (-110, model 61.8%)
  - MIL @ CHC MIL_ML (-110, model 64.3%)
- **2-leg @ +264 (prob 39.7%, EV +44.66%)**
  - MIL @ CHC MIL_ML (-110, model 64.3%)
  - STL @ LAD OVER_7.5 (-110, model 61.7%)
- **2-leg @ +310 (prob 35.0%, EV +43.5%)**
  - Edwin Arroyo OVER 0.5 batter_hits (-140, model 68.0%)
  - CHW @ HOU CHW_ML (+139, model 51.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 25 | 40.0% | 46.5% | 1.155 | 0.892 |
| batter hits | 66 | 60.6% | 56.0% | 0.924 | 1.075 |

Cumulative graded plays: 9786. Wins: 3518. Hit rate: 35.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHW @ HOU | 28.1% | +256 | 6.35 | +182 | -182 |
| DET @ MIN | 32.0% | +212 | 5.55 | +246 | -246 |
| MIA @ KCR | 53.0% | -113 | 3.24 | +225 | -225 |
| MIL @ CHC | 51.3% | -106 | 3.46 | +310 | -310 |
| NYM @ TBR | 50.8% | -103 | 3.39 | -110 | +110 |
| NYY @ LAA | 70.2% | -236 | 1.77 | +461 | -461 |
| SFG @ PIT | 39.1% | +156 | 4.84 | +135 | -135 |
| STL @ LAD | 51.0% | -104 | 3.34 | -179 | +179 |
| TOR @ CLE | 58.2% | -139 | 2.83 | +271 | -271 |

## Team Form (last 10)

**Hot:** CHC 4-6 (L1, +37), CLE 8-2 (W2, +26), PHI 8-2 (W6, +21), NYY 6-4 (W1, +17), BAL 7-3 (L1, +15)

**Cold:** DET 2-8 (L3, -37), SEA 4-6 (W1, -25), STL 3-7 (W1, -20), CIN 5-5 (W2, -16), BOS 5-5 (L1, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 8.0 IP across 3 games
- SF: 9.5 IP across 2 games
- MIN: 10.0 IP across 2 games
- MIL: 8.3 IP across 2 games
- BOS: 9.2 IP across 2 games
- CIN: 10.4 IP across 3 games
- HOU: 9.1 IP across 2 games
- WSH: 11.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-02._