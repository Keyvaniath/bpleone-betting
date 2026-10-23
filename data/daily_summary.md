# EdgeStat Daily Brief - 2026-10-23

**Model Confidence: 9.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-10-23T06:43:04 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**TBR @ MIL - OVER_6.5**
- Market: -110
- Model probability: 70.9%
- Raw edge: +35.39%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:00p ET | TBR @ MIL | American Family Field | indoor | OVER_6.5 +35.39% |

## Parlays - top 5

- **3-leg @ +575 (prob 19.7%, EV +33.09%)**
  - Richie Palacios OVER 0.5 batter_hits (+100, model 55.4%)
  - Taylor Walls OVER 0.5 batter_hits (+122, model 49.2%)
  - TBR @ MIL MIL_ML (-192, model 72.3%)
- **3-leg @ +453 (prob 23.9%, EV +32.08%)**
  - Richie Palacios OVER 0.5 batter_hits (+100, model 55.4%)
  - Liam Hicks OVER 0.5 batter_hits (-122, model 59.6%)
  - TBR @ MIL MIL_ML (-192, model 72.3%)
- **3-leg @ +682 (prob 16.9%, EV +31.84%)**
  - Richie Palacios OVER 0.5 batter_hits (+100, model 55.4%)
  - Brice Turang UNDER 0.5 batter_hits (+157, model 42.1%)
  - TBR @ MIL MIL_ML (-192, model 72.3%)
- **3-leg @ +761 (prob 15.2%, EV +30.76%)**
  - Richie Palacios OVER 0.5 batter_hits (+100, model 55.4%)
  - Jackson Chourio UNDER 0.5 batter_hits (+183, model 37.9%)
  - TBR @ MIL MIL_ML (-192, model 72.3%)
- **3-leg @ +514 (prob 21.2%, EV +30.2%)**
  - Taylor Walls OVER 0.5 batter_hits (+122, model 49.2%)
  - Liam Hicks OVER 0.5 batter_hits (-122, model 59.6%)
  - TBR @ MIL MIL_ML (-192, model 72.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 82 | 34.2% | 41.9% | 1.224 | 0.830 |
| batter hits | 312 | 53.5% | 56.2% | 1.050 | 0.953 |

Cumulative graded plays: 18394. Wins: 7856. Hit rate: 42.7%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| TBR @ MIL | 68.9% | -221 | 1.86 | -147 | +147 |

## Team Form (last 10)

**Hot:** MIL 7-1 (W5, +13), TB 7-2 (W3, +12), CLE 5-5 (L3, +4), SD 1-3 (L1, -3), LAD 3-5 (L4, -4)

**Cold:** CWS 2-3 (L3, -8), ATL 1-3 (L2, -6), NYY 0-3 (L3, -5), LAD 3-5 (L4, -4), SD 1-3 (L1, -3)

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-10-22._