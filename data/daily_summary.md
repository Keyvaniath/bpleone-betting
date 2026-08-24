# EdgeStat Daily Brief - 2026-08-24

**Model Confidence: 19.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-24T21:23:00 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ WSN - OVER_8.0**
- Market: -110
- Model probability: 90.3%
- Raw edge: +72.31%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | TBR @ DET | Comerica Park | 70F 4mph | OVER_7.5 +6.64% |
| 6:40p ET | BOS @ MIA | loanDepot park | indoor | BOS_ML +7.27% |
| 6:45p ET | COL @ WSN | Nationals Park | 70F 4mph | OVER_8.0 +72.31% |
| 7:40p ET | TEX @ CHW | Rate Field | 65F 7mph | CHW_ML +38.65% |
| 9:38p ET | CLE @ LAA | Angel Stadium | 74F 4mph | CLE_ML +10.2% |
| 9:40p ET | CHC @ ARI | Chase Field | indoor | OVER_8.5 +50.67% |
| 9:40p ET | PIT @ SDP | Petco Park | 72F 2mph | PIT_ML +24.52% |
| 9:40p ET | MIN @ OAK | Sutter Health Park | 71F 7mph | OVER_9.5 +67.58% |
| 9:40p ET | PHI @ SEA | T-Mobile Park | indoor | PHI_ML +21.68% |
| 9:45p ET | CIN @ SFG | Oracle Park | 58F 11mph | CIN_ML +23.1% |

## Parlays - top 5

- **2-leg @ +287 (prob 38.7%, EV +49.78%)**
  - PHI @ SEA PHI_ML (-101, model 61.1%)
  - CIN @ SFG CIN_ML (-106, model 63.3%)
- **2-leg @ +271 (prob 40.3%, EV +49.59%)**
  - PIT @ SDP PIT_ML (-106, model 64.1%)
  - PHI @ SEA UNDER_7.5 (-110, model 62.9%)
- **3-leg @ +549 (prob 23.0%, EV +49.53%)**
  - TBR @ DET TBR_ML (-128, model 58.7%)
  - TEX @ CHW OVER_8.0 (-110, model 62.3%)
  - PHI @ SEA UNDER_7.5 (-110, model 62.9%)
- **3-leg @ +462 (prob 26.5%, EV +48.69%)**
  - CLE @ LAA CLE_ML (-144, model 65.0%)
  - MIN @ OAK MIN_ML (-150, model 66.5%)
  - PHI @ SEA PHI_ML (-101, model 61.1%)
- **2-leg @ +187 (prob 51.8%, EV +48.62%)**
  - COL @ WSN WSN_ML (-210, model 81.8%)
  - CIN @ SFG CIN_ML (-106, model 63.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |

Cumulative graded plays: 9810. Wins: 3615. Hit rate: 36.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ MIA | 47.5% | +111 | 3.72 | +280 | -280 |
| CHC @ ARI | 23.4% | +327 | 7.26 | +576 | -576 |
| CIN @ SFG | 34.2% | +193 | 5.76 | +308 | -308 |
| CLE @ LAA | 57.8% | -137 | 2.81 | +340 | -340 |
| COL @ WSN | 38.1% | +163 | 4.71 | -276 | +276 |
| MIN @ OAK | 32.7% | +206 | 5.78 | +312 | -312 |
| PHI @ SEA | 45.7% | +119 | 3.91 | +296 | -296 |
| PIT @ SDP | 51.8% | -108 | 3.33 | +314 | -314 |
| TBR @ DET | 43.8% | +128 | 4.19 | +253 | -253 |
| TEX @ CHW | 31.3% | +219 | 5.53 | -130 | +130 |

## Travel / Rest Flags

- **COL @ WSN** (away): travel + back-to-back (+2h tz shift)
- **CLE @ LAA** (home): travel + back-to-back (-2h tz shift)
- **MIN @ OAK** (home): travel + back-to-back (-2h tz shift)
- **PHI @ SEA** (away): travel + back-to-back (-3h tz shift)
- **CIN @ SFG** (home): travel + back-to-back (-3h tz shift)

## Team Form (last 10)

**Hot:** MIL 7-3 (L1, +31), PHI 9-1 (W9, +28), KC 9-1 (W8, +23), LAA 5-5 (L1, +20), BOS 7-3 (W3, +20)

**Cold:** SEA 6-4 (L1, -34), MIN 4-6 (L3, -20), COL 3-7 (L6, -18), CIN 3-7 (L1, -18), TB 3-7 (W1, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.0 IP across 2 games
- PIT: 10.0 IP across 2 games
- SD: 9.1 IP across 2 games
- CWS: 13.1 IP across 2 games
- NYY: 8.8 IP across 2 games
- AZ: 9.8 IP across 2 games
- CHC: 8.5 IP across 2 games
- COL: 10.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-23._