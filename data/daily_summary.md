# EdgeStat Daily Brief - 2026-07-07

**Model Confidence: 22.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-07-07T23:09:19 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ LAD - OVER_9.5**
- Market: -110
- Model probability: 74.6%
- Raw edge: +42.48%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:45p ET | MIL @ STL | Busch Stadium | 79F 4mph | OVER_8.5 +25.3% |
| 6:35p ET | CHC @ BAL | Oriole Park at Camden Yards | 75F 7mph | OVER_9.0 +19.9% |
| 7:10p ET | KCR @ NYM | Citi Field | 66F 6mph | KCR_ML +30.81% |
| 7:10p ET | PHI @ CIN | Great American Ball Park | 75F 4mph | OVER_9.0 +20.13% |
| 7:40p ET | CLE @ MIN | Target Field | 76F 5mph | MIN_ML +27.77% |
| 7:40p ET | BOS @ CHW | Rate Field | 70F 1mph | OVER_8.5 +4.58% |
| 8:05p ET | LAA @ TEX | Globe Life Field | indoor | OVER_7.0 +33.37% |
| 9:40p ET | ARI @ SDP | Petco Park | 66F 3mph | ARI_ML +27.08% |
| 9:45p ET | TOR @ SFG | Oracle Park | 55F 16mph | SFG_ML +17.28% |
| 10:10p ET | COL @ LAD | UNIQLO Field at Dodger Stadium | 64F 4mph | OVER_9.5 +42.48% |

## Parlays - top 5

- **2-leg @ +276 (prob 39.7%, EV +49.42%)**
  - ATL @ PIT PIT_ML (-149, model 72.6%)
  - KCR @ NYM KCR_ML (+125, model 54.7%)
- **2-leg @ +285 (prob 38.3%, EV +47.28%)**
  - NYY @ TBR NYY_ML (+105, model 57.5%)
  - CLE @ MIN MIN_ML (-114, model 66.6%)
- **2-leg @ +232 (prob 44.3%, EV +47.2%)**
  - SEA @ MIA MIA_ML (-130, model 66.6%)
  - CLE @ MIN MIN_ML (-114, model 66.6%)
- **2-leg @ +258 (prob 40.8%, EV +46.39%)**
  - OAK @ DET OVER_8.0 (-110, model 61.4%)
  - CLE @ MIN MIN_ML (-114, model 66.6%)
- **2-leg @ +291 (prob 37.4%, EV +46.34%)**
  - NYY @ TBR NYY_ML (+105, model 57.5%)
  - PHI @ CIN OVER_9.0 (-110, model 65.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6498. Wins: 2720. Hit rate: 41.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SDP | 18.1% | +452 | 8.4 | +314 | -314 |
| BOS @ CHW | 26.4% | +279 | 6.68 | +166 | -166 |
| CHC @ BAL | -- | -- | -- | +272 | -272 |
| CLE @ MIN | 52.4% | -110 | 3.22 | -118 | +118 |
| COL @ LAD | 38.4% | +161 | 4.8 | -280 | +280 |
| KCR @ NYM | 22.5% | +344 | 7.16 | +260 | -260 |
| LAA @ TEX | 30.9% | +224 | 5.88 | +109 | -109 |
| MIL @ STL | 48.4% | +107 | 3.56 | +225 | -225 |
| PHI @ CIN | 42.1% | +137 | 4.42 | +398 | -398 |
| TOR @ SFG | 39.2% | +155 | 5.17 | +125 | -125 |

## Travel / Rest Flags

- **OAK @ DET** (away): 2 days rest (+3h tz)
- **SEA @ MIA** (home): 2 days rest (+3h tz)
- **SEA @ MIA** (away): 2 days rest (+3h tz)
- **BOS @ CHW** (away): 2 days rest (+2h tz)
- **LAA @ TEX** (away): 2 days rest (+2h tz)

## Team Form (last 10)

**Hot:** CWS 6-4 (W2, +29), LAD 8-2 (W1, +26), MIA 7-3 (W3, +21), SEA 6-4 (W2, +19), TB 7-3 (L3, +18)

**Cold:** SD 1-9 (L1, -51), KC 3-7 (W2, -33), NYY 2-8 (W1, -28), TOR 3-7 (L3, -23), LAA 3-7 (L6, -21)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATL: 9.2 IP across 2 games
- COL: 9.1 IP across 2 games
- KC: 8.0 IP across 2 games
- LAD: 9.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-07._