# EdgeStat Daily Brief - 2026-06-23

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-23T23:10:53 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**BAL @ LAA - OVER_9.0**
- Market: -110
- Model probability: 85.4%
- Raw edge: +62.95%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | CHC @ NYM | Citi Field | 64F 3mph | CHC_ML +46.23% |
| 7:10p ET | MIL @ CIN | Great American Ball Park | 67F 5mph | OVER_9.5 +38.52% |
| 7:40p ET | LAD @ MIN | Target Field | 64F 3mph | OVER_9.0 +8.01% |
| 7:40p ET | CLE @ CHW | Rate Field | 60F 5mph | OVER_7.0 +15.77% |
| 7:45p ET | ARI @ STL | Busch Stadium | 72F 4mph | STL_ML +18.1% |
| 8:40p ET | BOS @ COL | Coors Field | 71F 7mph | OVER_10.5 +47.81% |
| 9:38p ET | BAL @ LAA | Angel Stadium | 65F 3mph | OVER_9.0 +62.95% |
| 9:40p ET | ATL @ SDP | Petco Park | 65F 4mph | ATL_ML +28.16% |
| 9:45p ET | OAK @ SFG | Oracle Park | 55F 10mph | OVER_9.0 +37.11% |

## Parlays - top 5

- **2-leg @ +295 (prob 36.1%, EV +42.72%)**
  - SEA @ PIT PIT_ML (+107, model 55.7%)
  - LAD @ MIN OVER_8.5 (-110, model 64.8%)
- **2-leg @ +264 (prob 39.1%, EV +42.67%)**
  - SEA @ PIT UNDER_8.5 (-110, model 60.4%)
  - LAD @ MIN OVER_8.5 (-110, model 64.8%)
- **2-leg @ +264 (prob 39.1%, EV +42.32%)**
  - LAD @ MIN OVER_8.5 (-110, model 64.8%)
  - CLE @ CHW OVER_7.0 (-110, model 60.3%)
- **2-leg @ +255 (prob 39.9%, EV +41.95%)**
  - LAD @ MIN OVER_8.5 (-110, model 64.8%)
  - ARI @ STL STL_ML (-116, model 61.6%)
- **2-leg @ +287 (prob 36.4%, EV +40.73%)**
  - SEA @ PIT PIT_ML (+107, model 55.7%)
  - ATL @ SDP ATL_ML (-115, model 65.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ STL | 41.3% | +142 | 4.3 | +105 | -105 |
| ATL @ SDP | 52.1% | -109 | 3.18 | +370 | -370 |
| BAL @ LAA | 43.0% | +133 | 9.02 | +950 | -950 |
| BOS @ COL | 16.5% | +506 | 8.71 | +364 | -364 |
| CHC @ NYM | 15.8% | +533 | 9.35 | +630 | -630 |
| CLE @ CHW | 38.0% | +163 | 4.88 | +141 | -141 |
| LAD @ MIN | 68.1% | -213 | 1.93 | +382 | -382 |
| MIL @ CIN | 20.4% | +390 | 8.19 | +336 | -336 |
| OAK @ SFG | 26.7% | +274 | 7.03 | +152 | -152 |

## Travel / Rest Flags

- **SEA @ PIT** (home): 2 days rest (+2h tz)
- **SEA @ PIT** (away): 2 days rest (+3h tz)
- **OAK @ SFG** (home): 2 days rest (-3h tz)

## Team Form (last 10)

**Hot:** MIN 7-3 (L1, +22), CHC 6-4 (L1, +22), MIL 6-4 (W2, +17), DET 6-4 (W4, +17), COL 5-5 (W1, +11)

**Cold:** TEX 4-6 (W2, -26), ATL 3-7 (L2, -23), CWS 4-6 (W1, -13), ATH 5-5 (L2, -13), NYM 5-5 (L2, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 9.0 IP across 2 games
- STL: 8.6 IP across 2 games
- TEX: 10.3 IP across 2 games
- PHI: 10.1 IP across 2 games
- KC: 8.4 IP across 2 games
- LAD: 12.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-22._