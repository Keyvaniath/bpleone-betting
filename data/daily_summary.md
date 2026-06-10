# EdgeStat Daily Brief - 2026-06-10

**Model Confidence: 73.1/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-10T23:30:42 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ OAK - UNDER_15.0**
- Market: -110
- Model probability: 96.7%
- Raw edge: +84.61%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | TEX @ KCR | Kauffman Stadium | 82F 8mph | UNDER_10.0 +49.55% |
| 7:40p ET | ATL @ CHW | Rate Field | 74F 9mph | OVER_7.0 +34.08% |
| 8:40p ET | CHC @ COL | Coors Field | 76F 4mph | OVER_11.5 +38.72% |
| 9:05p ET | MIL @ OAK | Las Vegas Ballpark | 70F 0mph | UNDER_15.0 +84.61% |
| 9:38p ET | HOU @ LAA | Angel Stadium | 65F 5mph | -- |

## Parlays - top 5

- **3-leg @ +793 (prob 16.8%, EV +49.87%)**
  - CIN @ SDP UNDER_8.5 (-110, model 60.8%)
  - SEA @ BAL SEA_ML (-109, model 64.7%)
  - MIN @ DET MIN_ML (+144, model 42.7%)
- **3-leg @ +742 (prob 17.8%, EV +49.81%)**
  - CIN @ SDP UNDER_8.5 (-110, model 60.8%)
  - CIN @ SDP CIN_ML (+130, model 45.3%)
  - SEA @ BAL SEA_ML (-109, model 64.7%)
- **3-leg @ +599 (prob 21.4%, EV +49.64%)**
  - SEA @ BAL SEA_ML (-109, model 64.7%)
  - MIN @ DET UNDER_9.5 (-110, model 59.8%)
  - PHI @ TOR OVER_9.0 (-110, model 55.4%)
- **3-leg @ +499 (prob 24.8%, EV +48.6%)**
  - WSN @ SFG WSN_ML (-112, model 60.5%)
  - PHI @ TOR OVER_9.0 (-110, model 55.4%)
  - ATL @ CHW ATL_ML (-152, model 74.0%)
- **3-leg @ +879 (prob 15.2%, EV +48.57%)**
  - WSN @ SFG WSN_ML (-112, model 60.5%)
  - MIN @ DET MIN_ML (+144, model 42.7%)
  - STL @ NYM STL_ML (+112, model 58.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 1524 | 26.0% | 32.4% | 1.246 | 0.803 |
| pitcher strikeouts | 325 | 36.6% | 38.7% | 1.056 | 0.948 |
| batter singles | 761 | 42.3% | 44.8% | 1.058 | 0.946 |
| batter home runs | 761 | 11.0% | 13.1% | 1.187 | 0.845 |
| batter hits | 1569 | 39.5% | 41.9% | 1.063 | 0.941 |
| batter runs scored | 761 | 36.9% | 38.9% | 1.052 | 0.951 |
| batter doubles | 761 | 14.2% | 16.0% | 1.126 | 0.889 |
| batter rbis | 1522 | 19.5% | 23.6% | 1.211 | 0.827 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ CHW | 41.5% | +141 | 4.64 | +242 | -242 |
| CHC @ COL | 8.6% | +1067 | 12.54 | +266 | -266 |
| HOU @ LAA | 49.1% | +104 | 3.65 | +165 | -165 |
| MIL @ OAK | 20.9% | +378 | 7.83 | -125 | +125 |
| TEX @ KCR | 43.0% | +133 | 4.43 | +227 | -227 |

## Team Form (last 10)

**Hot:** MIL 7-3 (L1, +32), LAD 6-4 (W1, +20), TEX 7-3 (L1, +17), NYM 6-4 (L1, +17), LAA 4-6 (W1, +16)

**Cold:** AZ 3-7 (L1, -27), CIN 3-7 (W1, -22), CHC 3-7 (L2, -20), COL 5-5 (W1, -18), MIN 3-7 (L3, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.7 IP across 2 games
- SD: 9.7 IP across 2 games
- TOR: 9.0 IP across 2 games
- CWS: 9.1 IP across 1 games
- MIL: 10.8 IP across 2 games
- LAA: 8.2 IP across 2 games
- BAL: 8.2 IP across 2 games
- HOU: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-09._