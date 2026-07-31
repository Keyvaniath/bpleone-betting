# EdgeStat Daily Brief - 2026-07-31

**Model Confidence: 23.1/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-07-31T23:12:41 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ ATL - WSN_ML**
- Market: +164
- Model probability: 60.1%
- Raw edge: +58.74%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:15p ET | WSN @ ATL | Truist Park | 78F 4mph | WSN_ML +58.74% |
| 8:15p ET | TEX @ HOU | Daikin Park | indoor | OVER_8.5 +23.65% |
| 8:40p ET | KCR @ COL | Coors Field | 71F 6mph | OVER_12.0 +36.96% |
| 9:38p ET | MIL @ LAA | Angel Stadium | 73F 3mph | MIL_ML +57.9% |
| 9:40p ET | DET @ OAK | Sutter Health Park | 76F 5mph | DET_ML +29.03% |
| 9:45p ET | SFG @ SDP | Petco Park | 70F 2mph | UNDER_8.5 +12.8% |
| 10:10p ET | BOS @ LAD | UNIQLO Field at Dodger Stadium | 67F 3mph | UNDER_8.5 +32.89% |
| 10:10p ET | MIN @ SEA | T-Mobile Park | indoor | MIN_ML +5.03% |

## Parlays - top 5

- **2-leg @ +240 (prob 44.1%, EV +49.8%)**
  - WSN @ ATL WSN_ML (+101, model 59.8%)
  - DET @ OAK DET_ML (-145, model 73.7%)
- **2-leg @ +223 (prob 46.3%, EV +49.36%)**
  - STL @ TOR UNDER_7.5 (-110, model 62.8%)
  - DET @ OAK DET_ML (-145, model 73.7%)
- **2-leg @ +284 (prob 38.3%, EV +46.82%)**
  - NYY @ CHC OVER_9.0 (-110, model 63.9%)
  - WSN @ ATL WSN_ML (+101, model 59.8%)
- **2-leg @ +264 (prob 40.2%, EV +46.39%)**
  - NYY @ CHC OVER_9.0 (-110, model 63.9%)
  - STL @ TOR UNDER_7.5 (-110, model 62.8%)
- **2-leg @ +223 (prob 45.0%, EV +45.08%)**
  - MIL @ LAA OVER_9.0 (-110, model 61.0%)
  - DET @ OAK DET_ML (-145, model 73.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 6729. Wins: 2798. Hit rate: 41.6%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ CLE | 32.2% | +210 | 5.66 | -- | -- |
| BOS @ LAD | 49.2% | +103 | 8.73 | +105 | -105 |
| CHW @ TBR | 54.6% | -120 | 3.03 | -- | -- |
| DET @ OAK | 26.5% | +277 | 6.78 | +505 | -505 |
| KCR @ COL | 25.9% | +287 | 6.99 | +205 | -205 |
| MIA @ NYM | 20.4% | +389 | 7.94 | -- | -- |
| MIL @ LAA | 24.8% | +304 | 7.11 | +1174 | -1174 |
| MIN @ SEA | 29.0% | +245 | 6.19 | +133 | -133 |
| PHI @ BAL | 25.0% | +301 | 6.94 | -- | -- |
| SFG @ SDP | 26.0% | +285 | 6.67 | +103 | -103 |
| STL @ TOR | 61.9% | -163 | 2.4 | -- | -- |
| TEX @ HOU | 41.9% | +138 | 4.34 | +176 | -176 |
| WSN @ ATL | 49.6% | +102 | 3.43 | +244 | -244 |

## Travel / Rest Flags

- **TEX @ HOU** (home): 2 days rest (+2h tz)
- **DET @ OAK** (away): 2 days rest (-3h tz)
- **MIN @ SEA** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** TB 8-2 (W2, +29), CHC 6-4 (W1, +27), SF 5-5 (W2, +17), NYM 5-5 (W2, +13), WSH 5-5 (L2, +12)

**Cold:** COL 3-7 (L4, -19), PIT 3-7 (L3, -18), STL 3-7 (L1, -17), MIA 3-7 (L1, -15), TOR 4-6 (W1, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.2 IP across 2 games
- PIT: 9.2 IP across 2 games
- SD: 9.8 IP across 2 games
- STL: 8.2 IP across 2 games
- TB: 11.0 IP across 2 games
- ATL: 9.6 IP across 3 games
- CWS: 10.3 IP across 2 games
- NYM: 8.2 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-07-30._