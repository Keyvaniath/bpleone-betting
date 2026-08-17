# EdgeStat Daily Brief - 2026-08-17

**Model Confidence: 27.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-17T13:45:24 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ COL - LAD_ML**
- Market: +100
- Model probability: 94.8%
- Raw edge: +89.7%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (11 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 1:40p ET | STL @ CIN | Great American Ball Park | 85F 5mph | OVER_8.5 +37.85% |
| 6:40p ET | STL @ CIN | Great American Ball Park | 85F 5mph | OVER_8.5 +34.79% |
| 6:05p ET | BAL @ TBR | Tropicana Field | indoor | TBR_ML +23.55% |
| 6:40p ET | MIA @ PHI | Citizens Bank Park | 78F 3mph | PHI_ML +14.12% |
| 7:05p ET | DET @ PIT | PNC Park | 72F 2mph | OVER_8.5 +2.69% |
| 7:10p ET | ARI @ BOS | Fenway Park | 68F 3mph | OVER_8.5 +28.48% |
| 7:10p ET | SDP @ NYM | Citi Field | 74F 5mph | UNDER_8.5 +18.86% |
| 7:40p ET | OAK @ KCR | Kauffman Stadium | 79F 6mph | OVER_8.5 +61.67% |
| 7:40p ET | ATL @ MIN | Target Field | 73F 5mph | OVER_8.5 +37.93% |
| 8:05p ET | CHW @ CHC | Wrigley Field | 66F 5mph | OVER_8.5 +42.54% |
| 8:40p ET | LAD @ COL | Coors Field | 77F 3mph | LAD_ML +89.7% |

## Parlays - top 5

- **2-leg @ +282 (prob 38.7%, EV +47.72%)**
  - STL @ CIN STL_ML (+100, model 62.1%)
  - SDP @ NYM UNDER_8.5 (-110, model 62.3%)
- **2-leg @ +264 (prob 40.3%, EV +46.86%)**
  - BAL @ TBR TBR_ML (-110, model 64.7%)
  - SDP @ NYM UNDER_8.5 (-110, model 62.3%)
- **2-leg @ +480 (prob 24.8%, EV +43.98%)**
  - Corbin Carroll UNDER 0.5 batter_hits (+190, model 40.0%)
  - STL @ CIN STL_ML (+100, model 62.1%)
- **2-leg @ +454 (prob 25.9%, EV +43.15%)**
  - Corbin Carroll UNDER 0.5 batter_hits (+190, model 40.0%)
  - BAL @ TBR TBR_ML (-110, model 64.7%)
- **2-leg @ +282 (prob 37.1%, EV +41.84%)**
  - STL @ CIN STL_ML (+100, model 62.1%)
  - MIA @ PHI PHI_ML (-110, model 59.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 34 | 58.8% | 58.3% | 0.991 | 1.008 |
| batter total bases | 11 | 45.5% | 52.1% | 1.132 | 0.924 |

Cumulative graded plays: 8746. Wins: 3288. Hit rate: 37.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ BOS | 46.9% | +113 | 3.72 | -115 | +115 |
| ATL @ MIN | 51.1% | -105 | 3.43 | +281 | -281 |
| BAL @ TBR | 42.4% | +136 | 4.29 | -104 | +104 |
| CHW @ CHC | 35.6% | +181 | 5.31 | +130 | -130 |
| DET @ PIT | 43.4% | +130 | 4.22 | +155 | -155 |
| LAD @ COL | 31.5% | +217 | 5.66 | +3503 | -3503 |
| MIA @ PHI | 58.4% | -140 | 2.72 | +114 | -114 |
| OAK @ KCR | 31.0% | +223 | 5.71 | -151 | +151 |
| SDP @ NYM | 44.1% | +127 | 3.96 | +143 | -143 |
| STL @ CIN | 36.7% | +173 | 5.11 | +202 | -202 |

## Travel / Rest Flags

- **OAK @ KCR** (home): travel + back-to-back (+2h tz shift)
- **OAK @ KCR** (away): travel + back-to-back (+2h tz shift)

## Team Form (last 10)

**Hot:** SD 8-2 (W1, +20), STL 7-3 (W2, +19), TB 7-3 (L3, +15), DET 5-5 (L3, +14), MIA 6-4 (W2, +12)

**Cold:** CIN 4-6 (L2, -25), SEA 3-7 (W2, -20), ATH 4-6 (W1, -18), SF 3-7 (L1, -17), TEX 4-6 (L1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 10.0 IP across 2 games
- SD: 10.0 IP across 2 games
- TOR: 10.5 IP across 2 games
- ATL: 8.1 IP across 2 games
- COL: 9.1 IP across 2 games
- DET: 8.2 IP across 2 games
- HOU: 9.0 IP across 2 games
- WSH: 9.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-0.1**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-17._