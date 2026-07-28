# EdgeStat Daily Brief - 2026-07-28

**Model Confidence: 22.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-28T23:03:24 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYY @ CHW - OVER_8.0**
- Market: -110
- Model probability: 74.3%
- Raw edge: +41.79%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | CLE @ CIN | Great American Ball Park | 75F 4mph | -- |
| 7:40p ET | KCR @ MIN | Target Field | 80F 4mph | OVER_9.0 +25.85% |
| 7:40p ET | NYY @ CHW | Rate Field | 65F 10mph | OVER_8.0 +41.79% |
| 7:45p ET | CHC @ STL | Busch Stadium | 81F 6mph | OVER_8.5 +37.93% |
| 9:38p ET | HOU @ LAA | Angel Stadium | 70F 4mph | UNDER_9.5 +12.75% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 75F 6mph | UNDER_10.5 +28.57% |
| 9:40p ET | COL @ SDP | Petco Park | 68F 3mph | OVER_8.5 +9.44% |
| 9:45p ET | MIL @ SFG | Oracle Park | 60F 5mph | UNDER_8.0 +22.8% |
| 10:10p ET | SEA @ LAD | UNIQLO Field at Dodger Stadium | 68F 2mph | LAD_ML +32.93% |

## Parlays - top 5

- **2-leg @ +264 (prob 40.9%, EV +49.23%)**
  - CHC @ STL OVER_9.0 (-110, model 65.3%)
  - SEA @ LAD UNDER_9.5 (-110, model 62.7%)
- **2-leg @ +264 (prob 40.6%, EV +47.82%)**
  - PHI @ MIA OVER_8.0 (-110, model 62.2%)
  - CHC @ STL OVER_9.0 (-110, model 65.3%)
- **2-leg @ +255 (prob 40.9%, EV +45.24%)**
  - ARI @ PIT PIT_ML (-116, model 65.1%)
  - SEA @ LAD UNDER_9.5 (-110, model 62.7%)
- **2-leg @ +264 (prob 39.6%, EV +44.52%)**
  - BAL @ DET OVER_9.0 (-110, model 60.8%)
  - CHC @ STL OVER_9.0 (-110, model 65.3%)
- **2-leg @ +255 (prob 40.5%, EV +43.87%)**
  - ARI @ PIT PIT_ML (-116, model 65.1%)
  - PHI @ MIA OVER_8.0 (-110, model 62.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6680. Wins: 2769. Hit rate: 41.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ OAK | 39.5% | +153 | 4.77 | +279 | -279 |
| CHC @ STL | 40.5% | +147 | 4.32 | +272 | -272 |
| CLE @ CIN | 39.3% | +154 | 12.89 | +186 | -186 |
| COL @ SDP | 43.3% | +131 | 4.21 | +151 | -151 |
| HOU @ LAA | 50.3% | -101 | 3.5 | +167 | -167 |
| KCR @ MIN | 43.9% | +128 | 4.04 | +115 | -115 |
| MIL @ SFG | 56.8% | -132 | 2.91 | +287 | -287 |
| NYY @ CHW | 40.9% | +144 | 4.23 | +270 | -270 |
| SEA @ LAD | 47.2% | +112 | 3.8 | -219 | +219 |

## Travel / Rest Flags

- **COL @ SDP** (home): 2 days rest (-3h tz)
- **COL @ SDP** (away): 2 days rest (-2h tz)
- **SEA @ LAD** (home): 2 days rest (-3h tz)
- **SEA @ LAD** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** CHC 6-4 (W1, +28), SD 5-5 (W3, +22), WSH 6-4 (L1, +22), BOS 8-2 (W2, +19), NYM 5-5 (W2, +14)

**Cold:** COL 3-7 (L2, -23), MIA 1-9 (W1, -21), ATH 3-7 (L3, -21), TOR 4-6 (W1, -18), CLE 3-7 (L5, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.3 IP across 2 games
- STL: 8.4 IP across 2 games
- PHI: 8.1 IP across 2 games
- CWS: 9.4 IP across 2 games
- NYY: 9.6 IP across 2 games
- BAL: 10.3 IP across 2 games
- BOS: 8.2 IP across 2 games
- HOU: 10.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-27._