# EdgeStat Daily Brief - 2026-09-11

**Model Confidence: 20.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-11T23:57:43 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PHI @ ATL - ATL_ML**
- Market: +113
- Model probability: 75.9%
- Raw edge: +61.68%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | PHI @ ATL | Truist Park | 73F 6mph | ATL_ML +61.68% |
| 8:10p ET | CLE @ MIN | Target Field | 73F 11mph | OVER_7.5 +20.54% |
| 8:15p ET | CHW @ STL | Busch Stadium | 74F 2mph | CHW_ML +12.24% |
| 9:40p ET | SEA @ OAK | Sutter Health Park | 69F 7mph | OVER_9.5 +21.21% |
| 9:40p ET | TEX @ ARI | Chase Field | indoor | TEX_ML +42.39% |
| 10:15p ET | SDP @ SFG | Oracle Park | 59F 12mph | SFG_ML +32.21% |

## Parlays - top 5

- **2-leg @ +463 (prob 25.9%, EV +46.1%)**
  - Kevin McGonigle UNDER 0.5 batter_hits (+195, model 40.2%)
  - CIN @ MIL OVER_8.5 (-110, model 64.5%)
- **2-leg @ +454 (prob 26.4%, EV +45.98%)**
  - Gleyber Torres UNDER 0.5 batter_hits (+190, model 40.9%)
  - CIN @ MIL OVER_8.5 (-110, model 64.5%)
- **2-leg @ +490 (prob 24.7%, EV +45.82%)**
  - Kevin McGonigle UNDER 0.5 batter_hits (+195, model 40.2%)
  - SEA @ OAK SEA_ML (+100, model 61.5%)
- **2-leg @ +282 (prob 38.2%, EV +45.82%)**
  - LAD @ MIA LAD_ML (+100, model 59.2%)
  - CIN @ MIL OVER_8.5 (-110, model 64.5%)
- **2-leg @ +480 (prob 25.1%, EV +45.7%)**
  - Gleyber Torres UNDER 0.5 batter_hits (+190, model 40.9%)
  - SEA @ OAK SEA_ML (+100, model 61.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 97 | 42.3% | 47.8% | 1.130 | 0.892 |
| batter hits | 198 | 54.5% | 56.1% | 1.028 | 0.974 |

Cumulative graded plays: 10399. Wins: 3752. Hit rate: 36.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHW @ STL | 16.5% | +507 | 9.1 | +225 | -225 |
| CLE @ MIN | 47.2% | +112 | 3.88 | +173 | -173 |
| PHI @ ATL | 56.9% | -132 | 2.85 | -177 | +177 |
| SDP @ SFG | 61.7% | -161 | 2.6 | +136 | -136 |
| SEA @ OAK | 29.1% | +244 | 6.18 | +262 | -262 |
| TEX @ ARI | 30.8% | +224 | 5.89 | +302 | -302 |

## Travel / Rest Flags

- **LAA @ WSN** (home): 2 days rest (+3h tz)
- **BAL @ TOR** (home): 2 days rest (+3h tz)
- **LAD @ MIA** (away): 2 days rest (+3h tz)
- **CIN @ MIL** (away): 2 days rest (+2h tz)
- **CHW @ STL** (home): 2 days rest (+2h tz)

## Team Form (last 10)

**Hot:** NYY 7-3 (W3, +29), LAD 8-2 (W7, +21), TOR 6-4 (L1, +18), PIT 8-2 (W4, +11), TEX 5-5 (L2, +10)

**Cold:** WSH 2-8 (L7, -20), KC 3-7 (W1, -15), CLE 5-5 (L1, -14), COL 3-7 (L4, -13), CIN 5-5 (L3, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 8.4 IP across 2 games
- CWS: 9.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-11._