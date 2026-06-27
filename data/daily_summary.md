# EdgeStat Daily Brief - 2026-06-27

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-27T23:13:06 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ SDP - UNDER_8.0**
- Market: -110
- Model probability: 73.8%
- Raw edge: +40.94%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | MIA @ STL | Busch Stadium | 76F 2mph | MIA_ML +5.39% |
| 8:40p ET | LAD @ SDP | Petco Park | 65F 4mph | UNDER_8.0 +40.94% |
| 9:05p ET | ATL @ SFG | Oracle Park | 57F 9mph | UNDER_8.0 +13.6% |
| 9:38p ET | OAK @ LAA | Angel Stadium | 64F 5mph | OVER_8.0 +17.48% |

## Parlays - top 5

- **3-leg @ +684 (prob 18.5%, EV +44.91%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +684 (prob 18.3%, EV +43.3%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - SEA @ CLE UNDER_7.5 (-110, model 57.8%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +510 (prob 23.4%, EV +42.74%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - LAD @ SDP LAD_ML (-206, model 74.0%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +684 (prob 18.2%, EV +42.62%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - SEA @ CLE UNDER_7.5 (-110, model 57.8%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
- **3-leg @ +510 (prob 23.3%, EV +42.06%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
  - LAD @ SDP LAD_ML (-206, model 74.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ SFG | 41.5% | +141 | 4.66 | +176 | -176 |
| CHC @ MIL | 27.2% | +267 | 6.5 | -- | -- |
| COL @ MIN | 37.5% | +167 | 4.9 | -- | -- |
| LAD @ SDP | 56.6% | -131 | 2.87 | +569 | -569 |
| MIA @ STL | 42.3% | +136 | 4.23 | +160 | -160 |
| OAK @ LAA | 34.6% | +189 | 5.49 | +166 | -166 |
| SEA @ CLE | 53.9% | -117 | 3.09 | -- | -- |
| WSN @ BAL | 59.2% | -145 | 2.62 | -- | -- |

## Team Form (last 10)

**Hot:** CHC 7-3 (L1, +24), PHI 7-3 (W4, +21), BOS 6-4 (W3, +16), MIL 7-3 (W5, +15), MIN 6-4 (W1, +14)

**Cold:** NYM 2-8 (L7, -25), NYY 3-7 (L3, -20), ATL 3-7 (W1, -18), KC 5-5 (L3, -17), STL 4-6 (L3, -17)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 10.3 IP across 2 games
- CHC: 8.1 IP across 2 games
- HOU: 13.1 IP across 3 games
- KC: 8.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-26._