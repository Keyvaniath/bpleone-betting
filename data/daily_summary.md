# EdgeStat Daily Brief - 2026-08-27

**Model Confidence: 19.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-27T22:47:37 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ ATL - OVER_6.5**
- Market: -110
- Model probability: 70.0%
- Raw edge: +33.54%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:07p ET | KCR @ TOR | Rogers Centre | indoor | KCR_ML +13.84% |
| 7:10p ET | MIL @ NYM | Citi Field | 72F 3mph | MIL_ML +17.28% |
| 7:15p ET | LAD @ ATL | Truist Park | 75F 4mph | OVER_6.5 +33.54% |
| 9:45p ET | ARI @ SFG | Oracle Park | 63F 3mph | SFG_ML +23.15% |

## Parlays - top 5

- **3-leg @ +584 (prob 21.9%, EV +49.65%)**
  - HOU @ NYY OVER_8.0 (-110, model 64.3%)
  - KCR @ TOR KCR_ML (-114, model 60.6%)
  - KCR @ TOR OVER_8.0 (-110, model 56.1%)
- **2-leg @ +200 (prob 48.1%, EV +43.95%)**
  - MIL @ NYM MIL_ML (-204, model 78.4%)
  - ARI @ SFG SFG_ML (+101, model 61.3%)
- **2-leg @ +184 (prob 50.4%, EV +43.51%)**
  - HOU @ NYY OVER_8.0 (-110, model 64.3%)
  - MIL @ NYM MIL_ML (-204, model 78.4%)
- **3-leg @ +434 (prob 26.7%, EV +42.48%)**
  - KCR @ TOR KCR_ML (-114, model 60.6%)
  - KCR @ TOR OVER_8.0 (-110, model 56.1%)
  - MIL @ NYM MIL_ML (-204, model 78.4%)
- **2-leg @ +277 (prob 37.1%, EV +40.19%)**
  - KCR @ TOR KCR_ML (-114, model 60.6%)
  - ARI @ SFG SFG_ML (+101, model 61.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |

Cumulative graded plays: 9758. Wins: 3528. Hit rate: 36.2%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SFG | 31.6% | +216 | 5.87 | +110 | -110 |
| HOU @ NYY | 44.4% | +125 | 4.06 | -- | -- |
| KCR @ TOR | 31.9% | +214 | 5.71 | +269 | -269 |
| LAD @ ATL | 59.0% | -144 | 2.66 | +156 | -156 |
| MIL @ NYM | 52.3% | -110 | 3.23 | +708 | -708 |

## Team Form (last 10)

**Hot:** MIL 7-3 (W1, +38), CLE 8-2 (W7, +23), KC 9-1 (L1, +22), SD 6-4 (W1, +19), NYY 7-3 (W1, +17)

**Cold:** SEA 6-4 (L1, -33), COL 2-8 (L1, -25), HOU 3-7 (L1, -24), STL 4-6 (W1, -19), DET 2-8 (L1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 8.7 IP across 2 games
- STL: 13.6 IP across 3 games
- TB: 8.2 IP across 2 games
- TEX: 8.2 IP across 2 games
- TOR: 8.2 IP across 2 games
- CWS: 9.4 IP across 2 games
- MIA: 9.2 IP across 2 games
- MIL: 11.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.4**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-27._