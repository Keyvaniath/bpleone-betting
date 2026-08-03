# EdgeStat Daily Brief - 2026-08-03

**Model Confidence: 20.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (10/15 artifacts ok; 5 empty, 0 stale)._ 

_Generated at 2026-08-03T08:17:35 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ PHI - WSN_ML**
- Market: +130
- Model probability: 72.5%
- Raw edge: +66.76%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (8 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:40p ET | WSN @ PHI | Citizens Bank Park | 73F 5mph | WSN_ML +66.76% |
| 7:05p ET | STL @ NYY | Yankee Stadium | 69F 4mph | NYY_ML +17.23% |
| 7:40p ET | PIT @ MIL | American Family Field | indoor | OVER_8.5 +45.55% |
| 8:05p ET | LAD @ CHC | Wrigley Field | 66F 5mph | OVER_8.0 +44.02% |
| 8:05p ET | SFG @ TEX | Globe Life Field | indoor | OVER_8.0 +24.2% |
| 8:10p ET | TOR @ HOU | Daikin Park | indoor | OVER_9.0 +38.27% |
| 8:40p ET | TBR @ COL | Coors Field | 78F 12mph | OVER_11.5 +48.07% |
| 9:40p ET | SDP @ ARI | Chase Field | indoor | UNDER_8.5 +5.09% |

## Parlays - top 5

- **2-leg @ +408 (prob 29.4%, EV +49.28%)**
  - Brandon Nimmo OVER 1.5 batter_total_bases (+130, model 53.3%)
  - CJ Abrams OVER 1.5 batter_total_bases (+121, model 55.0%)
- **2-leg @ +443 (prob 27.5%, EV +49.07%)**
  - Shohei Ohtani OVER 1.5 batter_total_bases (+112, model 58.7%)
  - Corey Seager UNDER 0.5 batter_hits (+156, model 46.8%)
- **2-leg @ +290 (prob 38.2%, EV +49.06%)**
  - Shohei Ohtani OVER 1.5 batter_total_bases (+112, model 58.7%)
  - Chandler Simpson UNDER 1.5 batter_total_bases (-119, model 65.0%)
- **2-leg @ +231 (prob 45.0%, EV +48.97%)**
  - Brandon Nimmo OVER 1.5 batter_total_bases (+130, model 53.3%)
  - Cedric Mullins UNDER 1.5 batter_hits (-228, model 84.4%)
- **2-leg @ +270 (prob 40.2%, EV +48.96%)**
  - Junior Caminero UNDER 1.5 batter_hits (-148, model 73.1%)
  - CJ Abrams OVER 1.5 batter_total_bases (+121, model 55.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 7012. Wins: 2909. Hit rate: 41.5%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAD @ CHC | 51.3% | -105 | 3.36 | +174 | -174 |
| PIT @ MIL | 37.0% | +170 | 4.97 | +179 | -179 |
| SDP @ ARI | 50.3% | -101 | 3.43 | +162 | -162 |
| SFG @ TEX | 38.1% | +162 | 4.82 | +224 | -224 |
| STL @ NYY | 53.2% | -114 | 3.22 | -207 | +207 |
| TBR @ COL | 23.6% | +324 | 6.65 | +307 | -307 |
| TOR @ HOU | 31.0% | +223 | 5.86 | -174 | +174 |
| WSN @ PHI | 33.3% | +200 | 5.35 | +430 | -430 |

## Travel / Rest Flags

- **PIT @ MIL** (home): travel + back-to-back (+2h tz shift)
- **LAD @ CHC** (away): travel + back-to-back (+2h tz shift)
- **SFG @ TEX** (away): travel + back-to-back (+2h tz shift)
- **TBR @ COL** (away): travel + back-to-back (-2h tz shift)
- **SDP @ ARI** (home): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** DET 6-4 (W3, +35), CHC 6-4 (L1, +24), HOU 9-1 (W6, +21), SD 8-2 (W3, +17), BOS 8-2 (W5, +15)

**Cold:** ATH 2-8 (L5, -32), PIT 3-7 (L1, -21), LAA 2-8 (W1, -17), SEA 4-6 (W2, -14), KC 3-7 (L4, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.3 IP across 2 games
- PIT: 10.0 IP across 2 games
- SD: 8.8 IP across 2 games
- CWS: 9.2 IP across 2 games
- LAA: 9.3 IP across 2 games
- KC: 8.1 IP across 2 games
- NYM: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **-1.8**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-02._