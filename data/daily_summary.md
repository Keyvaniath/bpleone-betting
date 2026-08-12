# EdgeStat Daily Brief - 2026-08-12

**Model Confidence: 21.6/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-12T21:42:01 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**CHC @ WSN - OVER_8.5**
- Market: -110
- Model probability: 84.6%
- Raw edge: +61.56%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | CLE @ DET | Comerica Park | 72F 9mph | DET_ML +40.03% |
| 6:40p ET | PIT @ MIA | loanDepot park | indoor | OVER_7.5 +31.77% |
| 6:45p ET | CHC @ WSN | Nationals Park | 77F 5mph | OVER_8.5 +61.56% |
| 7:05p ET | SEA @ NYY | Yankee Stadium | 74F 6mph | NYY_ML +11.96% |
| 7:07p ET | BOS @ TOR | Rogers Centre | indoor | UNDER_8.0 +23.34% |
| 7:15p ET | NYM @ ATL | Truist Park | 78F 4mph | OVER_8.5 +2.77% |
| 7:40p ET | CIN @ CHW | Rate Field | 73F 3mph | OVER_8.5 +27.28% |
| 10:10p ET | KCR @ LAD | UNIQLO Field at Dodger Stadium | 67F 3mph | KCR_ML +31.67% |
| 10:10p ET | TEX @ LAA | Angel Stadium | 69F 4mph | OVER_8.5 +49.83% |

## Parlays - top 5

- **3-leg @ +596 (prob 21.5%, EV +49.76%)**
  - CLE @ DET UNDER_8.5 (-110, model 56.8%)
  - BOS @ TOR UNDER_8.0 (-110, model 64.6%)
  - KCR @ LAD OVER_9.0 (-110, model 58.7%)
- **3-leg @ +512 (prob 24.4%, EV +49.69%)**
  - CLE @ DET UNDER_8.5 (-110, model 56.8%)
  - SEA @ NYY NYY_ML (-147, model 66.6%)
  - BOS @ TOR UNDER_8.0 (-110, model 64.6%)
- **3-leg @ +485 (prob 25.4%, EV +49.0%)**
  - CLE @ DET UNDER_8.5 (-110, model 56.8%)
  - BOS @ TOR BOS_ML (-165, model 71.4%)
  - CIN @ CHW OVER_8.5 (-110, model 62.8%)
- **2-leg @ +264 (prob 40.6%, EV +47.81%)**
  - BOS @ TOR UNDER_8.0 (-110, model 64.6%)
  - CIN @ CHW OVER_8.5 (-110, model 62.8%)
- **3-leg @ +565 (prob 22.0%, EV +46.6%)**
  - CHC @ WSN WSN_ML (+117, model 47.8%)
  - BOS @ TOR UNDER_8.0 (-110, model 64.6%)
  - BOS @ TOR BOS_ML (-165, model 71.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8215. Wins: 3238. Hit rate: 39.4%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BOS @ TOR | 47.4% | +111 | 3.73 | +476 | -476 |
| CHC @ WSN | 43.5% | +130 | 4.28 | +174 | -174 |
| CIN @ CHW | 30.0% | +233 | 6.15 | +114 | -114 |
| CLE @ DET | 37.6% | +166 | 4.82 | -126 | +126 |
| KCR @ LAD | 30.2% | +231 | 6.06 | +151 | -151 |
| NYM @ ATL | 47.2% | +112 | 3.85 | +103 | -103 |
| PIT @ MIA | 45.3% | +121 | 3.96 | +219 | -219 |
| SEA @ NYY | 29.4% | +240 | 6.2 | -115 | +115 |
| TEX @ LAA | 32.1% | +211 | 5.84 | +654 | -654 |

## Team Form (last 10)

**Hot:** DET 8-2 (W3, +51), BOS 6-4 (L4, +26), CHC 8-2 (W2, +22), TB 9-1 (W8, +20), ATL 7-3 (W1, +20)

**Cold:** ATH 2-8 (L2, -35), SEA 3-7 (L5, -25), LAA 4-6 (W1, -18), KC 3-7 (L3, -16), PIT 3-7 (L2, -16)

## Gassed Bullpens (> 8.0 IP in 2 days)

- STL: 9.6 IP across 3 games
- TOR: 8.3 IP across 2 games
- MIN: 9.0 IP across 3 games
- BAL: 10.6 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-12._