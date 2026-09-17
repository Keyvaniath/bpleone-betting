# EdgeStat Daily Brief - 2026-09-17

**Model Confidence: 21.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-17T14:03:04 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAD @ CIN - OVER_9.5**
- Market: -110
- Model probability: 88.9%
- Raw edge: +69.65%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 12:35p ET | MIL @ PIT | PNC Park | 81F 11mph | OVER_8.5 +15.17% |
| 12:40p ET | LAD @ CIN | Great American Ball Park | 96F 8mph | OVER_9.5 +69.65% |
| 1:10p ET | OAK @ TBR | Tropicana Field | indoor | OVER_7.5 +48.01% |
| 3:10p ET | SDP @ COL | Coors Field | 79F 9mph | OVER_11.0 +44.48% |
| 7:15p ET | KCR @ HOU | Daikin Park | indoor | KCR_ML +6.66% |
| 7:15p ET | PHI @ NYM | Citi Field | 72F 6mph | OVER_8.0 +4.44% |
| 7:40p ET | DET @ CHW | Rate Field | 68F 11mph | OVER_8.5 +33.89% |
| 8:05p ET | BOS @ TEX | Globe Life Field | indoor | OVER_7.5 +4.78% |
| 9:38p ET | MIN @ LAA | Angel Stadium | 67F 2mph | OVER_7.5 +6.81% |

## Parlays - top 5

- **2-leg @ +452 (prob 26.2%, EV +44.62%)**
  - Brice Turang UNDER 0.5 batter_hits (+180, model 43.9%)
  - DET @ CHW DET_ML (-103, model 59.8%)
- **2-leg @ +435 (prob 26.9%, EV +43.91%)**
  - Brice Turang UNDER 0.5 batter_hits (+180, model 43.9%)
  - DET @ CHW OVER_8.5 (-110, model 61.4%)
- **2-leg @ +279 (prob 37.7%, EV +42.87%)**
  - Brice Turang UNDER 0.5 batter_hits (+180, model 43.9%)
  - OAK @ TBR TBR_ML (-284, model 86.0%)
- **2-leg @ +460 (prob 25.3%, EV +41.8%)**
  - Konnor Griffin UNDER 0.5 batter_hits (+184, model 42.4%)
  - DET @ CHW DET_ML (-103, model 59.8%)
- **2-leg @ +367 (prob 30.3%, EV +41.78%)**
  - Oneil Cruz OVER 1.5 batter_total_bases (+137, model 50.8%)
  - DET @ CHW DET_ML (-103, model 59.8%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 251 | 51.8% | 55.8% | 1.078 | 0.929 |
| batter total bases | 113 | 45.1% | 47.0% | 1.041 | 0.963 |

Cumulative graded plays: 11221. Wins: 4202. Hit rate: 37.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ TEX | 46.3% | +116 | 3.85 | +187 | -187 |
| DET @ CHW | 53.5% | -115 | 2.93 | +251 | -251 |
| KCR @ HOU | 26.5% | +277 | 6.64 | +145 | -145 |
| LAD @ CIN | 13.7% | +632 | 10.32 | +766 | -766 |
| MIL @ PIT | 34.2% | +192 | 5.67 | +163 | -163 |
| MIN @ LAA | 53.0% | -113 | 3.21 | +217 | -217 |
| OAK @ TBR | 45.7% | +119 | 3.91 | -350 | +350 |
| PHI @ NYM | 50.5% | -102 | 3.54 | +128 | -128 |
| SDP @ COL | 32.7% | +206 | 5.89 | +193 | -193 |

## Travel / Rest Flags

- **MIN @ LAA** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** MIL 7-3 (W2, +26), TB 8-2 (W5, +25), DET 7-3 (L1, +25), LAD 7-3 (L1, +23), NYY 7-3 (L1, +18)

**Cold:** CIN 3-7 (W1, -39), MIN 3-7 (W1, -34), COL 1-9 (L1, -32), HOU 3-7 (L1, -18), ATH 5-5 (L2, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.6 IP across 2 games
- TEX: 8.3 IP across 2 games
- TOR: 11.2 IP across 2 games
- MIN: 9.5 IP across 2 games
- CWS: 10.6 IP across 2 games
- MIA: 11.5 IP across 2 games
- AZ: 10.1 IP across 2 games
- BAL: 8.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-0.1**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-16._