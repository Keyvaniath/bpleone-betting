# EdgeStat Daily Brief - 2026-07-03

**Model Confidence: 7.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-03T23:05:40 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIN @ NYY - OVER_9.5**
- Market: -110
- Model probability: 81.3%
- Raw edge: +55.25%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (11 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | MIN @ NYY | Yankee Stadium | 80F 5mph | OVER_9.5 +55.25% |
| 7:10p ET | BAL @ CIN | Great American Ball Park | 86F 3mph | BAL_ML +24.19% |
| 7:10p ET | CHW @ CLE | Progressive Field | 79F 6mph | CHW_ML +21.39% |
| 7:15p ET | NYM @ ATL | Truist Park | 76F 3mph | UNDER_9.0 +15.6% |
| 8:10p ET | SFG @ COL | Coors Field | 75F 7mph | OVER_11.5 +33.27% |
| 8:15p ET | TBR @ HOU | Daikin Park | indoor | TBR_ML +23.5% |
| 9:38p ET | BOS @ LAA | Angel Stadium | 67F 4mph | UNDER_7.5 +10.29% |
| 9:40p ET | MIA @ OAK | Sutter Health Park | 69F 7mph | -- |
| 9:45p ET | MIL @ ARI | Chase Field | indoor | MIL_ML +36.11% |
| 10:10p ET | SDP @ LAD | UNIQLO Field at Dodger Stadium | 60F 3mph | LAD_ML +24.39% |
| 10:10p ET | TOR @ SEA | T-Mobile Park | indoor | UNDER_7.0 +26.05% |

## Parlays - top 5

- **3-leg @ +587 (prob 21.8%, EV +49.95%)**
  - STL @ CHC UNDER_11.0 (-110, model 62.7%)
  - NYM @ ATL ATL_ML (-113, model 58.0%)
  - BOS @ LAA UNDER_7.5 (-110, model 60.0%)
- **2-leg @ +266 (prob 40.9%, EV +49.74%)**
  - CHW @ CLE OVER_8.0 (-110, model 63.5%)
  - TBR @ HOU TBR_ML (-109, model 64.4%)
- **3-leg @ +590 (prob 21.7%, EV +49.63%)**
  - NYM @ ATL UNDER_9.0 (-110, model 58.0%)
  - NYM @ ATL ATL_ML (-113, model 58.0%)
  - TBR @ HOU TBR_ML (-109, model 64.4%)
- **3-leg @ +596 (prob 21.4%, EV +49.18%)**
  - STL @ CHC UNDER_11.0 (-110, model 62.7%)
  - BOS @ LAA UNDER_7.5 (-110, model 60.0%)
  - MIA @ OAK UNDER_10.5 (-110, model 57.0%)
- **3-leg @ +596 (prob 21.4%, EV +49.17%)**
  - CHW @ CLE OVER_8.0 (-110, model 63.5%)
  - BOS @ LAA UNDER_7.5 (-110, model 60.0%)
  - MIL @ ARI UNDER_9.0 (-110, model 56.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ CIN | 42.4% | +136 | 4.37 | +367 | -367 |
| BOS @ LAA | 52.0% | -109 | 3.32 | +172 | -172 |
| CHW @ CLE | 31.3% | +219 | 5.59 | +243 | -243 |
| MIA @ OAK | 28.9% | +246 | 6.44 | +114 | -114 |
| MIL @ ARI | 51.3% | -105 | 3.34 | +758 | -758 |
| MIN @ NYY | 30.6% | +227 | 5.96 | -158 | +158 |
| NYM @ ATL | 44.4% | +125 | 4.05 | +126 | -126 |
| SDP @ LAD | 46.4% | +116 | 3.91 | -466 | +466 |
| SFG @ COL | 50.4% | -102 | 3.46 | +380 | -380 |
| TBR @ HOU | 27.6% | +262 | 6.43 | +309 | -309 |
| TOR @ SEA | 44.5% | +125 | 4.04 | +286 | -286 |

## Travel / Rest Flags

- **BOS @ LAA** (away): 2 days rest (-3h tz)
- **TOR @ SEA** (away): 2 days rest (-3h tz)

## Team Form (last 10)

**Hot:** CHC 9-1 (W5, +42), TB 8-2 (W8, +29), LAD 8-2 (W1, +29), CWS 6-4 (L2, +28), PHI 7-3 (L1, +12)

**Cold:** KC 3-7 (L3, -39), SD 4-6 (L6, -31), NYY 2-8 (L7, -25), NYM 2-8 (L1, -18), ATL 2-8 (L1, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 8.3 IP across 2 games
- SD: 9.0 IP across 2 games
- STL: 8.7 IP across 2 games
- TOR: 8.0 IP across 1 games
- PHI: 8.4 IP across 2 games
- COL: 8.2 IP across 2 games
- KC: 10.0 IP across 2 games
- LAD: 12.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-02._