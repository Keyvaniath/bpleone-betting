# EdgeStat Daily Brief - 2026-06-24

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-24T23:09:35 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**ATL @ SDP - ATL_ML**
- Market: -121
- Model probability: 75.9%
- Raw edge: +38.7%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (6 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:10p ET | CHC @ NYM | Citi Field | 70F 4mph | CHC_ML +15.87% |
| 7:10p ET | MIL @ CIN | Great American Ball Park | 70F 3mph | MIL_ML +33.77% |
| 7:40p ET | LAD @ MIN | Target Field | 64F 5mph | LAD_ML +18.02% |
| 7:45p ET | ARI @ STL | Busch Stadium | 74F 5mph | OVER_9.0 +7.89% |
| 8:40p ET | ATL @ SDP | Petco Park | 66F 6mph | ATL_ML +38.7% |
| 9:45p ET | OAK @ SFG | Oracle Park | 56F 11mph | OAK_ML +33.7% |

## Parlays - top 5

- **2-leg @ +278 (prob 39.3%, EV +48.42%)**
  - CHC @ NYM CHC_ML (-102, model 60.6%)
  - BOS @ COL OVER_11.0 (-110, model 64.8%)
- **2-leg @ +264 (prob 40.6%, EV +47.89%)**
  - BOS @ COL OVER_11.0 (-110, model 64.8%)
  - SEA @ PIT UNDER_8.0 (-110, model 62.6%)
- **2-leg @ +278 (prob 38.0%, EV +43.47%)**
  - CHC @ NYM CHC_ML (-102, model 60.6%)
  - SEA @ PIT UNDER_8.0 (-110, model 62.6%)
- **2-leg @ +301 (prob 35.8%, EV +43.36%)**
  - BOS @ COL OVER_11.0 (-110, model 64.8%)
  - PHI @ WSN WSN_ML (+110, model 55.2%)
- **2-leg @ +305 (prob 35.0%, EV +41.71%)**
  - BOS @ COL OVER_11.0 (-110, model 64.8%)
  - NYY @ DET NYY_ML (+112, model 54.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ STL | 37.4% | +167 | 5.08 | +134 | -134 |
| ATL @ SDP | 49.8% | +101 | 3.37 | +618 | -618 |
| CHC @ NYM | 42.8% | +134 | 4.34 | +292 | -292 |
| HOU @ TOR | 22.9% | +336 | 7.36 | -- | -- |
| LAD @ MIN | 56.5% | -130 | 2.86 | +479 | -479 |
| MIL @ CIN | 37.0% | +171 | 5.05 | +551 | -551 |
| OAK @ SFG | 39.9% | +151 | 4.92 | +444 | -444 |

## Team Form (last 10)

**Hot:** CHC 7-3 (W1, +26), PHI 6-4 (W1, +18), KC 6-4 (W2, +16), MIL 6-4 (W3, +13), MIN 6-4 (L2, +12)

**Cold:** ATL 3-7 (L3, -22), TEX 4-6 (L1, -19), CWS 4-6 (W2, -18), ATH 4-6 (L3, -17), NYM 4-6 (L3, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- SD: 10.3 IP across 2 games
- TEX: 12.6 IP across 2 games
- TOR: 9.5 IP across 2 games
- MIN: 9.3 IP across 2 games
- PHI: 9.1 IP across 2 games
- HOU: 10.4 IP across 2 games
- LAD: 10.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-23._