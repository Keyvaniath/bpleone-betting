# EdgeStat Daily Brief - 2026-10-27

**Model Confidence: 9.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-10-27T15:12:18 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ TBR - OVER_7.0**
- Market: -110
- Model probability: 66.0%
- Raw edge: +26.02%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:00p ET | MIL @ TBR | Tropicana Field | indoor | OVER_7.0 +26.02% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 332 | 56.0% | 56.7% | 1.012 | 0.988 |
| batter total bases | 83 | 36.1% | 41.1% | 1.134 | 0.890 |

Cumulative graded plays: 19812. Wins: 8795. Hit rate: 44.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| MIL @ TBR | 56.6% | -130 | 2.85 | +186 | -186 |

## Team Form (last 10)

**Hot:** MIL 8-0 (W8, +23), CLE 5-4 (L3, +5), NYY 0-1 (L1, -1), SD 0-1 (L1, -2), TB 5-5 (L3, -3)

**Cold:** CWS 0-3 (L3, -12), LAD 1-4 (L4, -7), ATL 0-1 (L1, -3), TB 5-5 (L3, -3), SD 0-1 (L1, -2)

## Loop Activity (since last refresh)

- Confidence delta: **-0.3**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-10-27._