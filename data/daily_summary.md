# EdgeStat Daily Brief - 2026-07-23

**Model Confidence: 22.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-23T23:00:57 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CIN @ COL - CIN_ML**
- Market: -110
- Model probability: 73.7%
- Raw edge: +40.74%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | SDP @ LAD | Petco Park | 62F -6mph | LAD_ML +25.43% |
| 6:45p ET | BOS @ NYY | Yankee Stadium | 71F 12mph | OVER_9.0 +30.97% |
| 9:40p ET | CIN @ COL | Coors Field | 74F 4mph | CIN_ML +40.74% |

## Parlays - top 5

- **2-leg @ +331 (prob 34.7%, EV +49.63%)**
  - SDP @ ATL OVER_8.0 (-110, model 64.4%)
  - MIN @ CLE MIN_ML (+126, model 53.9%)
- **3-leg @ +282 (prob 37.6%, EV +43.66%)**
  - SDP @ ATL ATL_ML (-260, model 79.0%)
  - ARI @ STL OVER_7.5 (-110, model 65.4%)
  - KCR @ DET DET_ML (-225, model 72.8%)
- **3-leg @ +282 (prob 37.0%, EV +41.36%)**
  - SDP @ ATL OVER_8.0 (-110, model 64.4%)
  - SDP @ ATL ATL_ML (-260, model 79.0%)
  - KCR @ DET DET_ML (-225, model 72.8%)
- **3-leg @ +352 (prob 31.0%, EV +40.02%)**
  - SDP @ ATL ATL_ML (-260, model 79.0%)
  - MIN @ CLE MIN_ML (+126, model 53.9%)
  - KCR @ DET DET_ML (-225, model 72.8%)
- **2-leg @ +164 (prob 51.7%, EV +36.58%)**
  - SDP @ ATL ATL_ML (-260, model 79.0%)
  - ARI @ STL OVER_7.5 (-110, model 65.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6523. Wins: 2680. Hit rate: 41.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | -- | -- | -- | +115 | -115 |
| CIN @ COL | -- | -- | -- | +465 | -465 |
| SDP @ LAD | -- | -- | -- | -166 | +166 |

## Travel / Rest Flags

- **ARI @ STL** (home): travel + back-to-back (+2h tz shift)

## Team Form (last 10)

**Hot:** CWS 7-3 (W1, +30), AZ 8-2 (W2, +27), BOS 9-1 (W1, +27), BAL 8-2 (L1, +20), WSH 5-5 (W1, +19)

**Cold:** ATH 2-8 (L2, -41), KC 5-5 (W3, -25), COL 3-7 (L1, -21), MIN 4-6 (W1, -18), TOR 3-7 (L4, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TEX: 10.0 IP across 2 games
- TOR: 11.0 IP across 2 games
- MIN: 10.2 IP across 2 games
- ATL: 8.5 IP across 2 games
- MIL: 8.1 IP across 2 games
- AZ: 9.0 IP across 2 games
- BOS: 11.2 IP across 2 games
- COL: 8.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-23._