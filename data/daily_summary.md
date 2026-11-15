# EdgeStat Daily Brief - 2026-11-15

**Model Confidence: 13.8/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-15T01:44:49 UTC. Game lines source: **DraftKings via ESPN (40 pre-game priced games, observed 2026-11-15T01:44:39 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 140 | 57.1% | 58.0% | 1.014 | 0.987 |
| batter total bases | 30 | 46.7% | 40.2% | 0.866 | 1.129 |

Cumulative graded plays: 23862. Wins: 11695. Hit rate: 49.0%.

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**
- batter total bases: cf -0.0721 (-5 new settled)
- batter hits: cf +0.0238 (-18 new settled)

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-14._