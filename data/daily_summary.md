# EdgeStat Daily Brief - 2026-07-06

**Model Confidence: 7.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-06T23:12:10 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ LAD - OVER_10.0**
- Market: -110
- Model probability: 84.2%
- Raw edge: +60.76%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | NYM @ ATL | Truist Park | 75F 0mph | ATL_ML +23.41% |
| 7:45p ET | MIL @ STL | Busch Stadium | 76F 3mph | MIL_ML +6.53% |
| 9:40p ET | ARI @ SDP | Petco Park | 66F 4mph | UNDER_8.5 +32.52% |
| 9:45p ET | TOR @ SFG | Oracle Park | 55F 12mph | SFG_ML +24.28% |
| 10:10p ET | COL @ LAD | UNIQLO Field at Dodger Stadium | 65F 4mph | OVER_10.0 +60.76% |

## Parlays - top 5

- **3-leg @ +522 (prob 23.2%, EV +44.12%)**
  - PHI @ KCR UNDER_8.5 (-110, model 54.1%)
  - HOU @ WSN WSN_ML (-118, model 60.8%)
  - NYM @ ATL ATL_ML (-131, model 70.4%)
- **3-leg @ +540 (prob 22.5%, EV +44.04%)**
  - PHI @ KCR UNDER_8.5 (-110, model 54.1%)
  - NYM @ ATL ATL_ML (-131, model 70.4%)
  - MIL @ STL MIL_ML (-111, model 59.1%)
- **3-leg @ +543 (prob 22.4%, EV +43.64%)**
  - PHI @ KCR UNDER_8.5 (-110, model 54.1%)
  - NYM @ ATL ATL_ML (-131, model 70.4%)
  - TOR @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +570 (prob 21.1%, EV +41.32%)**
  - HOU @ WSN WSN_ML (-118, model 60.8%)
  - MIL @ STL MIL_ML (-111, model 59.1%)
  - TOR @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +543 (prob 21.8%, EV +40.28%)**
  - PHI @ KCR UNDER_8.5 (-110, model 54.1%)
  - NYM @ ATL ATL_ML (-131, model 70.4%)
  - NYM @ ATL UNDER_9.0 (-110, model 57.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6520. Wins: 2755. Hit rate: 42.3%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SDP | 34.2% | +193 | 5.24 | +138 | -138 |
| COL @ LAD | 35.9% | +179 | 5.14 | -130 | +130 |
| MIL @ STL | 57.4% | -134 | 2.73 | +255 | -255 |
| NYM @ ATL | 47.8% | +109 | 3.7 | -135 | +135 |
| TOR @ SFG | 43.4% | +130 | 4.51 | -103 | +103 |

## Team Form (last 10)

**Hot:** TB 8-2 (L2, +33), CWS 6-4 (W2, +29), MIA 7-3 (W3, +21), SEA 6-4 (W2, +19), LAD 7-3 (L1, +19)

**Cold:** KC 2-8 (W1, -49), SD 2-8 (W1, -37), NYY 1-9 (L2, -35), LAA 3-7 (L6, -21), NYM 3-7 (W1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 10.1 IP across 2 games
- PIT: 8.1 IP across 2 games
- SD: 9.6 IP across 2 games
- TEX: 8.2 IP across 2 games
- ATL: 8.2 IP across 2 games
- CWS: 10.4 IP across 2 games
- NYY: 8.7 IP across 2 games
- LAA: 8.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-06._