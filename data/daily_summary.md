# EdgeStat Daily Brief - 2026-09-10

**Model Confidence: 27.3/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-10T00:06:03 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ NYY - NYY_ML**
- Market: -110
- Model probability: 82.6%
- Raw edge: +57.74%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (5 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:15p ET | TBR @ ATL | Truist Park | 92F 5mph | OVER_8.5 +32.07% |
| 1:05p ET | HOU @ PHI | Citizens Bank Park | 88F 10mph | OVER_8.5 +53.14% |
| 4:10p ET | TEX @ SEA | T-Mobile Park | indoor | UNDER_8.5 +35.7% |
| 7:05p ET | COL @ NYY | Yankee Stadium | 77F 5mph | NYY_ML +57.74% |
| 7:40p ET | PIT @ CHW | Rate Field | 70F 0mph | OVER_8.5 +20.25% |

## Parlays - top 5

- **2-leg @ +348 (prob 33.4%, EV +49.59%)**
  - Jordan Walker OVER 1.5 batter_total_bases (+126, model 54.9%)
  - CLE @ BAL BAL_ML (-102, model 60.9%)
- **2-leg @ +278 (prob 39.5%, EV +49.49%)**
  - WSN @ SDP OVER_8.5 (-110, model 63.6%)
  - ARI @ KCR KCR_ML (-102, model 62.2%)
- **2-leg @ +188 (prob 51.8%, EV +49.31%)**
  - CLE @ BAL BAL_ML (-102, model 60.9%)
  - LAA @ BOS BOS_ML (-220, model 85.1%)
- **2-leg @ +292 (prob 37.8%, EV +48.39%)**
  - CLE @ BAL BAL_ML (-102, model 60.9%)
  - ARI @ KCR KCR_ML (-102, model 62.2%)
- **2-leg @ +418 (prob 28.6%, EV +48.0%)**
  - Jordan Walker OVER 1.5 batter_total_bases (+126, model 54.9%)
  - Dillon Dingler OVER 1.5 batter_total_bases (+129, model 52.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 174 | 54.0% | 56.2% | 1.040 | 0.963 |
| batter total bases | 79 | 46.8% | 46.9% | 1.001 | 0.999 |

Cumulative graded plays: 10279. Wins: 3679. Hit rate: 35.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| CIN @ LAD | 36.2% | +176 | 5.08 | -- | -- |
| COL @ NYY | -- | -- | -- | -283 | +283 |
| HOU @ PHI | -- | -- | -- | +103 | -103 |
| PIT @ CHW | -- | -- | -- | +197 | -197 |
| TBR @ ATL | -- | -- | -- | +202 | -202 |
| TEX @ SEA | -- | -- | -- | +320 | -320 |

## Team Form (last 10)

**Hot:** TOR 7-3 (W1, +21), NYY 6-4 (W1, +18), TEX 6-4 (W2, +13), NYM 7-3 (W3, +13), MIN 5-5 (W1, +11)

**Cold:** DET 3-7 (L1, -20), BOS 6-4 (L1, -15), KC 3-7 (L2, -13), WSH 3-7 (L6, -12), SEA 3-7 (L1, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- MIA: 9.2 IP across 2 games
- AZ: 14.6 IP across 2 games
- CLE: 9.4 IP across 2 games
- KC: 8.3 IP across 2 games
- NYM: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-08._