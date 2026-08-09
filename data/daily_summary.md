# EdgeStat Daily Brief - 2026-08-09

**Model Confidence: 20.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-09T22:38:51 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**HOU @ SDP - HOU_ML**
- Market: +103
- Model probability: 56.9%
- Raw edge: +15.5%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:20p ET | HOU @ SDP | Petco Park | 72F 3mph | HOU_ML +15.5% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 7372. Wins: 3029. Hit rate: 41.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| HOU @ SDP | 51.2% | -105 | 3.39 | +224 | -224 |

## Team Form (last 10)

**Hot:** DET 7-3 (W1, +60), BOS 8-2 (L2, +35), ATL 8-2 (W1, +24), HOU 7-3 (L1, +22), CHC 7-3 (W1, +18)

**Cold:** ATH 2-8 (W2, -36), SEA 3-7 (L3, -25), LAA 3-7 (L2, -23), KC 3-7 (L1, -17), BAL 5-5 (L3, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.6 IP across 3 games
- PIT: 14.3 IP across 3 games
- SF: 9.8 IP across 2 games
- STL: 10.4 IP across 3 games
- TOR: 13.8 IP across 3 games
- PHI: 13.5 IP across 3 games
- CWS: 10.5 IP across 2 games
- MIA: 11.3 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-09._