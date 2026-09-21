# EdgeStat Daily Brief - 2026-09-21

**Model Confidence: 20.3/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-09-21T19:21:45 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ DET - OVER_8.5**
- Market: -110
- Model probability: 61.8%
- Raw edge: +17.93%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (3 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:35p ET | TOR @ BAL | Oriole Park at Camden Yards | 66F 9mph | BAL_ML +10.83% |
| 6:40p ET | WSN @ DET | Comerica Park | 56F 6mph | OVER_8.5 +17.93% |
| 9:45p ET | MIN @ SFG | Oracle Park | 56F 9mph | OVER_8.5 +4.61% |

## Parlays - top 5

- **2-leg @ +452 (prob 27.0%, EV +48.78%)**
  - James Wood OVER 1.5 batter_total_bases (+131, model 53.3%)
  - WSN @ DET WSN_ML (+139, model 50.6%)
- **2-leg @ +341 (prob 33.2%, EV +46.27%)**
  - James Wood OVER 1.5 batter_total_bases (+131, model 53.3%)
  - TOR @ BAL OVER_7.5 (-110, model 62.2%)
- **2-leg @ +341 (prob 32.9%, EV +45.22%)**
  - James Wood OVER 1.5 batter_total_bases (+131, model 53.3%)
  - WSN @ DET OVER_8.5 (-110, model 61.8%)
- **2-leg @ +510 (prob 23.7%, EV +44.45%)**
  - James Wood OVER 1.5 batter_total_bases (+131, model 53.3%)
  - George Springer UNDER 0.5 batter_hits (+164, model 44.4%)
- **2-leg @ +356 (prob 31.5%, EV +43.56%)**
  - TOR @ BAL OVER_7.5 (-110, model 62.2%)
  - WSN @ DET WSN_ML (+139, model 50.6%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter total bases | 138 | 44.9% | 47.2% | 1.050 | 0.954 |
| batter hits | 313 | 52.1% | 55.6% | 1.067 | 0.939 |

Cumulative graded plays: 12037. Wins: 4652. Hit rate: 38.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| MIN @ SFG | 45.4% | +120 | 4.18 | +155 | -155 |
| TOR @ BAL | 37.0% | +171 | 4.89 | +125 | -125 |
| WSN @ DET | 41.3% | +142 | 4.47 | +172 | -172 |

## Team Form (last 10)

**Hot:** MIL 8-2 (W3, +32), TB 8-2 (W2, +25), SD 9-1 (W5, +24), LAD 7-3 (W4, +24), CHC 6-4 (W2, +22)

**Cold:** CIN 3-7 (L2, -41), ATH 3-7 (L6, -34), COL 2-8 (L1, -23), HOU 3-7 (L3, -18), LAA 4-6 (L1, -14)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 13.0 IP across 2 games
- TEX: 10.7 IP across 2 games
- TOR: 8.3 IP across 2 games
- LAA: 9.4 IP across 2 games
- AZ: 9.6 IP across 2 games
- CIN: 8.0 IP across 2 games
- COL: 9.0 IP across 2 games
- LAD: 11.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-0.5**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-21._