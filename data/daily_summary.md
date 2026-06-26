# EdgeStat Daily Brief - 2026-06-26

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-26T23:14:04 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**KCR @ CHW - OVER_8.5**
- Market: -110
- Model probability: 93.0%
- Raw edge: +77.44%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | KCR @ CHW | Rate Field | 63F 8mph | OVER_8.5 +77.44% |
| 7:45p ET | CHC @ MIL | American Family Field | indoor | OVER_7.0 +28.28% |
| 8:10p ET | COL @ MIN | Target Field | 67F 6mph | OVER_9.0 +55.32% |
| 8:15p ET | MIA @ STL | Busch Stadium | 73F 4mph | OVER_8.0 +13.95% |
| 9:38p ET | OAK @ LAA | Angel Stadium | 64F 6mph | OVER_8.5 +31.67% |
| 9:45p ET | LAD @ SDP | Petco Park | 64F 2mph | LAD_ML +23.06% |
| 10:15p ET | ATL @ SFG | Oracle Park | 58F 8mph | -- |

## Parlays - top 5

- **3-leg @ +519 (prob 24.2%, EV +49.96%)**
  - WSN @ BAL OVER_9.0 (-110, model 62.4%)
  - ARI @ TBR TBR_ML (-143, model 70.6%)
  - MIA @ STL OVER_8.0 (-110, model 54.9%)
- **3-leg @ +516 (prob 24.3%, EV +49.96%)**
  - NYY @ BOS UNDER_9.0 (-110, model 60.0%)
  - MIA @ STL OVER_8.0 (-110, model 54.9%)
  - LAD @ SDP LAD_ML (-145, model 73.9%)
- **3-leg @ +519 (prob 24.2%, EV +49.95%)**
  - HOU @ DET UNDER_9.0 (-110, model 57.2%)
  - ARI @ TBR TBR_ML (-143, model 70.6%)
  - NYY @ BOS UNDER_9.0 (-110, model 60.0%)
- **2-leg @ +187 (prob 52.2%, EV +49.91%)**
  - ARI @ TBR TBR_ML (-143, model 70.6%)
  - LAD @ SDP LAD_ML (-145, model 73.9%)
- **3-leg @ +301 (prob 37.3%, EV +49.73%)**
  - HOU @ DET UNDER_9.0 (-110, model 57.2%)
  - CIN @ PIT PIT_ML (-190, model 81.7%)
  - CHC @ MIL MIL_ML (-265, model 79.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ TBR | 29.1% | +244 | 6.17 | -- | -- |
| ATL @ SFG | 50.9% | -104 | 3.56 | +198 | -198 |
| CHC @ MIL | 42.2% | +137 | 4.31 | -222 | +222 |
| COL @ MIN | 30.7% | +226 | 5.79 | -104 | +104 |
| KCR @ CHW | 13.6% | +636 | 9.44 | -102 | +102 |
| LAD @ SDP | 44.8% | +123 | 3.98 | +537 | -537 |
| MIA @ STL | 46.7% | +114 | 3.74 | +234 | -234 |
| NYY @ BOS | 36.5% | +174 | 5.03 | -- | -- |
| OAK @ LAA | 50.4% | -102 | 3.55 | +192 | -192 |
| PHI @ NYM | 34.4% | +190 | 5.33 | -- | -- |
| SEA @ CLE | 37.0% | +170 | 4.97 | -- | -- |
| TEX @ TOR | 24.5% | +309 | 7.04 | -- | -- |
| WSN @ BAL | 45.9% | +118 | 3.89 | -- | -- |

## Travel / Rest Flags

- **WSN @ BAL** (home): 2 days rest (+3h tz)
- **LAD @ SDP** (away): 2 days rest (-2h tz)

## Team Form (last 10)

**Hot:** PHI 7-3 (W3, +27), CHC 7-3 (W4, +24), MIL 7-3 (W4, +15), MIN 6-4 (L3, +14), COL 6-4 (W1, +14)

**Cold:** NYM 2-8 (L6, -36), ATL 2-8 (L4, -27), SEA 4-6 (L2, -25), TEX 4-6 (W1, -19), STL 4-6 (L2, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 11.2 IP across 2 games
- CWS: 8.2 IP across 1 games
- CHC: 12.3 IP across 3 games
- NYM: 13.1 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-25._