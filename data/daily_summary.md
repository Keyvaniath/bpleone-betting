# EdgeStat Daily Brief - 2026-06-25

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-25T16:31:00 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ NYM - CHC_ML**
- Market: -108
- Model probability: 80.7%
- Raw edge: +55.35%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | SEA @ PIT | PNC Park | 80F 10mph | PIT_ML +12.38% |
| 3:45p ET | OAK @ SFG | Oracle Park | 62F 18mph | OVER_8.0 +49.41% |
| 6:40p ET | HOU @ DET | Comerica Park | 68F 6mph | OVER_9.0 +21.27% |
| 6:45p ET | PHI @ WSN | Nationals Park | 76F 12mph | WSN_ML +25.74% |
| 7:07p ET | TEX @ TOR | Rogers Centre | indoor | TEX_ML +12.99% |
| 7:10p ET | CHC @ NYM | Citi Field | 70F 10mph | CHC_ML +55.35% |
| 7:10p ET | NYY @ BOS | Fenway Park | 70F 8mph | NYY_ML +45.31% |
| 7:45p ET | ARI @ STL | Busch Stadium | 76F 2mph | STL_ML +10.14% |

## Parlays - top 5

- **2-leg @ +264 (prob 41.0%, EV +49.55%)**
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
- **3-leg @ +727 (prob 18.1%, EV +49.35%)**
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - TEX @ TOR TEX_ML (+127, model 49.8%)
  - CHC @ NYM UNDER_8.5 (-110, model 57.1%)
- **3-leg @ +716 (prob 18.3%, EV +49.07%)**
  - SEA @ PIT PIT_ML (+124, model 49.5%)
  - CHC @ NYM UNDER_8.5 (-110, model 57.1%)
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
- **3-leg @ +529 (prob 23.7%, EV +49.05%)**
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
  - ARI @ STL STL_ML (-138, model 63.9%)
  - ARI @ STL OVER_9.0 (-110, model 57.5%)
- **3-leg @ +638 (prob 20.1%, EV +48.12%)**
  - SEA @ PIT PIT_ML (+124, model 49.5%)
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - ARI @ STL STL_ML (-138, model 63.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ STL | 26.0% | +284 | 6.62 | -106 | +106 |
| CHC @ NYM | 33.7% | +196 | 5.73 | +792 | -792 |
| HOU @ DET | 43.6% | +129 | 4.3 | +204 | -204 |
| NYY @ BOS | 49.0% | +104 | 3.69 | +1238 | -1238 |
| OAK @ SFG | 25.4% | +294 | 7.67 | -164 | +164 |
| PHI @ WSN | 43.0% | +132 | 4.35 | +156 | -156 |
| SEA @ PIT | 57.0% | -133 | 2.99 | +176 | -176 |
| TEX @ TOR | 39.8% | +151 | 4.6 | +176 | -176 |

## Travel / Rest Flags

- **NYY @ BOS** (home): travel + back-to-back (+2h tz shift)

## Team Form (last 10)

**Hot:** CHC 7-3 (W3, +28), PHI 6-4 (W2, +18), MIL 7-3 (W4, +15), KC 6-4 (L1, +15), MIN 6-4 (L3, +14)

**Cold:** NYM 3-7 (L5, -28), ATL 2-8 (L4, -27), SEA 4-6 (L1, -26), ATH 3-7 (L4, -20), TEX 4-6 (L2, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 11.4 IP across 2 games
- TOR: 9.5 IP across 2 games
- MIN: 10.0 IP across 2 games
- CWS: 10.4 IP across 2 games
- LAA: 8.6 IP across 2 games
- CHC: 11.2 IP across 3 games
- HOU: 9.1 IP across 2 games
- WSH: 11.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-24._