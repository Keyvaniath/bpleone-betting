# EdgeStat Daily Brief - 2026-11-07

**Model Confidence: 10.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (7/15 artifacts ok; 8 empty, 0 stale)._ 

_Generated at 2026-11-07T01:42:33 UTC. Game lines source: **DraftKings via ESPN (101 pre-game priced games, observed 2026-11-07T01:42:25 UTC)**._

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 53 | 39.6% | 39.0% | 0.984 | 1.014 |
| batter hits | 244 | 56.6% | 57.5% | 1.017 | 0.984 |

Cumulative graded plays: 21548. Wins: 10035. Hit rate: 46.6%.

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**
- batter total bases: cf +0.0634 (-7 new settled)
- batter hits: cf -0.0042 (-16 new settled)

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↑ 5 -> **7**
  - _1 market(s) had correction_factor swing >0.05 between consecutive refreshes -- prior anchor isn't damping enough. Raising N_PRIOR will stabilize._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-11-06._