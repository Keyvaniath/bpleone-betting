# EdgeStat Daily Brief - 2026-08-27

**Model Confidence: 19.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (12/15 artifacts ok; 3 empty, 0 stale)._ 

_Generated at 2026-08-27T23:51:20 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ARI @ SFG - SFG_ML**
- Market: +104
- Model probability: 61.3%
- Raw edge: +25.08%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 9:45p ET | ARI @ SFG | Oracle Park | 63F 4mph | SFG_ML +25.08% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 54 | 63.0% | 57.4% | 0.912 | 1.087 |
| batter total bases | 15 | 40.0% | 50.4% | 1.241 | 0.862 |

Cumulative graded plays: 9654. Wins: 3476. Hit rate: 36.0%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ SFG | 31.6% | +216 | 5.89 | +110 | -110 |

## Team Form (last 10)

**Hot:** MIL 7-3 (W1, +38), CLE 8-2 (W7, +23), KC 9-1 (L1, +22), SD 6-4 (W1, +19), NYY 7-3 (W1, +17)

**Cold:** SEA 6-4 (L1, -33), COL 2-8 (L1, -25), HOU 3-7 (L1, -24), STL 4-6 (W1, -19), DET 2-8 (L1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SF: 8.7 IP across 2 games
- STL: 13.6 IP across 3 games
- TB: 8.2 IP across 2 games
- TEX: 8.2 IP across 2 games
- TOR: 8.2 IP across 2 games
- CWS: 9.4 IP across 2 games
- MIA: 9.2 IP across 2 games
- MIL: 11.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-27._