# EdgeStat Daily Brief - 2026-09-03

**Model Confidence: 19.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-03T23:57:11 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**OAK @ SEA - OAK_ML**
- Market: +180
- Model probability: 59.2%
- Raw edge: +65.72%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:05p ET | TBR @ TEX | Globe Life Field | indoor | TBR_ML +20.86% |
| 9:40p ET | OAK @ SEA | T-Mobile Park | indoor | OAK_ML +65.72% |
| 10:10p ET | STL @ LAD | UNIQLO Field at Dodger Stadium | 63F 2mph | UNDER_7.5 +6.05% |

## Parlays - top 5

- **2-leg @ +460 (prob 26.6%, EV +48.96%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - TBR @ TEX TBR_ML (+100, model 62.3%)
- **2-leg @ +300 (prob 37.1%, EV +48.47%)**
  - MIA @ KCR MIA_ML (+100, model 59.5%)
  - TBR @ TEX TBR_ML (+100, model 62.3%)
- **2-leg @ +282 (prob 38.8%, EV +47.98%)**
  - MIL @ CHC OVER_8.5 (-110, model 62.2%)
  - TBR @ TEX TBR_ML (+100, model 62.3%)
- **2-leg @ +300 (prob 36.9%, EV +47.6%)**
  - TBR @ TEX TBR_ML (+100, model 62.3%)
  - OAK @ SEA OAK_ML (+100, model 59.2%)
- **2-leg @ +435 (prob 27.5%, EV +46.84%)**
  - Spencer Horwitz UNDER 0.5 batter_hits (+180, model 42.7%)
  - MIA @ KCR OVER_8.5 (-110, model 64.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 80 | 57.5% | 56.9% | 0.989 | 1.010 |
| batter total bases | 33 | 45.5% | 45.4% | 0.998 | 1.002 |

Cumulative graded plays: 9841. Wins: 3524. Hit rate: 35.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| OAK @ SEA | 43.8% | +129 | 4.13 | +246 | -246 |
| STL @ LAD | 42.6% | +134 | 4.25 | -143 | +143 |
| TBR @ TEX | 51.3% | -106 | 3.33 | +287 | -287 |

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

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-03._