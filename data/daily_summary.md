# EdgeStat Daily Brief - 2026-06-22

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-22T23:25:49 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ MIN - LAD_ML**
- Market: -149
- Model probability: 83.0%
- Raw edge: +38.66%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | LAD @ MIN | Target Field | 66F 4mph | LAD_ML +38.66% |
| 7:40p ET | CLE @ CHW | Rate Field | 59F 6mph | OVER_7.5 +29.77% |
| 7:45p ET | ARI @ STL | Busch Stadium | 66F 4mph | OVER_8.5 +28.38% |
| 8:40p ET | BOS @ COL | Coors Field | 75F 10mph | BOS_ML +8.78% |
| 9:38p ET | BAL @ LAA | Angel Stadium | 63F 5mph | OVER_9.0 +24.59% |
| 10:10p ET | ATL @ SDP | Petco Park | 64F 3mph | ATL_ML +38.04% |

## Parlays - top 5

- **3-leg @ +514 (prob 24.4%, EV +49.65%)**
  - PHI @ WSN WSN_ML (-124, model 59.0%)
  - ARI @ STL OVER_8.5 (-110, model 65.3%)
  - BOS @ COL BOS_ML (-128, model 63.2%)
- **3-leg @ +514 (prob 24.3%, EV +49.61%)**
  - PHI @ WSN WSN_ML (-124, model 59.0%)
  - BOS @ COL BOS_ML (-128, model 63.2%)
  - BAL @ LAA OVER_9.0 (-110, model 65.3%)
- **3-leg @ +621 (prob 20.8%, EV +49.57%)**
  - TEX @ MIA TEX_ML (+109, model 53.8%)
  - PHI @ WSN WSN_ML (-124, model 59.0%)
  - ARI @ STL OVER_8.5 (-110, model 65.3%)
- **3-leg @ +621 (prob 20.7%, EV +49.52%)**
  - TEX @ MIA TEX_ML (+109, model 53.8%)
  - PHI @ WSN WSN_ML (-124, model 59.0%)
  - BAL @ LAA OVER_9.0 (-110, model 65.3%)
- **3-leg @ +514 (prob 24.3%, EV +49.31%)**
  - TEX @ MIA UNDER_8.5 (-110, model 65.1%)
  - PHI @ WSN WSN_ML (-124, model 59.0%)
  - BOS @ COL BOS_ML (-128, model 63.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ STL | 32.4% | +208 | 5.68 | -186 | +186 |
| ATL @ SDP | 37.5% | +167 | 4.83 | +415 | -415 |
| BAL @ LAA | 32.2% | +210 | 5.81 | +205 | -205 |
| BOS @ COL | 23.4% | +327 | 7.72 | +279 | -279 |
| CLE @ CHW | 22.6% | +343 | 7.29 | +143 | -143 |
| LAD @ MIN | 34.1% | +193 | 5.23 | +871 | -871 |

## Travel / Rest Flags

- **LAD @ MIN** (away): travel + back-to-back (+2h tz shift)
- **ATL @ SDP** (home): travel + back-to-back (-2h tz shift)
- **ATL @ SDP** (away): travel + back-to-back (-3h tz shift)

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +22), MIL 5-5 (W1, +15), PHI 6-4 (W2, +13), NYY 6-4 (L2, +13), DET 5-5 (W3, +13)

**Cold:** TEX 4-6 (W1, -25), ATL 3-7 (L1, -23), CWS 4-6 (L3, -13), ATH 5-5 (L2, -13), NYM 5-5 (L2, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 8.0 IP across 2 games
- SD: 11.2 IP across 2 games
- CIN: 8.0 IP across 2 games
- WSH: 10.1 IP across 2 games
- NYM: 9.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-21._