# EdgeStat Daily Brief - 2026-09-05

**Model Confidence: 27.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-05T23:42:34 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**STL @ COL - OVER_11.5**
- Market: -110
- Model probability: 75.1%
- Raw edge: +43.34%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:10p ET | STL @ COL | Coors Field | 75F 6mph | OVER_11.5 +43.34% |
| 9:10p ET | WSN @ LAD | UNIQLO Field at Dodger Stadium | 71F 2mph | WSN_ML +8.22% |
| 9:40p ET | OAK @ SEA | T-Mobile Park | indoor | OVER_7.5 +39.78% |

## Parlays - top 5

- **2-leg @ +398 (prob 30.0%, EV +49.72%)**
  - Michael Busch UNDER 0.5 batter_hits (+161, model 46.1%)
  - MIL @ CIN OVER_9.0 (-110, model 65.2%)
- **2-leg @ +347 (prob 33.5%, EV +49.61%)**
  - ATL @ PHI ATL_ML (+134, model 51.3%)
  - MIL @ CIN OVER_9.0 (-110, model 65.2%)
- **2-leg @ +421 (prob 28.7%, EV +49.55%)**
  - Juan Soto OVER 1.5 batter_total_bases (+116, model 56.6%)
  - SFG @ NYM SFG_ML (+141, model 50.7%)
- **2-leg @ +575 (prob 21.8%, EV +47.34%)**
  - Francisco Lindor UNDER 0.5 batter_hits (+180, model 43.0%)
  - SFG @ NYM SFG_ML (+141, model 50.7%)
- **2-leg @ +464 (prob 26.1%, EV +47.08%)**
  - Juan Soto OVER 1.5 batter_total_bases (+116, model 56.6%)
  - Michael Busch UNDER 0.5 batter_hits (+161, model 46.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 46 | 43.5% | 45.2% | 1.038 | 0.968 |
| batter hits | 115 | 53.9% | 56.3% | 1.043 | 0.961 |

Cumulative graded plays: 9929. Wins: 3559. Hit rate: 35.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| OAK @ SEA | 24.9% | +302 | 6.96 | -108 | +108 |
| STL @ COL | 25.9% | +286 | 6.89 | +165 | -165 |
| WSN @ LAD | 59.2% | -145 | 2.64 | +105 | -105 |

## Team Form (last 10)

**Hot:** TOR 7-3 (W3, +21), NYY 6-4 (L1, +16), CHC 4-6 (W2, +16), MIL 7-3 (W1, +14), MIN 4-6 (L2, +13)

**Cold:** BOS 4-6 (W2, -26), DET 3-7 (L2, -25), CIN 5-5 (L1, -17), SEA 3-7 (L2, -15), LAA 1-9 (L3, -11)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.4 IP across 2 games
- PIT: 9.2 IP across 2 games
- SEA: 8.1 IP across 2 games
- SF: 8.0 IP across 2 games
- TEX: 9.3 IP across 2 games
- TOR: 11.1 IP across 2 games
- CWS: 8.0 IP across 2 games
- CLE: 14.5 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-05._