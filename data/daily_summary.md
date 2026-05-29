# EdgeStat Daily Brief - 2026-05-29

**Model Confidence: 74.0/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-29T23:23:23 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYY @ OAK - NYY_ML**
- Market: -140
- Model probability: 80.6%
- Raw edge: +38.23%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | DET @ CHW | Rate Field | 62F 3mph | OVER_8.5 +20.52% |
| 8:05p ET | KCR @ TEX | Globe Life Field | indoor | TEX_ML +5.91% |
| 8:10p ET | MIL @ HOU | Daikin Park | indoor | UNDER_8.5 +34.86% |
| 8:40p ET | SFG @ COL | Coors Field | 63F 5mph | SFG_ML +14.12% |
| 9:40p ET | NYY @ OAK | Sutter Health Park | 63F 7mph | NYY_ML +38.23% |
| 10:10p ET | ARI @ SEA | T-Mobile Park | indoor | -- |
| 10:15p ET | PHI @ LAD | UNIQLO Field at Dodger Stadium | 57F 3mph | UNDER_8.0 +29.57% |

## Parlays - top 5

- **2-leg @ +228 (prob 45.4%, EV +48.91%)**
  - ATL @ CIN ATL_ML (-139, model 71.2%)
  - DET @ CHW OVER_8.5 (-110, model 63.7%)
- **2-leg @ +228 (prob 45.0%, EV +47.72%)**
  - ATL @ CIN ATL_ML (-139, model 71.2%)
  - CHC @ STL OVER_7.5 (-110, model 63.2%)
- **2-leg @ +264 (prob 40.2%, EV +46.56%)**
  - CHC @ STL OVER_7.5 (-110, model 63.2%)
  - DET @ CHW OVER_8.5 (-110, model 63.7%)
- **2-leg @ +228 (prob 44.1%, EV +44.91%)**
  - ATL @ CIN ATL_ML (-139, model 71.2%)
  - SDP @ WSN UNDER_9.0 (-110, model 62.0%)
- **2-leg @ +264 (prob 39.5%, EV +43.78%)**
  - SDP @ WSN UNDER_9.0 (-110, model 62.0%)
  - DET @ CHW OVER_8.5 (-110, model 63.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter rbis | 6902 | 19.1% | 23.3% | 1.221 | 0.819 |
| batter total bases | 6904 | 25.1% | 32.0% | 1.274 | 0.785 |
| batter runs scored | 3451 | 35.5% | 38.8% | 1.094 | 0.915 |
| pitcher strikeouts | 1464 | 34.7% | 38.1% | 1.098 | 0.911 |
| batter hits | 6904 | 38.5% | 41.8% | 1.084 | 0.922 |
| batter singles | 3451 | 42.7% | 44.5% | 1.042 | 0.959 |
| batter doubles | 3451 | 14.6% | 16.0% | 1.097 | 0.912 |
| batter home runs | 3451 | 10.1% | 12.9% | 1.281 | 0.781 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SEA | 36.5% | +174 | 5.03 | +139 | -139 |
| BOS @ CLE | 63.2% | -172 | 2.29 | -- | -- |
| CHC @ STL | 33.4% | +199 | 5.48 | -- | -- |
| DET @ CHW | 29.8% | +236 | 5.93 | +221 | -221 |
| KCR @ TEX | 48.5% | +106 | 3.61 | +126 | -126 |
| LAA @ TBR | 71.2% | -248 | 1.69 | -- | -- |
| MIA @ NYM | 51.4% | -106 | 3.33 | -- | -- |
| MIL @ HOU | 59.1% | -145 | 2.63 | +330 | -330 |
| NYY @ OAK | 36.4% | +175 | 5.28 | +740 | -740 |
| PHI @ LAD | 52.2% | -109 | 3.29 | -127 | +127 |
| SFG @ COL | 18.0% | +455 | 8.5 | +366 | -366 |

## Travel / Rest Flags

- **SDP @ WSN** (away): 2 days rest (+3h tz)
- **NYY @ OAK** (away): 2 days rest (-2h tz)

## Team Form (last 10)

**Hot:** LAD 8-2 (W5, +35), AZ 9-1 (W5, +31), NYY 6-4 (W4, +20), MIL 7-3 (W3, +16), HOU 7-3 (W2, +14)

**Cold:** COL 2-8 (L5, -33), KC 3-7 (L3, -24), CHC 2-8 (W2, -23), DET 2-8 (L1, -18), NYM 3-7 (W1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- MIN: 8.3 IP across 2 games
- ATL: 8.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-28._