# EdgeStat Daily Brief - 2026-10-26

**Model Confidence: 10.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-10-26T20:13:46 UTC. Game lines source: **DraftKings**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ TBR - OVER_7.0**
- Market: -115
- Model probability: 68.2%
- Raw edge: +27.5%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:00p ET | MIL @ TBR | Tropicana Field | indoor | OVER_7.0 +27.5% |

## Parlays - top 5

- **3-leg @ +694 (prob 16.1%, EV +28.1%)**
  - Junior Caminero OVER 1.5 batter_total_bases (+122, model 48.9%)
  - Ryan Vilade OVER 0.5 batter_hits (-124, model 58.9%)
  - MIL @ TBR MIL_ML (-102, model 56.1%)
- **3-leg @ +872 (prob 13.1%, EV +27.37%)**
  - Junior Caminero OVER 1.5 batter_total_bases (+122, model 48.9%)
  - Jackson Chourio OVER 1.5 batter_total_bases (+121, model 47.8%)
  - MIL @ TBR MIL_ML (-102, model 56.1%)
- **3-leg @ +1171 (prob 10.0%, EV +26.56%)**
  - Junior Caminero OVER 1.5 batter_total_bases (+122, model 48.9%)
  - Jackson Chourio UNDER 0.5 batter_hits (+189, model 36.4%)
  - MIL @ TBR MIL_ML (-102, model 56.1%)
- **3-leg @ +1004 (prob 11.4%, EV +25.7%)**
  - Junior Caminero OVER 1.5 batter_total_bases (+122, model 48.9%)
  - William Contreras OVER 1.5 batter_total_bases (+151, model 41.6%)
  - MIL @ TBR MIL_ML (-102, model 56.1%)
- **3-leg @ +1105 (prob 10.4%, EV +24.97%)**
  - Junior Caminero OVER 1.5 batter_total_bases (+122, model 48.9%)
  - Junior Caminero UNDER 0.5 batter_hits (+174, model 37.9%)
  - MIL @ TBR MIL_ML (-102, model 56.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 84 | 35.7% | 41.4% | 1.157 | 0.874 |
| batter hits | 330 | 55.1% | 56.5% | 1.024 | 0.977 |

Cumulative graded plays: 19725. Wins: 8746. Hit rate: 44.3%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| MIL @ TBR | 64.3% | -180 | 2.21 | +222 | -222 |

## Team Form (last 10)

**Hot:** MIL 7-1 (W7, +13), TB 5-4 (L2, +6), CLE 5-4 (L3, +5), SD 1-1 (L1, -1), NYY 0-1 (L1, -1)

**Cold:** CWS 0-3 (L3, -12), LAD 2-4 (L4, -5), ATL 0-2 (L2, -5), NYY 0-1 (L1, -1), SD 1-1 (L1, -1)

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-10-26._