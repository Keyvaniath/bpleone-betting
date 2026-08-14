# EdgeStat Daily Brief - 2026-08-14

**Model Confidence: 22.5/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-08-14T22:24:52 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYY @ TOR - NYY_ML**
- Market: +100
- Model probability: 82.3%
- Raw edge: +64.7%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (12 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | BOS @ PIT | PNC Park | 71F 4mph | BOS_ML +12.71% |
| 6:40p ET | CHW @ DET | Comerica Park | 73F 5mph | UNDER_8.5 +36.69% |
| 7:10p ET | WSN @ NYM | Citi Field | 72F 3mph | WSN_ML +55.16% |
| 7:10p ET | SDP @ CLE | Progressive Field | 71F 2mph | UNDER_8.5 +31.56% |
| 7:10p ET | BAL @ TBR | Tropicana Field | indoor | OVER_8.5 +12.32% |
| 7:15p ET | ARI @ ATL | Truist Park | 77F 3mph | ATL_ML +42.26% |
| 7:15p ET | NYY @ TOR | Rogers Centre | indoor | NYY_ML +64.7% |
| 8:10p ET | SEA @ HOU | Daikin Park | indoor | HOU_ML +14.19% |
| 9:38p ET | KCR @ LAA | Angel Stadium | 70F 4mph | KCR_ML +13.75% |
| 9:40p ET | TEX @ OAK | Sutter Health Park | 66F 9mph | OVER_8.5 +44.29% |
| 10:10p ET | MIL @ LAD | UNIQLO Field at Dodger Stadium | 66F 3mph | LAD_ML +25.39% |
| 10:15p ET | COL @ SFG | Oracle Park | 58F 12mph | OVER_8.5 +16.38% |

## Parlays - top 5

- **2-leg @ +190 (prob 50.2%, EV +45.43%)**
  - STL @ CHC CHC_ML (-193, model 77.0%)
  - BAL @ TBR OVER_8.0 (-110, model 65.1%)
- **2-leg @ +264 (prob 39.5%, EV +43.99%)**
  - WSN @ NYM OVER_8.5 (-110, model 60.7%)
  - BAL @ TBR OVER_8.0 (-110, model 65.1%)
- **2-leg @ +278 (prob 37.8%, EV +43.04%)**
  - MIA @ CIN MIA_ML (-102, model 58.1%)
  - BAL @ TBR OVER_8.0 (-110, model 65.1%)
- **2-leg @ +189 (prob 48.7%, EV +40.61%)**
  - BAL @ TBR OVER_8.0 (-110, model 65.1%)
  - ARI @ ATL ATL_ML (-195, model 74.7%)
- **2-leg @ +264 (prob 38.3%, EV +39.46%)**
  - BAL @ TBR OVER_8.0 (-110, model 65.1%)
  - KCR @ LAA OVER_8.5 (-110, model 58.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 8281. Wins: 3136. Hit rate: 37.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ ATL | 63.4% | -173 | 2.32 | -165 | +165 |
| BAL @ TBR | 33.8% | +196 | 5.43 | +127 | -127 |
| BOS @ PIT | 42.8% | +134 | 4.34 | +224 | -224 |
| CHW @ DET | 48.3% | +107 | 3.68 | +114 | -114 |
| COL @ SFG | 34.6% | +189 | 5.74 | +118 | -118 |
| KCR @ LAA | 33.4% | +199 | 5.58 | +225 | -225 |
| MIL @ LAD | 51.9% | -108 | 3.3 | -112 | +112 |
| NYY @ TOR | 47.0% | +113 | 3.77 | +874 | -874 |
| SDP @ CLE | 48.6% | +106 | 3.64 | +172 | -172 |
| SEA @ HOU | 42.9% | +133 | 4.23 | +118 | -118 |
| TEX @ OAK | 31.0% | +222 | 6.16 | +202 | -202 |
| WSN @ NYM | 25.2% | +296 | 6.87 | +617 | -617 |

## Travel / Rest Flags

- **SDP @ CLE** (away): 2 days rest (+3h tz)
- **BAL @ TBR** (home): 2 days rest (+3h tz)
- **ARI @ ATL** (away): 2 days rest (+2h tz)
- **SEA @ HOU** (home): 2 days rest (+2h tz)

## Team Form (last 10)

**Hot:** DET 7-3 (W1, +38), BOS 5-5 (W1, +26), TB 9-1 (W9, +23), STL 7-3 (W2, +19), CHC 8-2 (L1, +19)

**Cold:** ATH 2-8 (L3, -37), SEA 3-7 (W1, -28), KC 3-7 (L4, -12), SF 3-7 (L1, -12), COL 4-6 (W2, -11)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TEX: 8.3 IP across 2 games
- MIN: 8.3 IP across 2 games
- CWS: 8.3 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-13._