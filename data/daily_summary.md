# EdgeStat Daily Brief - 2026-09-04

**Model Confidence: 19.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-04T23:48:25 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**OAK @ SEA - OVER_7.0**
- Market: -110
- Model probability: 78.0%
- Raw edge: +48.93%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (7 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 8:05p ET | TBR @ TEX | Globe Life Field | indoor | OVER_7.0 +44.73% |
| 8:10p ET | ARI @ HOU | Daikin Park | indoor | OVER_8.5 +40.63% |
| 8:10p ET | TOR @ KCR | Kauffman Stadium | 87F 5mph | KCR_ML +44.01% |
| 8:40p ET | STL @ COL | Coors Field | 74F 4mph | OVER_11.0 +36.21% |
| 9:40p ET | NYY @ SDP | Petco Park | 66F 1mph | NYY_ML +37.42% |
| 10:10p ET | WSN @ LAD | UNIQLO Field at Dodger Stadium | 64F 1mph | OVER_8.0 +15.83% |
| 10:10p ET | OAK @ SEA | T-Mobile Park | indoor | OVER_7.0 +48.93% |

## Parlays - top 5

- **2-leg @ +502 (prob 24.9%, EV +49.64%)**
  - Steven Kwan UNDER 0.5 batter_hits (+201, model 41.3%)
  - ATL @ PHI ATL_ML (+100, model 60.2%)
- **2-leg @ +282 (prob 39.2%, EV +49.59%)**
  - ATL @ PHI ATL_ML (+100, model 60.2%)
  - LAA @ PIT OVER_8.5 (-110, model 65.1%)
- **2-leg @ +713 (prob 18.2%, EV +47.78%)**
  - Steven Kwan UNDER 0.5 batter_hits (+201, model 41.3%)
  - Sal Frelick UNDER 0.5 batter_hits (+170, model 44.0%)
- **2-leg @ +415 (prob 28.7%, EV +47.74%)**
  - Sal Frelick UNDER 0.5 batter_hits (+170, model 44.0%)
  - LAA @ PIT OVER_8.5 (-110, model 65.1%)
- **2-leg @ +300 (prob 36.9%, EV +47.56%)**
  - ATL @ PHI ATL_ML (+100, model 60.2%)
  - STL @ COL STL_ML (+100, model 61.3%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 41 | 41.5% | 45.5% | 1.095 | 0.924 |
| batter hits | 95 | 53.7% | 57.0% | 1.061 | 0.946 |

Cumulative graded plays: 9875. Wins: 3534. Hit rate: 35.8%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ HOU | 28.5% | +251 | 6.27 | +117 | -117 |
| DET @ CLE | 34.3% | +191 | 5.35 | -- | -- |
| MIN @ CHW | 55.7% | -126 | 2.92 | -- | -- |
| NYY @ SDP | 56.5% | -130 | 2.85 | +445 | -445 |
| OAK @ SEA | 21.1% | +373 | 7.77 | -130 | +130 |
| STL @ COL | 26.7% | +275 | 6.75 | +253 | -253 |
| TBR @ TEX | 36.9% | +171 | 4.98 | +223 | -223 |
| TOR @ KCR | 32.2% | +211 | 5.77 | -190 | +190 |
| WSN @ LAD | 46.3% | +116 | 3.86 | -228 | +228 |

## Travel / Rest Flags

- **ATL @ PHI** (home): 2 days rest (+2h tz)
- **LAA @ PIT** (away): 2 days rest (+3h tz)
- **NYY @ SDP** (home): 2 days rest (-3h tz)
- **WSN @ LAD** (away): 2 days rest (-3h tz)

## Team Form (last 10)

**Hot:** CHC 4-6 (W1, +18), NYY 6-4 (W2, +15), BAL 6-4 (L3, +14), PHI 7-3 (L1, +11), ATL 8-2 (W1, +10)

**Cold:** DET 3-7 (W1, -30), BOS 4-6 (W1, -23), CIN 5-5 (W2, -16), LAA 1-9 (L2, -12), NYM 4-6 (W1, -11)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.3 IP across 2 games
- PIT: 11.2 IP across 2 games
- SEA: 8.1 IP across 2 games
- STL: 12.1 IP across 2 games
- TB: 8.4 IP across 2 games
- BOS: 8.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-04._