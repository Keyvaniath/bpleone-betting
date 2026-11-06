# EdgeStat Daily Brief - 2026-11-06

**Model Confidence: 10.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-06T02:14:52 UTC. Game lines source: **DraftKings via ESPN (96 pre-game priced games, observed 2026-11-06T02:14:43 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 260 | 56.1% | 56.9% | 1.012 | 0.988 |
| batter total bases | 60 | 36.7% | 38.8% | 1.057 | 0.951 |

Cumulative graded plays: 21415. Wins: 9924. Hit rate: 46.3%.

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**
- batter total bases: cf +0.0485 (-3 new settled)
- batter hits: cf -0.0031 (-1 new settled)

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-05._