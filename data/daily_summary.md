# EdgeStat Daily Brief - 2026-09-07

**Model Confidence: 27.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-07T18:47:17 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CIN @ LAD - CIN_ML**
- Market: +260
- Model probability: 37.1%
- Raw edge: +33.6%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 3:10p ET | MIN @ DET | Comerica Park | 75F 7mph | MIN_ML +10.3% |
| 5:10p ET | WSN @ SDP | Petco Park | 88F 11mph | SDP_ML +8.32% |
| 8:10p ET | STL @ SFG | Oracle Park | 66F 5mph | SFG_ML +16.56% |
| 9:10p ET | CIN @ LAD | UNIQLO Field at Dodger Stadium | 76F 2mph | CIN_ML +33.6% |
| 10:05p ET | TOR @ OAK | Sutter Health Park | 67F 4mph | UNDER_9.5 +13.85% |

## Parlays - top 5

- **3-leg @ +433 (prob 23.3%, EV +24.28%)**
  - MIN @ DET MIN_ML (+104, model 51.5%)
  - WSN @ SDP SDP_ML (-206, model 72.9%)
  - STL @ SFG SFG_ML (-132, model 62.1%)
- **3-leg @ +398 (prob 24.9%, EV +23.89%)**
  - WSN @ SDP SDP_ML (-206, model 72.9%)
  - STL @ SFG SFG_ML (-132, model 62.1%)
  - CIN @ LAD OVER_8.5 (-110, model 54.9%)
- **3-leg @ +398 (prob 24.8%, EV +23.57%)**
  - MIN @ DET OVER_8.0 (-110, model 54.8%)
  - WSN @ SDP SDP_ML (-206, model 72.9%)
  - STL @ SFG SFG_ML (-132, model 62.1%)
- **3-leg @ +584 (prob 17.6%, EV +20.26%)**
  - MIN @ DET MIN_ML (+104, model 51.5%)
  - STL @ SFG SFG_ML (-132, model 62.1%)
  - CIN @ LAD OVER_8.5 (-110, model 54.9%)
- **3-leg @ +584 (prob 17.5%, EV +19.95%)**
  - MIN @ DET MIN_ML (+104, model 51.5%)
  - MIN @ DET OVER_8.0 (-110, model 54.8%)
  - STL @ SFG SFG_ML (-132, model 62.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 62 | 46.8% | 46.1% | 0.987 | 1.012 |
| batter hits | 144 | 54.9% | 56.0% | 1.020 | 0.981 |

Cumulative graded plays: 10153. Wins: 3644. Hit rate: 35.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CIN @ LAD | 39.0% | +157 | 4.76 | +101 | -101 |
| MIN @ DET | 29.0% | +245 | 6.09 | +185 | -185 |
| STL @ SFG | 39.6% | +152 | 4.74 | +108 | -108 |
| TOR @ OAK | 58.1% | -139 | 2.78 | +380 | -380 |
| WSN @ SDP | 46.7% | +114 | 3.56 | -153 | +153 |

## Travel / Rest Flags

- **STL @ SFG** (home): travel + back-to-back (-3h tz shift)
- **CIN @ LAD** (away): travel + back-to-back (-3h tz shift)
- **TOR @ OAK** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** PHI 7-3 (L1, +17), NYY 6-4 (L1, +17), TOR 7-3 (L1, +16), CHC 5-5 (L1, +13), ATL 7-3 (W1, +8)

**Cold:** DET 3-7 (L1, -20), BOS 6-4 (W4, -14), SEA 3-7 (W1, -14), CLE 5-5 (W1, -10), COL 3-7 (L1, -8)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 8.5 IP across 2 games
- STL: 8.6 IP across 2 games
- TEX: 9.3 IP across 2 games
- CWS: 11.3 IP across 2 games
- BAL: 8.1 IP across 2 games
- CIN: 8.3 IP across 2 games
- LAD: 9.0 IP across 2 games
- NYM: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.1**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-06._