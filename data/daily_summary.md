# EdgeStat Daily Brief - 2026-10-28

**Model Confidence: 9.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-10-28T15:37:13 UTC. Game lines source: **DraftKings**. Pick-em opportunities from PrizePicks._

## Play of the Day

**MIL @ TBR - MIL_ML**
- Market: -157
- Model probability: 70.9%
- Raw edge: +16.03%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:00p ET | MIL @ TBR | Tropicana Field | indoor | MIL_ML +16.03% |

## Parlays - top 5

- **3-leg @ +471 (prob 26.1%, EV +48.74%)**
  - Victor Mesa Jr. OVER 0.5 batter_hits (-121, model 60.3%)
  - MIL @ TBR OVER_6.5 (-110, model 61.0%)
  - MIL @ TBR MIL_ML (-157, model 70.9%)
- **3-leg @ +578 (prob 21.9%, EV +48.38%)**
  - Taylor Walls OVER 0.5 batter_hits (+117, model 50.6%)
  - MIL @ TBR OVER_6.5 (-110, model 61.0%)
  - MIL @ TBR MIL_ML (-157, model 70.9%)
- **3-leg @ +459 (prob 26.3%, EV +46.94%)**
  - Garrett Mitchell OVER 0.5 batter_hits (-127, model 60.9%)
  - MIL @ TBR OVER_6.5 (-110, model 61.0%)
  - MIL @ TBR MIL_ML (-157, model 70.9%)
- **3-leg @ +601 (prob 21.0%, EV +46.9%)**
  - Richie Palacios OVER 0.5 batter_hits (+101, model 57.0%)
  - Victor Mesa Jr. OVER 0.5 batter_hits (-121, model 60.3%)
  - MIL @ TBR OVER_6.5 (-110, model 61.0%)
- **3-leg @ +733 (prob 17.6%, EV +46.54%)**
  - Richie Palacios OVER 0.5 batter_hits (+101, model 57.0%)
  - Taylor Walls OVER 0.5 batter_hits (+117, model 50.6%)
  - MIL @ TBR OVER_6.5 (-110, model 61.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 87 | 36.8% | 41.1% | 1.116 | 0.903 |
| batter hits | 349 | 55.6% | 56.7% | 1.020 | 0.981 |

Cumulative graded plays: 19852. Wins: 8812. Hit rate: 44.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| MIL @ TBR | 60.8% | -155 | 2.49 | +457 | -457 |

## Team Form (last 10)

**Hot:** MIL 7-1 (L1, +20), CLE 4-4 (L3, -1), TB 5-5 (W1, -3), CWS 0-2 (L2, -6), LAD 0-4 (L4, -10)

**Cold:** LAD 0-4 (L4, -10), CWS 0-2 (L2, -6), TB 5-5 (W1, -3), CLE 4-4 (L3, -1), MIL 7-1 (L1, 20)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 11.4 IP across 2 games
- MIL: 9.6 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-0.5**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-10-27._