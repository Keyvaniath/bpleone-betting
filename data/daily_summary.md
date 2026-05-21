# EdgeStat Daily Brief - 2026-05-21

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-21T08:02:21 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYM @ WSN - UNDER_8.5**
- Market: -110
- Model probability: 72.9%
- Raw edge: +39.1%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:10p ET | CLE @ DET | Comerica Park | 64F 11mph | DET_ML +9.59% |
| 1:15p ET | PIT @ STL | Busch Stadium | 70F 7mph | OVER_7.5 +11.9% |
| 4:05p ET | NYM @ WSN | Nationals Park | 60F 6mph | UNDER_8.5 +39.1% |
| 6:40p ET | ATL @ MIA | loanDepot park | indoor | ATL_ML +27.17% |
| 7:05p ET | TOR @ NYY | Yankee Stadium | 56F 3mph | NYY_ML +21.47% |
| 9:38p ET | OAK @ LAA | Angel Stadium | 60F 5mph | OVER_8.0 +13.31% |
| 9:40p ET | COL @ ARI | Chase Field | indoor | -- |

## Parlays - top 5

- **3-leg @ +489 (prob 25.4%, EV +49.92%)**
  - TOR @ NYY NYY_ML (-168, model 76.1%)
  - OAK @ LAA OVER_8.0 (-110, model 59.4%)
  - OAK @ LAA OAK_ML (-107, model 56.3%)
- **3-leg @ +465 (prob 26.4%, EV +48.97%)**
  - CLE @ DET DET_ML (-117, model 59.1%)
  - PIT @ STL OVER_7.5 (-110, model 58.6%)
  - TOR @ NYY NYY_ML (-168, model 76.1%)
- **3-leg @ +442 (prob 27.4%, EV +48.8%)**
  - PIT @ STL PIT_ML (-128, model 60.7%)
  - TOR @ NYY NYY_ML (-168, model 76.1%)
  - OAK @ LAA OVER_8.0 (-110, model 59.4%)
- **3-leg @ +489 (prob 25.1%, EV +48.08%)**
  - PIT @ STL OVER_7.5 (-110, model 58.6%)
  - TOR @ NYY NYY_ML (-168, model 76.1%)
  - OAK @ LAA OAK_ML (-107, model 56.3%)
- **3-leg @ +442 (prob 27.1%, EV +46.97%)**
  - PIT @ STL OVER_7.5 (-110, model 58.6%)
  - PIT @ STL PIT_ML (-128, model 60.7%)
  - TOR @ NYY NYY_ML (-168, model 76.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter home runs | 5253 | 11.1% | 12.8% | 1.161 | 0.862 |
| batter rbis | 10506 | 19.6% | 23.2% | 1.181 | 0.847 |
| pitcher strikeouts | 2280 | 32.7% | 38.2% | 1.169 | 0.856 |
| batter runs scored | 5253 | 36.4% | 38.7% | 1.063 | 0.941 |
| batter total bases | 10508 | 26.0% | 31.8% | 1.221 | 0.819 |
| batter doubles | 5253 | 14.3% | 15.9% | 1.109 | 0.902 |
| batter singles | 5253 | 43.6% | 44.5% | 1.020 | 0.980 |
| batter hits | 10508 | 39.5% | 41.6% | 1.054 | 0.949 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ATL @ MIA | 48.5% | +106 | 3.62 | +520 | -520 |
| CLE @ DET | 62.8% | -169 | 2.31 | +125 | -125 |
| COL @ ARI | 41.7% | +140 | 4.38 | -104 | +104 |
| NYM @ WSN | 40.3% | +148 | 4.38 | -112 | +112 |
| OAK @ LAA | 35.2% | +184 | 5.38 | +222 | -222 |
| PIT @ STL | 47.2% | +112 | 3.58 | +273 | -273 |
| TOR @ NYY | 34.5% | +190 | 5.32 | -179 | +179 |

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