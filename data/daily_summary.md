# EdgeStat Daily Brief - 2026-09-10

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-10T17:47:36 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ NYY - OVER_8.5**
- Market: -110
- Model probability: 78.6%
- Raw edge: +50.03%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 4:10p ET | TEX @ SEA | T-Mobile Park | indoor | TEX_ML +28.44% |
| 7:05p ET | COL @ NYY | Yankee Stadium | 78F 5mph | OVER_8.5 +50.03% |
| 7:40p ET | PIT @ CHW | Rate Field | 67F 6mph | OVER_7.5 +34.21% |

## Parlays - top 5

- **2-leg @ +401 (prob 29.8%, EV +48.94%)**
  - Yordan Alvarez OVER 1.5 batter_total_bases (-103, model 63.1%)
  - Jonathan Aranda OVER 1.5 batter_total_bases (+154, model 47.1%)
- **2-leg @ +312 (prob 35.8%, EV +47.61%)**
  - Yordan Alvarez OVER 1.5 batter_total_bases (-103, model 63.1%)
  - Michael Harris II OVER 1.5 batter_total_bases (+109, model 56.8%)
- **2-leg @ +470 (prob 25.6%, EV +45.78%)**
  - Yordan Alvarez OVER 1.5 batter_total_bases (-103, model 63.1%)
  - Ronald Acuna Jr. UNDER 0.5 batter_hits (+189, model 40.6%)
- **2-leg @ +304 (prob 35.2%, EV +42.1%)**
  - Yordan Alvarez OVER 1.5 batter_total_bases (-103, model 63.1%)
  - Junior Caminero OVER 1.5 batter_total_bases (+105, model 55.7%)
- **2-leg @ +320 (prob 33.5%, EV +40.55%)**
  - Yordan Alvarez OVER 1.5 batter_total_bases (-103, model 63.1%)
  - Drake Baldwin OVER 1.5 batter_total_bases (+113, model 53.1%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 184 | 54.9% | 55.9% | 1.019 | 0.982 |
| batter total bases | 87 | 47.1% | 47.3% | 1.004 | 0.997 |

Cumulative graded plays: 10358. Wins: 3729. Hit rate: 36.0%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ NYY | 37.9% | +164 | 4.91 | -286 | +286 |
| PIT @ CHW | 61.5% | -160 | 2.34 | +127 | -127 |
| TEX @ SEA | 32.6% | +207 | 5.61 | +320 | -320 |

## Team Form (last 10)

**Hot:** LAD 8-2 (W7, +21), TOR 6-4 (L1, +18), NYY 6-4 (W2, +16), TEX 6-4 (L1, +14), PIT 8-2 (W3, +13)

**Cold:** WSH 2-8 (L7, -20), KC 3-7 (W1, -15), CLE 5-5 (L1, -14), CIN 5-5 (L3, -12), DET 4-6 (W1, -10)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.0 IP across 2 games
- PIT: 9.4 IP across 2 games
- SD: 8.6 IP across 2 games
- TOR: 8.3 IP across 2 games
- ATL: 9.3 IP across 2 games
- CWS: 10.5 IP across 2 games
- MIA: 10.2 IP across 2 games
- AZ: 11.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.2**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-10._