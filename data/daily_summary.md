# EdgeStat Daily Brief - 2026-07-19

**Model Confidence: 22.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-19T22:51:58 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ NYY - LAD_ML**
- Market: -139
- Model probability: 69.3%
- Raw edge: +19.18%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | LAD @ NYY | Yankee Stadium | 66F 6mph | LAD_ML +19.18% |

## Parlays - top 1

- **2-leg (SGP) @ +240 (prob 37.1%, EV +26.06%)**
  - LAD @ NYY LAD_ML (-128, model 69.3%)
  - LAD @ NYY OVER_9.0 (-110, model 60.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6407. Wins: 2591. Hit rate: 40.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAD @ NYY | 51.3% | -105 | 3.36 | +386 | -386 |

## Team Form (last 10)

**Hot:** BOS 10-0 (W10, +40), PIT 7-3 (W2, +27), DET 8-2 (W2, +27), CWS 6-4 (W1, +20), CHC 7-3 (W2, +18)

**Cold:** ATH 1-9 (W1, -45), TEX 5-5 (L1, -26), PHI 5-5 (L1, -20), TB 4-6 (L5, -17), KC 4-6 (L1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 11.7 IP across 3 games
- SD: 14.2 IP across 3 games
- TB: 13.3 IP across 4 games
- TEX: 9.0 IP across 3 games
- TOR: 9.6 IP across 3 games
- MIN: 11.2 IP across 3 games
- PHI: 8.3 IP across 2 games
- ATL: 10.7 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-19._