# EdgeStat Daily Brief - 2026-06-03

**Model Confidence: 73.6/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-03T23:38:06 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ ARI - LAD_ML**
- Market: -147
- Model probability: 89.1%
- Raw edge: +49.66%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | SFG @ MIL | American Family Field | indoor | UNDER_9.5 +25.9% |
| 7:45p ET | TEX @ STL | Busch Stadium | 68F 4mph | TEX_ML +12.26% |
| 8:05p ET | OAK @ CHC | Wrigley Field | 64F 6mph | UNDER_11.0 +21.43% |
| 8:10p ET | PIT @ HOU | Daikin Park | indoor | PIT_ML +28.83% |
| 9:38p ET | COL @ LAA | Angel Stadium | 62F 4mph | OVER_8.5 +23.43% |
| 9:40p ET | LAD @ ARI | Chase Field | indoor | LAD_ML +49.66% |

## Parlays - top 5

- **3-leg @ +596 (prob 21.5%, EV +49.45%)**
  - CLE @ NYY UNDER_8.5 (-110, model 59.0%)
  - KCR @ CIN OVER_8.5 (-110, model 59.3%)
  - LAD @ ARI OVER_8.5 (-110, model 61.3%)
- **3-leg @ +596 (prob 21.5%, EV +49.4%)**
  - KCR @ CIN OVER_8.5 (-110, model 59.3%)
  - TOR @ ATL OVER_8.5 (-110, model 58.2%)
  - TEX @ STL UNDER_8.5 (-110, model 62.1%)
- **3-leg @ +596 (prob 21.5%, EV +49.36%)**
  - CLE @ NYY UNDER_8.5 (-110, model 59.0%)
  - KCR @ CIN CIN_ML (-110, model 62.5%)
  - TOR @ ATL OVER_8.5 (-110, model 58.2%)
- **3-leg @ +664 (prob 19.5%, EV +48.87%)**
  - SFG @ MIL SFG_ML (+100, model 52.5%)
  - TEX @ STL TEX_ML (+100, model 57.8%)
  - COL @ LAA OVER_8.5 (-110, model 64.2%)
- **3-leg @ +629 (prob 20.4%, EV +48.82%)**
  - SFG @ MIL SFG_ML (+100, model 52.5%)
  - COL @ LAA OVER_8.5 (-110, model 64.2%)
  - COL @ LAA LAA_ML (-110, model 60.5%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter home runs | 2307 | 10.5% | 13.1% | 1.244 | 0.805 |
| batter singles | 2307 | 41.8% | 44.5% | 1.065 | 0.939 |
| batter total bases | 4616 | 24.9% | 32.2% | 1.295 | 0.772 |
| batter runs scored | 2307 | 35.5% | 38.9% | 1.096 | 0.912 |
| batter rbis | 4614 | 19.0% | 23.5% | 1.233 | 0.811 |
| pitcher strikeouts | 957 | 35.4% | 39.0% | 1.099 | 0.910 |
| batter hits | 4661 | 37.9% | 41.9% | 1.106 | 0.905 |
| batter doubles | 2307 | 14.0% | 16.1% | 1.145 | 0.874 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ LAA | 30.8% | +225 | 6.01 | +109 | -109 |
| LAD @ ARI | 50.4% | -102 | 3.43 | +1564 | -1564 |
| OAK @ CHC | 38.0% | +163 | 4.87 | +144 | -144 |
| PIT @ HOU | 53.5% | -115 | 3.12 | +376 | -376 |
| SFG @ MIL | 26.8% | +273 | 6.58 | +193 | -193 |
| TEX @ STL | 52.4% | -110 | 3.31 | +245 | -245 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W1, +33), CWS 7-3 (W1, +28), NYY 6-4 (L1, +24), SEA 8-2 (L1, +22), BAL 7-3 (W3, +20)

**Cold:** TB 2-8 (L3, -37), ATH 3-7 (W1, -29), MIN 3-7 (L1, -28), COL 4-6 (W2, -22), KC 3-7 (L1, -21)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SEA: 12.2 IP across 3 games
- TB: 17.1 IP across 3 games
- MIN: 9.4 IP across 3 games
- CWS: 10.4 IP across 3 games
- MIA: 9.4 IP across 3 games
- MIL: 8.1 IP across 2 games
- LAA: 8.5 IP across 2 games
- CIN: 12.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-02._