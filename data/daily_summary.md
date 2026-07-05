# EdgeStat Daily Brief - 2026-07-05

**Model Confidence: 7.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-05T22:02:37 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**SDP @ LAD - OVER_10.0**
- Market: -110
- Model probability: 75.3%
- Raw edge: +43.79%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (2 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | SDP @ LAD | UNIQLO Field at Dodger Stadium | 69F 6mph | OVER_10.0 +43.79% |
| 9:30p ET | BOS @ LAA | Angel Stadium | 70F 3mph | BOS_ML +23.02% |

## Parlays - top 1

- **2-leg (SGP) @ +210 (prob 39.1%, EV +21.18%)**
  - BOS @ LAA BOS_ML (-160, model 76.1%)
  - BOS @ LAA OVER_8.0 (-110, model 57.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ LAA | 44.2% | +126 | 4.17 | +577 | -577 |
| SDP @ LAD | 23.6% | +324 | 7.45 | -1096 | +1096 |

## Team Form (last 10)

**Hot:** TB 9-1 (L1, +37), CWS 5-5 (W1, +27), LAD 8-2 (W3, +23), MIA 7-3 (W2, +22), COL 5-5 (L1, +12)

**Cold:** KC 2-8 (W1, -49), SD 2-8 (L8, -37), NYY 1-9 (L2, -35), NYM 3-7 (W1, -15), LAA 4-6 (L5, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.2 IP across 2 games
- PIT: 9.4 IP across 3 games
- SD: 9.0 IP across 2 games
- STL: 9.4 IP across 3 games
- MIN: 9.4 IP across 3 games
- ATL: 11.5 IP across 3 games
- NYY: 12.7 IP across 3 games
- MIL: 11.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-04._