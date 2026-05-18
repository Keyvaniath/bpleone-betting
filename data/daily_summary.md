# EdgeStat Daily Brief - 2026-05-18

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-05-18T23:44:53 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ SDP - LAD_ML**
- Market: -143
- Model probability: 78.4%
- Raw edge: +33.21%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:40p ET | TEX @ COL | Coors Field | 39F 9mph | -- |
| 9:38p ET | OAK @ LAA | Angel Stadium | 61F 4mph | OAK_ML +11.83% |
| 9:40p ET | LAD @ SDP | Petco Park | 62F 8mph | LAD_ML +33.21% |
| 9:40p ET | SFG @ ARI | Chase Field | indoor | UNDER_9.0 +17.17% |
| 9:40p ET | CHW @ SEA | T-Mobile Park | indoor | OVER_7.0 +15.89% |

## Parlays - top 5

- **3-leg @ +673 (prob 19.3%, EV +49.31%)**
  - OAK @ LAA OAK_ML (-134, model 64.2%)
  - SFG @ ARI UNDER_9.0 (-110, model 61.4%)
  - CHW @ SEA CHW_ML (+132, model 49.0%)
- **3-leg @ +673 (prob 19.1%, EV +47.66%)**
  - OAK @ LAA OAK_ML (-134, model 64.2%)
  - CHW @ SEA OVER_7.0 (-110, model 60.7%)
  - CHW @ SEA CHW_ML (+132, model 49.0%)
- **3-leg @ +648 (prob 19.7%, EV +47.27%)**
  - HOU @ MIN MIN_ML (-118, model 62.6%)
  - OAK @ LAA OAK_ML (-134, model 64.2%)
  - CHW @ SEA CHW_ML (+132, model 49.0%)
- **3-leg @ +525 (prob 22.8%, EV +42.39%)**
  - SFG @ ARI UNDER_9.0 (-110, model 61.4%)
  - SFG @ ARI ARI_ML (-140, model 61.2%)
  - CHW @ SEA OVER_7.0 (-110, model 60.7%)
- **3-leg @ +505 (prob 23.5%, EV +42.02%)**
  - HOU @ MIN MIN_ML (-118, model 62.6%)
  - SFG @ ARI UNDER_9.0 (-110, model 61.4%)
  - SFG @ ARI ARI_ML (-140, model 61.2%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter runs scored | 5937 | 36.9% | 38.7% | 1.048 | 0.954 |
| batter home runs | 5937 | 11.0% | 12.8% | 1.161 | 0.861 |
| batter hits | 11876 | 39.7% | 41.6% | 1.048 | 0.954 |
| pitcher strikeouts | 2588 | 32.6% | 38.1% | 1.167 | 0.857 |
| batter rbis | 11874 | 19.8% | 23.2% | 1.171 | 0.854 |
| batter singles | 5937 | 43.8% | 44.5% | 1.016 | 0.984 |
| batter doubles | 5937 | 14.7% | 15.9% | 1.078 | 0.927 |
| batter total bases | 11876 | 26.2% | 31.7% | 1.211 | 0.826 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CHW @ SEA | 36.0% | +178 | 5.11 | +169 | -169 |
| HOU @ MIN | 34.2% | +193 | 5.37 | -- | -- |
| LAD @ SDP | 45.2% | +121 | 4.16 | +694 | -694 |
| MIL @ CHC | 46.5% | +115 | 3.83 | -- | -- |
| OAK @ LAA | 53.1% | -113 | 3.23 | +312 | -312 |
| SFG @ ARI | 28.1% | +255 | 6.34 | +111 | -111 |
| TEX @ COL | 33.8% | +196 | 5.11 | +231 | -231 |

## Travel / Rest Flags

- **CHW @ SEA** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** CLE 7-3 (W2, +20), MIL 8-2 (L1, +19), ATL 6-4 (W1, +17), LAD 6-4 (W5, +17), PHI 7-3 (W4, +14)

**Cold:** LAA 2-8 (L6, -40), DET 2-8 (L2, -23), COL 4-6 (L1, -15), HOU 4-6 (L1, -14), CIN 4-6 (L2, -10)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.3 IP across 2 games
- SD: 8.0 IP across 2 games
- TOR: 10.5 IP across 2 games
- CWS: 10.0 IP across 2 games
- WSH: 9.4 IP across 2 games
- NYM: 12.2 IP across 2 games

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
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-17._