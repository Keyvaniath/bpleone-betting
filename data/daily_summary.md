# EdgeStat Daily Brief - 2026-08-13

**Model Confidence: 22.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-13T22:51:57 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ LAD - OVER_7.5**
- Market: -110
- Model probability: 72.5%
- Raw edge: +38.46%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:30p ET | PHI @ MIN | Field of Dreams | 70F 0mph | MIN_ML +20.11% |
| 10:07p ET | TEX @ LAA | Angel Stadium | 70F 4mph | OVER_7.5 +3.33% |
| 10:10p ET | MIL @ LAD | UNIQLO Field at Dodger Stadium | 68F 3mph | OVER_7.5 +38.46% |

## Parlays - top 4

- **3-leg @ +593 (prob 21.6%, EV +49.49%)**
  - PHI @ MIN MIN_ML (-111, model 63.7%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
  - TEX @ LAA OVER_7.5 (-110, model 54.1%)
- **2-leg (SGP) @ +263 (prob 34.9%, EV +26.52%)**
  - PHI @ MIN MIN_ML (-111, model 63.7%)
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
- **2-leg @ +263 (prob 34.5%, EV +25.17%)**
  - PHI @ MIN MIN_ML (-111, model 63.7%)
  - TEX @ LAA OVER_7.5 (-110, model 54.1%)
- **2-leg @ +264 (prob 33.9%, EV +23.42%)**
  - PHI @ MIN OVER_8.5 (-110, model 62.6%)
  - TEX @ LAA OVER_7.5 (-110, model 54.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8405. Wins: 3291. Hit rate: 39.2%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| MIL @ LAD | 38.4% | +161 | 4.88 | +196 | -196 |
| PHI @ MIN | 40.1% | +150 | 4.57 | -105 | +105 |
| TEX @ LAA | 50.4% | -102 | 3.52 | +284 | -284 |

## Team Form (last 10)

**Hot:** DET 7-3 (W1, +38), BOS 5-5 (W1, +26), CHC 8-2 (W3, +25), TB 9-1 (W9, +23), STL 7-3 (W2, +19)

**Cold:** ATH 2-8 (L3, -37), SEA 3-7 (W1, -28), LAA 5-5 (W2, -13), LAD 4-6 (W3, -12), KC 3-7 (L4, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.0 IP across 2 games
- PIT: 8.2 IP across 3 games
- SD: 10.0 IP across 2 games
- TOR: 9.6 IP across 3 games
- CWS: 11.3 IP across 3 games
- NYY: 10.7 IP across 3 games
- CIN: 11.7 IP across 3 games
- DET: 8.9 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-12._