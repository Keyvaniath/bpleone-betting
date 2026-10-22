# EdgeStat Daily Brief - 2026-10-22

**Model Confidence: 9.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-10-22T22:31:24 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CIN @ COL - CIN_ML**
- Market: -110
- Model probability: 73.7%
- Raw edge: +40.74%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | SDP @ LAD | Petco Park | 62F -6mph | LAD_ML +25.43% |
| 6:45p ET | BOS @ NYY | Yankee Stadium | 71F 12mph | OVER_9.0 +30.97% |
| 9:40p ET | CIN @ COL | Coors Field | 74F 4mph | CIN_ML +40.74% |

## Parlays - top 5

- **3-leg @ +629 (prob 20.4%, EV +48.71%)**
  - Richie Palacios OVER 0.5 batter_hits (+105, model 55.1%)
  - Liam Hicks OVER 0.5 batter_hits (-116, model 59.3%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **3-leg @ +839 (prob 15.6%, EV +46.84%)**
  - Richie Palacios OVER 0.5 batter_hits (+105, model 55.1%)
  - Jackson Chourio OVER 1.5 batter_total_bases (+140, model 45.4%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **3-leg @ +679 (prob 18.8%, EV +46.34%)**
  - Richie Palacios OVER 0.5 batter_hits (+105, model 55.1%)
  - David Hamilton OVER 0.5 batter_hits (-101, model 54.6%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **3-leg @ +753 (prob 16.8%, EV +43.44%)**
  - Liam Hicks OVER 0.5 batter_hits (-116, model 59.3%)
  - Jackson Chourio OVER 1.5 batter_total_bases (+140, model 45.4%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)
- **3-leg @ +607 (prob 20.2%, EV +42.95%)**
  - Liam Hicks OVER 0.5 batter_hits (-116, model 59.3%)
  - David Hamilton OVER 0.5 batter_hits (-101, model 54.6%)
  - CIN @ COL OVER_10.5 (-110, model 62.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 330 | 53.3% | 56.3% | 1.055 | 0.949 |
| batter total bases | 87 | 34.5% | 42.3% | 1.222 | 0.830 |

Cumulative graded plays: 12204. Wins: 4733. Hit rate: 38.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | -- | -- | -- | +115 | -115 |
| CIN @ COL | -- | -- | -- | +465 | -465 |
| SDP @ LAD | -- | -- | -- | -166 | +166 |

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