# EdgeStat Daily Brief - 2026-05-20

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-05-20T23:15:35 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ SDP - UNDER_7.5**
- Market: -110
- Model probability: 68.8%
- Raw edge: +31.3%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | BOS @ KCR | Kauffman Stadium | 57F 5mph | UNDER_7.5 +6.45% |
| 7:40p ET | MIL @ CHC | Wrigley Field | 49F 9mph | OVER_6.5 +28.09% |
| 7:45p ET | PIT @ STL | Busch Stadium | 61F 3mph | PIT_ML +18.46% |
| 8:40p ET | LAD @ SDP | Petco Park | 65F 3mph | UNDER_7.5 +31.3% |
| 9:38p ET | OAK @ LAA | Angel Stadium | 68F 5mph | OAK_ML +24.43% |

## Parlays - top 5

- **2-leg @ +264 (prob 41.0%, EV +49.35%)**
  - ATL @ MIA OVER_7.0 (-110, model 64.2%)
  - TOR @ NYY UNDER_8.0 (-110, model 63.9%)
- **2-leg @ +187 (prob 51.9%, EV +48.77%)**
  - BAL @ TBR TBR_ML (-122, model 66.0%)
  - TOR @ NYY NYY_ML (-174, model 78.7%)
- **2-leg @ +247 (prob 42.3%, EV +47.06%)**
  - BAL @ TBR TBR_ML (-122, model 66.0%)
  - ATL @ MIA OVER_7.0 (-110, model 64.2%)
- **2-leg @ +212 (prob 47.1%, EV +46.84%)**
  - TOR @ NYY NYY_ML (-174, model 78.7%)
  - PIT @ STL PIT_ML (-102, model 59.8%)
- **2-leg @ +247 (prob 42.1%, EV +46.35%)**
  - BAL @ TBR TBR_ML (-122, model 66.0%)
  - TOR @ NYY UNDER_8.0 (-110, model 63.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter rbis | 10856 | 19.8% | 23.2% | 1.173 | 0.853 |
| batter total bases | 10858 | 26.1% | 31.8% | 1.218 | 0.821 |
| batter home runs | 5428 | 11.0% | 12.8% | 1.163 | 0.860 |
| batter singles | 5428 | 43.8% | 44.5% | 1.016 | 0.984 |
| batter hits | 10858 | 39.6% | 41.6% | 1.050 | 0.952 |
| batter doubles | 5428 | 14.5% | 15.9% | 1.100 | 0.909 |
| pitcher strikeouts | 2356 | 32.5% | 38.2% | 1.174 | 0.853 |
| batter runs scored | 5428 | 36.6% | 38.7% | 1.057 | 0.947 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ KCR | 51.3% | -105 | 3.3 | +147 | -147 |
| LAD @ SDP | 69.9% | -232 | 1.82 | +1042 | -1042 |
| MIL @ CHC | 43.7% | +129 | 3.89 | +245 | -245 |
| OAK @ LAA | 38.4% | +160 | 4.88 | +412 | -412 |
| PIT @ STL | 52.6% | -111 | 3.17 | +267 | -267 |

## Team Form (last 10)

**Hot:** PHI 8-2 (L1, +25), TEX 6-4 (W1, +24), AZ 7-3 (W3, +22), CLE 7-3 (W4, +22), LAD 6-4 (W1, +20)

**Cold:** LAA 2-8 (L1, -51), COL 3-7 (L1, -30), DET 2-8 (L4, -25), HOU 4-6 (W1, -24), CHC 2-8 (L4, -23)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TEX: 13.6 IP across 2 games
- CHC: 8.2 IP across 2 games
- COL: 11.2 IP across 2 games
- KC: 10.0 IP across 2 games
- WSH: 11.3 IP across 2 games
- NYM: 9.4 IP across 2 games

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
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-19._