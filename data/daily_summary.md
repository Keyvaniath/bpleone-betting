# EdgeStat Daily Brief - 2026-09-03

**Model Confidence: 19.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-03T13:13:25 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**OAK @ SEA - OAK_ML**
- Market: +175
- Model probability: 59.2%
- Raw edge: +62.76%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | SFG @ PIT | PNC Park | 95F 12mph | OVER_8.5 +51.26% |
| 1:10p ET | TOR @ CLE | Progressive Field | 89F 7mph | TOR_ML +3.58% |
| 2:10p ET | CHW @ HOU | Daikin Park | indoor | OVER_8.5 +30.91% |
| 7:15p ET | BOS @ BAL | Oriole Park at Camden Yards | 82F 5mph | BOS_ML +21.32% |
| 7:15p ET | MIL @ CHC | Wrigley Field | 76F 5mph | OVER_8.0 +38.3% |
| 7:40p ET | MIA @ KCR | Kauffman Stadium | 88F 7mph | OVER_9.0 +12.47% |
| 8:05p ET | TBR @ TEX | Globe Life Field | indoor | OVER_8.0 +16.28% |
| 9:40p ET | OAK @ SEA | T-Mobile Park | indoor | OAK_ML +62.76% |
| 10:10p ET | STL @ LAD | UNIQLO Field at Dodger Stadium | 63F 4mph | UNDER_8.0 +15.83% |

## Parlays - top 5

- **2-leg @ +386 (prob 29.1%, EV +41.21%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - BOS @ BAL BOS_ML (-136, model 68.1%)
- **2-leg @ +435 (prob 26.2%, EV +40.09%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - BOS @ BAL OVER_8.5 (-110, model 61.4%)
- **2-leg @ +435 (prob 26.2%, EV +39.98%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - STL @ LAD UNDER_8.0 (-110, model 61.4%)
- **2-leg @ +435 (prob 26.0%, EV +38.93%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - TBR @ TEX OVER_8.0 (-110, model 60.9%)
- **2-leg @ +306 (prob 34.1%, EV +38.62%)**
  - Bryce Eldridge OVER 1.5 batter_total_bases (+134, model 50.1%)
  - BOS @ BAL BOS_ML (-136, model 68.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 80 | 57.5% | 56.9% | 0.989 | 1.010 |
| batter total bases | 33 | 45.5% | 45.4% | 0.998 | 1.002 |

Cumulative graded plays: 9860. Wins: 3541. Hit rate: 35.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ BAL | 43.4% | +130 | 4.32 | +368 | -368 |
| CHW @ HOU | 44.3% | +126 | 4.07 | +152 | -152 |
| MIA @ KCR | 50.2% | -101 | 3.54 | +248 | -248 |
| MIL @ CHC | 49.7% | +101 | 3.59 | +162 | -162 |
| OAK @ SEA | 43.8% | +129 | 4.13 | +246 | -246 |
| SFG @ PIT | 36.2% | +176 | 5.49 | +124 | -124 |
| STL @ LAD | 42.6% | +134 | 4.24 | -145 | +145 |
| TBR @ TEX | 51.3% | -106 | 3.33 | +287 | -287 |
| TOR @ CLE | 40.6% | +146 | 4.44 | +209 | -209 |

## Travel / Rest Flags

- **BOS @ BAL** (home): travel + back-to-back (+2h tz shift)
- **OAK @ SEA** (home): travel + back-to-back (-3h tz shift)
- **OAK @ SEA** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** CHC 4-6 (L2, +34), NYY 6-4 (W2, +15), BAL 6-4 (L2, +13), PHI 7-3 (L1, +11), SF 6-4 (W1, +10)

**Cold:** DET 3-7 (W1, -30), BOS 4-6 (L2, -22), SEA 4-6 (W2, -21), STL 4-6 (W2, -17), CIN 5-5 (W2, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 9.8 IP across 2 games
- STL: 12.3 IP across 2 games
- TOR: 9.3 IP across 2 games
- MIN: 13.9 IP across 2 games
- ATL: 10.0 IP across 2 games
- MIA: 8.1 IP across 2 games
- MIL: 9.2 IP across 2 games
- AZ: 11.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-1.2**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-03._