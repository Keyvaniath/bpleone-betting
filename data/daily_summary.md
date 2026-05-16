# EdgeStat Daily Brief - 2026-05-16

**Model Confidence: 73.6/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-05-16T22:54:46 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**BOS @ ATL - ATL_ML**
- Market: -121
- Model probability: 78.9%
- Raw edge: +44.16%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | TEX @ HOU | Daikin Park | indoor | HOU_ML +17.81% |
| 7:10p ET | CHC @ CHW | Rate Field | 71F 7mph | CHW_ML +32.23% |
| 7:10p ET | MIL @ MIN | Target Field | 65F 9mph | UNDER_8.5 +34.99% |
| 7:15p ET | SDP @ SEA | T-Mobile Park | indoor | UNDER_7.0 +27.31% |
| 7:15p ET | BOS @ ATL | Truist Park | 71F 4mph | ATL_ML +44.16% |
| 7:15p ET | NYY @ NYM | Citi Field | 66F 10mph | NYY_ML +41.54% |
| 9:38p ET | LAD @ LAA | Angel Stadium | 60F 6mph | LAD_ML +31.09% |
| 9:40p ET | SFG @ OAK | Sutter Health Park | 66F 10mph | OAK_ML +23.65% |

## Parlays - top 5

- **2-leg @ +212 (prob 47.9%, EV +49.57%)**
  - MIL @ MIN MIL_ML (-125, model 67.0%)
  - SFG @ OAK OAK_ML (-136, model 71.5%)
- **2-leg @ +231 (prob 44.4%, EV +47.03%)**
  - MIA @ TBR UNDER_7.5 (-110, model 62.1%)
  - SFG @ OAK OAK_ML (-136, model 71.5%)
- **2-leg @ +231 (prob 44.1%, EV +46.13%)**
  - CHC @ CHW OVER_8.5 (-110, model 61.7%)
  - SFG @ OAK OAK_ML (-136, model 71.5%)
- **2-leg @ +231 (prob 44.1%, EV +46.01%)**
  - BOS @ ATL UNDER_8.0 (-110, model 61.7%)
  - SFG @ OAK OAK_ML (-136, model 71.5%)
- **2-leg @ +244 (prob 41.6%, EV +42.98%)**
  - MIA @ TBR UNDER_7.5 (-110, model 62.1%)
  - MIL @ MIN MIL_ML (-125, model 67.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 12730 | 26.3% | 31.7% | 1.204 | 0.830 |
| batter runs scored | 6364 | 37.0% | 38.7% | 1.045 | 0.957 |
| batter hits | 12730 | 39.8% | 41.6% | 1.046 | 0.956 |
| batter doubles | 6364 | 14.8% | 15.9% | 1.070 | 0.934 |
| pitcher strikeouts | 2764 | 32.5% | 38.1% | 1.175 | 0.852 |
| batter rbis | 12728 | 19.8% | 23.1% | 1.168 | 0.856 |
| batter home runs | 6364 | 10.9% | 12.8% | 1.166 | 0.858 |
| batter singles | 6364 | 43.8% | 44.5% | 1.015 | 0.985 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ ATL | 65.0% | -186 | 2.16 | -201 | +201 |
| CHC @ CHW | 58.5% | -141 | 2.81 | -137 | +137 |
| LAD @ LAA | 48.5% | +106 | 3.66 | +560 | -560 |
| MIL @ MIN | 47.2% | +112 | 3.62 | +379 | -379 |
| NYY @ NYM | 31.2% | +221 | 6.18 | +687 | -687 |
| SDP @ SEA | 44.1% | +127 | 4.09 | +102 | -102 |
| SFG @ OAK | 50.5% | -102 | 3.41 | -143 | +143 |
| TEX @ HOU | 37.4% | +168 | 4.92 | +162 | -162 |

## Team Form (last 10)

**Hot:** TB 8-2 (W1, +20), MIL 7-3 (W2, +15), AZ 5-5 (W1, +14), PHI 7-3 (W2, +13), SEA 5-5 (L1, +11)

**Cold:** DET 2-8 (W1, -27), LAA 3-7 (L4, -23), COL 3-7 (L2, -22), HOU 4-6 (W1, -18), SF 4-6 (L3, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 11.1 IP across 2 games
- SD: 8.4 IP across 2 games
- PHI: 9.1 IP across 2 games
- MIA: 8.3 IP across 2 games
- MIL: 8.0 IP across 2 games
- CHC: 9.1 IP across 2 games
- COL: 11.4 IP across 2 games
- DET: 9.7 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↓ 8 -> **5**
  - _1 market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 5.0 -> **3.5**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-15._