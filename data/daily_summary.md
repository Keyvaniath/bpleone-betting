# EdgeStat Daily Brief - 2026-07-21

**Model Confidence: 22.7/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-21T22:58:52 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ COL - OVER_11.5**
- Market: -110
- Model probability: 81.8%
- Raw edge: +56.1%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (11 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:07p ET | TBR @ TOR | Rogers Centre | indoor | TBR_ML +29.36% |
| 7:15p ET | SDP @ ATL | Truist Park | 79F 9mph | ATL_ML +17.21% |
| 7:40p ET | SFG @ KCR | Kauffman Stadium | 78F 9mph | OVER_9.0 +39.4% |
| 7:40p ET | NYM @ MIL | American Family Field | indoor | -- |
| 8:05p ET | DET @ CHC | Wrigley Field | 66F 16mph | OVER_8.5 +32.98% |
| 8:05p ET | CHW @ TEX | Globe Life Field | indoor | OVER_8.5 +37.01% |
| 8:10p ET | MIA @ HOU | Daikin Park | indoor | OVER_8.5 +42.81% |
| 8:40p ET | WSN @ COL | Coors Field | 76F 13mph | OVER_11.5 +56.1% |
| 9:38p ET | STL @ LAA | Angel Stadium | 74F 4mph | UNDER_9.5 +7.45% |
| 9:40p ET | OAK @ ARI | Chase Field | indoor | OAK_ML +5.78% |
| 9:40p ET | CIN @ SEA | T-Mobile Park | indoor | UNDER_8.5 +39.16% |

## Parlays - top 5

- **3-leg @ +634 (prob 20.3%, EV +49.23%)**
  - TBR @ TOR OVER_7.5 (-110, model 54.7%)
  - SDP @ ATL ATL_ML (-152, model 70.6%)
  - CIN @ SEA CIN_ML (+132, model 52.6%)
- **2-leg @ +237 (prob 43.0%, EV +44.6%)**
  - SDP @ ATL ATL_ML (-152, model 70.6%)
  - MIA @ HOU MIA_ML (+103, model 60.8%)
- **2-leg @ +285 (prob 37.1%, EV +42.88%)**
  - SDP @ ATL ATL_ML (-152, model 70.6%)
  - CIN @ SEA CIN_ML (+132, model 52.6%)
- **3-leg @ +640 (prob 19.1%, EV +41.61%)**
  - SDP @ ATL OVER_9.0 (-110, model 55.9%)
  - MIA @ HOU MIA_ML (+103, model 60.8%)
  - STL @ LAA UNDER_9.5 (-110, model 56.3%)
- **3-leg @ +671 (prob 18.2%, EV +40.36%)**
  - MIA @ HOU MIA_ML (+103, model 60.8%)
  - STL @ LAA UNDER_9.5 (-110, model 56.3%)
  - OAK @ ARI OAK_ML (-101, model 53.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6440. Wins: 2613. Hit rate: 40.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHW @ TEX | 29.4% | +240 | 6.12 | +159 | -159 |
| CIN @ SEA | 42.4% | +136 | 4.29 | +204 | -204 |
| DET @ CHC | 25.1% | +299 | 6.21 | +141 | -141 |
| MIA @ HOU | 40.4% | +148 | 4.53 | +256 | -256 |
| NYM @ MIL | 45.0% | +122 | 3.99 | +125 | -125 |
| OAK @ ARI | 23.9% | +319 | 7.16 | +191 | -191 |
| SDP @ ATL | 25.1% | +299 | 7.13 | -143 | +143 |
| SFG @ KCR | 33.4% | +200 | 5.21 | +215 | -215 |
| STL @ LAA | 42.3% | +137 | 4.41 | +132 | -132 |
| TBR @ TOR | 41.0% | +144 | 4.46 | +392 | -392 |
| WSN @ COL | 31.5% | +217 | 5.29 | +549 | -549 |

## Team Form (last 10)

**Hot:** BOS 10-0 (W10, +34), CWS 6-4 (W2, +26), DET 7-3 (W1, +22), PIT 6-4 (L1, +18), SD 5-5 (L1, +17)

**Cold:** ATH 2-8 (W1, -39), TEX 5-5 (L2, -30), KC 4-6 (W1, -27), MIN 5-5 (L3, -16), COL 3-7 (L2, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.2 IP across 2 games
- SD: 9.0 IP across 2 games
- MIN: 9.0 IP across 2 games
- NYY: 12.3 IP across 3 games
- MIL: 9.0 IP across 2 games
- AZ: 10.5 IP across 2 games
- COL: 9.2 IP across 2 games
- DET: 9.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-21._