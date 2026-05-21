# EdgeStat Daily Brief - 2026-05-21

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-21T23:14:11 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**OAK @ LAA - OAK_ML**
- Market: +100
- Model probability: 56.3%
- Raw edge: +12.55%
- Recommended stake: 3.14u Kelly

## Full Slate (2 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 9:38p ET | OAK @ LAA | Angel Stadium | 61F 3mph | OAK_ML +12.55% |
| 9:40p ET | COL @ ARI | Chase Field | indoor | OVER_8.5 +7.11% |

## Parlays - top 5

- **3-leg @ +437 (prob 27.6%, EV +48.38%)**
  - PIT @ STL PIT_ML (-133, model 60.7%)
  - TOR @ NYY NYY_ML (-165, model 76.2%)
  - OAK @ LAA OVER_8.0 (-110, model 59.8%)
- **3-leg @ +485 (prob 25.3%, EV +48.29%)**
  - PIT @ STL OVER_7.5 (-110, model 58.3%)
  - TOR @ NYY NYY_ML (-165, model 76.2%)
  - COL @ ARI UNDER_9.5 (-110, model 57.1%)
- **3-leg @ +462 (prob 26.2%, EV +47.5%)**
  - CLE @ DET DET_ML (-120, model 59.1%)
  - PIT @ STL OVER_7.5 (-110, model 58.3%)
  - TOR @ NYY NYY_ML (-165, model 76.2%)
- **3-leg @ +488 (prob 25.0%, EV +47.0%)**
  - PIT @ STL OVER_7.5 (-110, model 58.3%)
  - TOR @ NYY NYY_ML (-165, model 76.2%)
  - OAK @ LAA OAK_ML (-109, model 56.3%)
- **3-leg @ +485 (prob 25.0%, EV +46.27%)**
  - ATL @ MIA OVER_7.5 (-110, model 54.9%)
  - TOR @ NYY NYY_ML (-165, model 76.2%)
  - OAK @ LAA OVER_8.0 (-110, model 59.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 10508 | 39.5% | 41.6% | 1.054 | 0.949 |
| batter total bases | 10508 | 26.0% | 31.8% | 1.221 | 0.819 |
| batter home runs | 5253 | 11.1% | 12.8% | 1.161 | 0.862 |
| batter singles | 5253 | 43.6% | 44.5% | 1.020 | 0.980 |
| batter runs scored | 5253 | 36.4% | 38.7% | 1.063 | 0.941 |
| pitcher strikeouts | 2280 | 32.7% | 38.2% | 1.169 | 0.856 |
| batter doubles | 5253 | 14.3% | 15.9% | 1.109 | 0.902 |
| batter rbis | 10506 | 19.6% | 23.2% | 1.181 | 0.847 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ ARI | 41.7% | +140 | 4.38 | -104 | +104 |
| OAK @ LAA | 35.2% | +184 | 5.32 | +223 | -223 |
| TOR @ NYY | 34.5% | +190 | 5.32 | -- | -- |

## Team Form (last 10)

**Hot:** LAD 7-3 (W2, +29), AZ 7-3 (W4, +24), CLE 8-2 (W5, +24), TB 8-2 (W4, +23), MIL 8-2 (W3, +22)

**Cold:** LAA 2-8 (L2, -39), COL 3-7 (L2, -25), HOU 4-6 (L1, -22), DET 2-8 (L5, -22), CHC 2-8 (L5, -22)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 10.1 IP across 2 games
- TB: 8.3 IP across 2 games
- TEX: 11.3 IP across 2 games
- MIA: 8.6 IP across 2 games
- COL: 11.5 IP across 2 games
- DET: 9.1 IP across 2 games
- KC: 9.3 IP across 2 games
- WSH: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↓ 5 -> **3**
  - _1 market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-20._