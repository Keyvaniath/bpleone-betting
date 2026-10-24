# EdgeStat Daily Brief - 2026-10-24

**Model Confidence: 9.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-10-24T13:11:06 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**TBR @ MIL - OVER_6.5**
- Market: -110
- Model probability: 70.3%
- Raw edge: +34.13%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:00p ET | TBR @ MIL | American Family Field | indoor | OVER_6.5 +34.13% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 81 | 35.8% | 41.4% | 1.154 | 0.876 |
| batter hits | 312 | 53.8% | 56.4% | 1.047 | 0.956 |

Cumulative graded plays: 18597. Wins: 7991. Hit rate: 43.0%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| TBR @ MIL | 62.3% | -166 | 2.36 | +167 | -167 |

## Team Form (last 10)

**Hot:** MIL 7-1 (W6, +13), TB 6-3 (L1, +10), CLE 5-5 (L3, +4), SD 1-2 (L1, -2), ATL 1-2 (L2, -4)

**Cold:** CWS 1-3 (L3, -11), LAD 2-5 (L4, -6), NYY 0-2 (L2, -4), ATL 1-2 (L2, -4), SD 1-2 (L1, -2)

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-10-23._