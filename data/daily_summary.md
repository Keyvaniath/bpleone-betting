# EdgeStat Daily Brief - 2026-07-18

**Model Confidence: 22.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-18T21:42:28 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**PIT @ CLE - UNDER_8.5**
- Market: -110
- Model probability: 81.8%
- Raw edge: +56.14%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | PIT @ CLE | Progressive Field | 71F 12mph | UNDER_8.5 +56.14% |
| 8:08p ET | SFG @ SEA | T-Mobile Park | indoor | SFG_ML +24.1% |
| 10:05p ET | WSN @ OAK | Sutter Health Park | 66F 6mph | OVER_11.5 +43.19% |
| 10:07p ET | DET @ LAA | Angel Stadium | 70F 3mph | DET_ML +7.08% |

## Parlays - top 5

- **3-leg @ +738 (prob 17.4%, EV +45.68%)**
  - PIT @ CLE CLE_ML (-112, model 57.9%)
  - SFG @ SEA SFG_ML (+132, model 53.3%)
  - SFG @ SEA UNDER_7.0 (-110, model 56.3%)
- **3-leg @ +554 (prob 22.2%, EV +45.04%)**
  - PIT @ CLE CLE_ML (-112, model 57.9%)
  - SFG @ SEA SFG_ML (+132, model 53.3%)
  - DET @ LAA DET_ML (-204, model 71.9%)
- **3-leg @ +560 (prob 21.6%, EV +42.32%)**
  - SFG @ SEA SFG_ML (+132, model 53.3%)
  - SFG @ SEA UNDER_7.0 (-110, model 56.3%)
  - DET @ LAA DET_ML (-204, model 71.9%)
- **3-leg @ +738 (prob 16.9%, EV +41.62%)**
  - PIT @ CLE CLE_ML (-112, model 57.9%)
  - SFG @ SEA SFG_ML (+132, model 53.3%)
  - DET @ LAA OVER_8.0 (-110, model 54.8%)
- **3-leg @ +746 (prob 16.4%, EV +38.96%)**
  - SFG @ SEA SFG_ML (+132, model 53.3%)
  - SFG @ SEA UNDER_7.0 (-110, model 56.3%)
  - DET @ LAA OVER_8.0 (-110, model 54.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6331. Wins: 2556. Hit rate: 40.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| DET @ LAA | 31.3% | +219 | 5.92 | +460 | -460 |
| PIT @ CLE | 53.1% | -113 | 2.93 | +138 | -138 |
| SFG @ SEA | 33.8% | +196 | 5.43 | +212 | -212 |
| WSN @ OAK | 34.7% | +188 | 5.43 | +173 | -173 |

## Team Form (last 10)

**Hot:** BOS 10-0 (W10, +43), PIT 7-3 (W4, +25), ATL 5-5 (W2, +20), CWS 6-4 (W4, +19), AZ 6-4 (L1, +15)

**Cold:** ATH 0-10 (L10, -66), TEX 5-5 (L1, -21), PHI 5-5 (L1, -18), TB 4-6 (L3, -17), COL 3-7 (L3, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- BOS: 9.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-18._