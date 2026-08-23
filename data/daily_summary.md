# EdgeStat Daily Brief - 2026-08-23

**Model Confidence: 19.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-23T22:28:06 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ATL @ MIL - MIL_ML**
- Market: -110
- Model probability: 62.1%
- Raw edge: +18.51%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | ATL @ MIL | Journey Bank Ballpark | 70F 0mph | MIL_ML +18.51% |

## Parlays - top 1

- **2-leg (SGP) @ +254 (prob 30.9%, EV +9.57%)**
  - ATL @ MIL MIL_ML (-117, model 62.1%)
  - ATL @ MIL OVER_7.5 (-110, model 57.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |

Cumulative graded plays: 9776. Wins: 3597. Hit rate: 36.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ MIL | 41.4% | +141 | 4.41 | +107 | -107 |

## Team Form (last 10)

**Hot:** MIL 7-3 (W3, +32), PHI 9-1 (W9, +28), LAA 6-4 (W1, +25), SD 7-3 (W2, +18), BOS 6-4 (W2, +17)

**Cold:** SEA 6-4 (W2, -22), HOU 4-6 (L1, -18), TB 3-7 (W1, -18), TEX 4-6 (L1, -17), MIN 4-6 (L2, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.2 IP across 2 games
- SD: 8.1 IP across 2 games
- STL: 11.5 IP across 3 games
- TOR: 11.5 IP across 3 games
- CWS: 16.1 IP across 3 games
- MIA: 11.0 IP across 3 games
- NYY: 11.8 IP across 3 games
- AZ: 8.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-23._