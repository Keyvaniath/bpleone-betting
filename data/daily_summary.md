# EdgeStat Daily Brief - 2026-11-18

**Model Confidence: 13.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-18T03:31:28 UTC. Game lines source: **DraftKings via ESPN (78 pre-game priced games, observed 2026-11-18T03:31:19 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 22 | 50.0% | 41.3% | 0.833 | 1.157 |
| batter hits | 105 | 56.2% | 58.0% | 1.032 | 0.971 |

Cumulative graded plays: 24986. Wins: 12438. Hit rate: 49.8%.

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**
- batter hits: cf +0.0073 (-17 new settled)
- batter total bases: cf -0.0011 (-2 new settled)

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-17._