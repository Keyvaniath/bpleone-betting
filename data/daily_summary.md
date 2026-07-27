# EdgeStat Daily Brief - 2026-07-27

**Model Confidence: 23.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-07-27T23:08:40 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**HOU @ LAA - OVER_8.0**
- Market: -110
- Model probability: 70.7%
- Raw edge: +34.93%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | ATL @ NYM | Citi Field | 72F 4mph | NYM_ML +5.84% |
| 7:40p ET | NYY @ CHW | Rate Field | 73F 5mph | NYY_ML +29.07% |
| 7:45p ET | CHC @ STL | Busch Stadium | 88F 4mph | CHC_ML +28.23% |
| 9:38p ET | HOU @ LAA | Angel Stadium | 71F 5mph | OVER_8.0 +34.93% |
| 9:40p ET | BOS @ OAK | Sutter Health Park | 71F 6mph | BOS_ML +5.45% |
| 9:45p ET | MIL @ SFG | Oracle Park | 58F 3mph | OVER_7.5 +30.75% |

## Parlays - top 5

- **3-leg @ +558 (prob 22.7%, EV +49.5%)**
  - CLE @ CIN OVER_8.5 (-110, model 57.8%)
  - NYY @ CHW OVER_8.5 (-110, model 59.5%)
  - CHC @ STL CHC_ML (-124, model 66.0%)
- **3-leg @ +851 (prob 15.7%, EV +49.05%)**
  - PHI @ MIA MIA_ML (+161, model 45.6%)
  - CLE @ CIN OVER_8.5 (-110, model 57.8%)
  - NYY @ CHW OVER_8.5 (-110, model 59.5%)
- **3-leg @ +599 (prob 21.3%, EV +48.86%)**
  - ATL @ NYM ATL_ML (-109, model 55.2%)
  - NYY @ CHW OVER_8.5 (-110, model 59.5%)
  - HOU @ LAA OVER_8.5 (-110, model 64.9%)
- **2-leg @ +264 (prob 40.7%, EV +48.48%)**
  - ATL @ NYM UNDER_8.5 (-110, model 62.8%)
  - HOU @ LAA OVER_8.5 (-110, model 64.9%)
- **3-leg @ +687 (prob 18.8%, EV +47.99%)**
  - SEA @ TEX TEX_ML (+116, model 50.2%)
  - CLE @ CIN OVER_8.5 (-110, model 57.8%)
  - HOU @ LAA OVER_8.5 (-110, model 64.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6664. Wins: 2758. Hit rate: 41.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ NYM | 54.8% | -121 | 3.04 | +220 | -220 |
| BOS @ OAK | 24.2% | +313 | 7.26 | +298 | -298 |
| CHC @ STL | 29.3% | +241 | 6.29 | +409 | -409 |
| HOU @ LAA | 56.6% | -130 | 2.9 | +147 | -147 |
| MIL @ SFG | 41.4% | +142 | 4.49 | +231 | -231 |
| NYY @ CHW | 29.1% | +243 | 6.16 | +537 | -537 |

## Travel / Rest Flags

- **HOU @ LAA** (away): travel + back-to-back (-2h tz shift)
- **BOS @ OAK** (home): travel + back-to-back (-2h tz shift)
- **BOS @ OAK** (away): travel + back-to-back (-3h tz shift)
- **MIL @ SFG** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +28), SD 5-5 (W3, +22), WSH 6-4 (W2, +21), CWS 6-4 (W1, +19), BOS 8-2 (W1, +19)

**Cold:** TOR 3-7 (L1, -27), ATH 3-7 (L2, -27), MIA 0-10 (L10, -25), COL 3-7 (L2, -23), CLE 3-7 (L5, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.4 IP across 2 games
- SD: 9.3 IP across 2 games
- MIN: 8.1 IP across 2 games
- PHI: 9.3 IP across 2 games
- NYY: 8.1 IP across 2 games
- BAL: 8.4 IP across 2 games
- BOS: 9.0 IP across 2 games
- NYM: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-26._