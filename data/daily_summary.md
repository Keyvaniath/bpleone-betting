# EdgeStat Daily Brief - 2026-06-14

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-14T18:21:57 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ OAK - UNDER_14.0**
- Market: -110
- Model probability: 70.2%
- Raw edge: +34.1%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 3:05p ET | COL @ OAK | Las Vegas Ballpark | 70F 0mph | UNDER_14.0 +34.1% |
| 3:10p ET | CHC @ SFG | Oracle Park | 65F 15mph | OVER_8.0 +12.41% |
| 4:07p ET | TBR @ LAA | Angel Stadium | 82F 10mph | TBR_ML +27.41% |
| 7:20p ET | TEX @ BOS | Fenway Park | 73F 14mph | OVER_9.0 +4.39% |

## Parlays - top 5

- **3-leg @ +639 (prob 20.2%, EV +49.24%)**
  - HOU @ KCR OVER_8.5 (-110, model 64.7%)
  - STL @ MIN STL_ML (-115, model 55.5%)
  - PHI @ MIL MIL_ML (+107, model 56.3%)
- **3-leg @ +849 (prob 15.7%, EV +49.19%)**
  - HOU @ KCR OVER_8.5 (-110, model 64.7%)
  - STL @ MIN STL_ML (-115, model 55.5%)
  - LAD @ CHW CHW_ML (+166, model 43.8%)
- **3-leg @ +610 (prob 20.9%, EV +48.24%)**
  - HOU @ KCR HOU_ML (-101, model 60.4%)
  - STL @ MIN OVER_9.5 (-110, model 62.3%)
  - STL @ MIN STL_ML (-115, model 55.5%)
- **2-leg @ +264 (prob 40.3%, EV +46.77%)**
  - HOU @ KCR OVER_8.5 (-110, model 64.7%)
  - STL @ MIN OVER_9.5 (-110, model 62.3%)
- **3-leg @ +610 (prob 20.6%, EV +46.6%)**
  - HOU @ KCR HOU_ML (-101, model 60.4%)
  - STL @ MIN STL_ML (-115, model 55.5%)
  - LAD @ CHW OVER_9.5 (-110, model 61.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHC @ SFG | 64.9% | -185 | 2.37 | +123 | -123 |
| COL @ OAK | 29.3% | +241 | 6.14 | -127 | +127 |
| HOU @ KCR | 46.3% | +116 | 3.85 | -- | -- |
| LAD @ CHW | 30.5% | +228 | 5.93 | -- | -- |
| PHI @ MIL | 72.6% | -265 | 1.6 | -- | -- |
| STL @ MIN | 27.7% | +261 | 6.41 | -- | -- |
| TBR @ LAA | 38.8% | +158 | 4.94 | +431 | -431 |
| TEX @ BOS | 35.5% | +181 | 5.55 | +173 | -173 |

## Team Form (last 10)

**Hot:** DET 6-4 (L2, +26), STL 7-3 (W1, +24), MIA 8-2 (L1, +23), LAA 6-4 (W4, +19), LAD 6-4 (W1, +16)

**Cold:** AZ 3-7 (L1, -32), MIN 3-7 (L1, -27), COL 3-7 (L3, -22), PIT 3-7 (W1, -19), CIN 3-7 (W1, -17)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 9.2 IP across 2 games
- PHI: 11.1 IP across 2 games
- ATL: 8.2 IP across 2 games
- CWS: 9.0 IP across 2 games
- BAL: 8.2 IP across 2 games
- DET: 8.1 IP across 2 games
- HOU: 10.7 IP across 2 games
- KC: 11.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-13._