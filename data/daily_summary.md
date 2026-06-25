# EdgeStat Daily Brief - 2026-06-25

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-25T23:22:33 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

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

- **2-leg @ +264 (prob 41.0%, EV +49.55%)**
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
- **3-leg @ +727 (prob 18.1%, EV +49.35%)**
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - TEX @ TOR TEX_ML (+127, model 49.8%)
  - CHC @ NYM UNDER_8.5 (-110, model 57.1%)
- **3-leg @ +716 (prob 18.3%, EV +49.07%)**
  - SEA @ PIT PIT_ML (+124, model 49.5%)
  - CHC @ NYM UNDER_8.5 (-110, model 57.1%)
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
- **3-leg @ +529 (prob 23.7%, EV +49.05%)**
  - NYY @ BOS OVER_8.0 (-110, model 64.6%)
  - ARI @ STL STL_ML (-138, model 63.9%)
  - ARI @ STL OVER_9.0 (-110, model 57.5%)
- **3-leg @ +638 (prob 20.1%, EV +48.12%)**
  - SEA @ PIT PIT_ML (+124, model 49.5%)
  - HOU @ DET OVER_9.0 (-110, model 63.5%)
  - ARI @ STL STL_ML (-138, model 63.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ NYY | -- | -- | -- | +115 | -115 |
| CIN @ COL | -- | -- | -- | +465 | -465 |
| SDP @ LAD | -- | -- | -- | -166 | +166 |

## Travel / Rest Flags

- **NYY @ BOS** (home): travel + back-to-back (+2h tz shift)

## Team Form (last 10)

**Hot:** CHC 7-3 (W3, +28), PHI 6-4 (W2, +18), MIL 7-3 (W4, +15), KC 6-4 (L1, +15), MIN 6-4 (L3, +14)

**Cold:** NYM 3-7 (L5, -28), ATL 2-8 (L4, -27), SEA 4-6 (L1, -26), ATH 3-7 (L4, -20), TEX 4-6 (L2, -18)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 11.4 IP across 2 games
- TOR: 9.5 IP across 2 games
- MIN: 10.0 IP across 2 games
- CWS: 10.4 IP across 2 games
- LAA: 8.6 IP across 2 games
- CHC: 11.2 IP across 3 games
- HOU: 9.1 IP across 2 games
- WSH: 11.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-24._