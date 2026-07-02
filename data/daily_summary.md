# EdgeStat Daily Brief - 2026-07-02

**Model Confidence: 37.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-02T16:16:09 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHW @ CLE - CHW_ML**
- Market: -107
- Model probability: 74.3%
- Raw edge: +43.81%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | PIT @ PHI | Citizens Bank Park | 104F 8mph | OVER_10.5 +12.93% |
| 2:10p ET | CIN @ MIL | American Family Field | indoor | MIL_ML +19.99% |
| 3:10p ET | MIA @ COL | Coors Field | 91F 10mph | OVER_12.0 +40.1% |
| 6:40p ET | CHW @ CLE | Progressive Field | 86F 4mph | CHW_ML +43.81% |
| 7:15p ET | STL @ ATL | Truist Park | 86F 4mph | OVER_8.5 +27.63% |
| 7:40p ET | TBR @ KCR | Kauffman Stadium | 84F 7mph | TBR_ML +24.81% |
| 8:05p ET | DET @ TEX | Globe Life Field | indoor | OVER_7.5 +19.51% |
| 9:40p ET | LAA @ SEA | T-Mobile Park | indoor | LAA_ML +19.58% |
| 10:10p ET | SDP @ LAD | UNIQLO Field at Dodger Stadium | 60F 3mph | LAD_ML +26.45% |

## Parlays - top 5

- **2-leg @ +168 (prob 56.0%, EV +49.76%)**
  - CIN @ MIL MIL_ML (-199, model 79.9%)
  - TBR @ KCR TBR_ML (-128, model 70.1%)
- **3-leg @ +617 (prob 20.9%, EV +49.6%)**
  - PIT @ PHI PHI_ML (-135, model 59.9%)
  - CIN @ MIL MIL_ML (-199, model 79.9%)
  - LAA @ SEA LAA_ML (+174, model 43.6%)
- **3-leg @ +399 (prob 29.9%, EV +49.52%)**
  - PIT @ PHI PHI_ML (-135, model 59.9%)
  - CIN @ MIL MIL_ML (-199, model 79.9%)
  - DET @ TEX OVER_7.5 (-110, model 62.6%)
- **2-leg @ +388 (prob 30.6%, EV +49.24%)**
  - TBR @ KCR TBR_ML (-128, model 70.1%)
  - LAA @ SEA LAA_ML (+174, model 43.6%)
- **2-leg @ +240 (prob 43.9%, EV +49.16%)**
  - TBR @ KCR TBR_ML (-128, model 70.1%)
  - DET @ TEX OVER_7.5 (-110, model 62.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 23 | 65.2% | 41.1% | 0.643 | 1.278 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHW @ CLE | 43.3% | +131 | 4.29 | +528 | -528 |
| CIN @ MIL | 60.7% | -154 | 2.5 | -212 | +212 |
| DET @ TEX | 48.2% | +108 | 3.65 | +178 | -178 |
| LAA @ SEA | 48.0% | +108 | 3.67 | +142 | -142 |
| MIA @ COL | 26.1% | +283 | 6.67 | +300 | -300 |
| PIT @ PHI | 26.9% | +271 | 6.73 | +107 | -107 |
| SDP @ LAD | 20.6% | +384 | 8.03 | -294 | +294 |
| STL @ ATL | 47.2% | +112 | 3.82 | +302 | -302 |
| TBR @ KCR | 51.3% | -105 | 3.44 | +396 | -396 |

## Travel / Rest Flags

- **SDP @ LAD** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** CHC 9-1 (W5, +42), CWS 6-4 (L1, +28), TB 8-2 (W7, +27), MIA 7-3 (L1, +22), DET 5-5 (W3, +16)

**Cold:** KC 3-7 (L2, -38), SD 4-6 (L5, -27), NYY 2-8 (L7, -25), NYM 2-8 (L1, -18), STL 4-6 (L1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 8.1 IP across 2 games
- TOR: 10.3 IP across 2 games
- ATL: 8.0 IP across 2 games
- NYY: 9.5 IP across 2 games
- BAL: 9.1 IP across 2 games
- BOS: 8.9 IP across 2 games
- HOU: 11.2 IP across 2 games
- LAD: 9.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-01._