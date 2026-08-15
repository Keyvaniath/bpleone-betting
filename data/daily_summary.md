# EdgeStat Daily Brief - 2026-08-15

**Model Confidence: 22.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-08-15T21:07:05 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ LAD - MIL_ML**
- Market: +140
- Model probability: 59.4%
- Raw edge: +42.57%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:10p ET | BAL @ TBR | Tropicana Field | indoor | OVER_7.5 +9.83% |
| 6:40p ET | MIA @ CIN | Great American Ball Park | 81F 3mph | OVER_9.5 +25.83% |
| 7:10p ET | SDP @ CLE | Progressive Field | 73F 4mph | UNDER_8.5 +16.03% |
| 7:10p ET | SEA @ HOU | Daikin Park | indoor | OVER_8.0 +2.96% |
| 7:10p ET | PHI @ MIN | Target Field | 73F 8mph | UNDER_9.5 +17.41% |
| 7:15p ET | BOS @ PIT | PNC Park | 74F 2mph | OVER_8.0 +13.26% |
| 7:15p ET | ARI @ ATL | Truist Park | 80F 2mph | OVER_8.5 +22.45% |
| 7:15p ET | MIL @ LAD | UNIQLO Field at Dodger Stadium | 69F 5mph | MIL_ML +42.57% |
| 9:38p ET | KCR @ LAA | Angel Stadium | 70F 3mph | UNDER_9.5 +30.39% |
| 9:40p ET | TEX @ OAK | Sutter Health Park | 66F 7mph | UNDER_10.5 +8.63% |

## Parlays - top 5

- **2-leg @ +349 (prob 33.1%, EV +48.45%)**
  - Jake McCarthy OVER 1.5 batter_total_bases (+135, model 51.6%)
  - ARI @ ATL OVER_8.5 (-110, model 64.1%)
- **2-leg @ +272 (prob 39.5%, EV +47.0%)**
  - Dillon Dingler OVER 1.5 batter_total_bases (+109, model 56.6%)
  - MIA @ CIN MIA_ML (-128, model 69.8%)
- **2-leg @ +345 (prob 32.8%, EV +46.06%)**
  - Miguel Vargas OVER 1.5 batter_total_bases (+133, model 53.4%)
  - PHI @ MIN UNDER_9.5 (-110, model 61.5%)
- **2-leg @ +240 (prob 42.9%, EV +45.87%)**
  - MIA @ CIN MIA_ML (-128, model 69.8%)
  - PHI @ MIN UNDER_9.5 (-110, model 61.5%)
- **2-leg @ +343 (prob 32.8%, EV +45.46%)**
  - Munetaka Murakami OVER 1.5 batter_total_bases (+132, model 53.4%)
  - PHI @ MIN UNDER_9.5 (-110, model 61.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8395. Wins: 3167. Hit rate: 37.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ ATL | 54.6% | -120 | 3.04 | +144 | -144 |
| BAL @ TBR | 46.7% | +114 | 3.81 | +107 | -107 |
| BOS @ PIT | 32.5% | +208 | 5.59 | +188 | -188 |
| KCR @ LAA | 50.5% | -102 | 3.45 | +159 | -159 |
| MIA @ CIN | 27.5% | +263 | 6.35 | +384 | -384 |
| MIL @ LAD | 34.4% | +191 | 5.5 | +258 | -258 |
| PHI @ MIN | 42.2% | +137 | 4.52 | +241 | -241 |
| SDP @ CLE | 44.5% | +125 | 4.12 | +202 | -202 |
| SEA @ HOU | 40.3% | +148 | 4.55 | +136 | -136 |
| TEX @ OAK | 52.5% | -111 | 3.34 | +233 | -233 |

## Team Form (last 10)

**Hot:** TB 9-1 (L1, +30), SD 8-2 (W6, +19), ATL 6-4 (L1, +14), DET 5-5 (L2, +14), NYM 7-3 (W1, +14)

**Cold:** SEA 2-8 (L1, -32), ATH 3-7 (W1, -21), CLE 2-8 (L2, -16), COL 4-6 (W3, -15), SF 3-7 (L2, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TEX: 8.3 IP across 2 games
- CWS: 16.0 IP across 3 games
- CHC: 8.4 IP across 3 games
- DET: 10.8 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-15._