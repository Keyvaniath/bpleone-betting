# EdgeStat Daily Brief - 2026-11-23

**Model Confidence: 13.3/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-23T02:19:40 UTC. Game lines source: **DraftKings via ESPN (84 pre-game priced games, observed 2026-11-23T02:19:31 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 15 | 46.7% | 42.7% | 0.920 | 1.062 |
| batter hits | 70 | 55.7% | 58.1% | 1.042 | 0.963 |

Cumulative graded plays: 26061. Wins: 13197. Hit rate: 50.6%.

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**
- batter total bases: cf -0.0326 (-4 new settled)
- batter hits: cf -0.0082 (-17 new settled)

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-22._