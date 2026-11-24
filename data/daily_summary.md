# EdgeStat Daily Brief - 2026-11-24

**Model Confidence: 12.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-24T01:42:47 UTC. Game lines source: **DraftKings via ESPN (94 pre-game priced games, observed 2026-11-24T01:42:38 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 12 | 50.0% | 43.1% | 0.874 | 1.097 |
| batter hits | 52 | 48.1% | 58.0% | 1.202 | 0.849 |

Cumulative graded plays: 26328. Wins: 13380. Hit rate: 50.8%.

## Loop Activity (since last refresh)

- Confidence delta: **-1.6**
- batter hits: cf -0.1134 (-18 new settled)
- batter total bases: cf +0.0348 (-3 new settled)

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-23._