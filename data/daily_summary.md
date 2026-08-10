# EdgeStat Daily Brief - 2026-08-10

**Model Confidence: 20.9/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (11/15 artifacts ok; 4 empty, 0 stale)._ 

_Generated at 2026-08-10T06:11:30 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**TBR @ OAK - OVER_10.0**
- Market: -110
- Model probability: 72.5%
- Raw edge: +38.31%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (10 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:07p ET | BOS @ TOR | Rogers Centre | indoor | BOS_ML +31.04% |
| 7:15p ET | NYM @ ATL | Truist Park | 77F 0mph | UNDER_8.5 +2.74% |
| 7:40p ET | BAL @ MIN | Target Field | 79F 0mph | OVER_8.5 +35.31% |
| 7:45p ET | PHI @ STL | Busch Stadium | 86F 10mph | OVER_9.0 +17.78% |
| 9:38p ET | TEX @ LAA | Angel Stadium | 70F 4mph | UNDER_8.5 +7.62% |
| 9:40p ET | COL @ ARI | Chase Field | indoor | COL_ML +26.94% |
| 9:40p ET | TBR @ OAK | Sutter Health Park | 71F 8mph | OVER_10.0 +38.31% |
| 9:40p ET | MIL @ SDP | Petco Park | 70F 4mph | UNDER_7.5 +19.46% |
| 9:45p ET | HOU @ SFG | Oracle Park | 58F 9mph | UNDER_8.5 +26.33% |
| 10:10p ET | KCR @ LAD | UNIQLO Field at Dodger Stadium | 66F 3mph | OVER_7.5 +23.89% |

## Parlays - top 5

- **2-leg @ +684 (prob 19.1%, EV +49.95%)**
  - Nick Sogard UNDER 0.5 batter_hits (+197, model 41.9%)
  - Corey Seager UNDER 0.5 batter_hits (+164, model 45.6%)
- **2-leg @ +695 (prob 18.9%, EV +49.94%)**
  - Ivan Herrera UNDER 0.5 batter_hits (+201, model 41.4%)
  - Corey Seager UNDER 0.5 batter_hits (+164, model 45.6%)
- **2-leg @ +524 (prob 24.0%, EV +49.69%)**
  - Corbin Carroll UNDER 0.5 batter_hits (+200, model 40.9%)
  - Michael Harris II OVER 1.5 batter_total_bases (+108, model 58.7%)
- **2-leg @ +506 (prob 24.7%, EV +49.61%)**
  - Nick Sogard UNDER 0.5 batter_hits (+197, model 41.9%)
  - Michael Soroka OVER 4.5 pitcher_strikeouts (+104, model 58.9%)
- **2-leg @ +514 (prob 24.4%, EV +49.6%)**
  - Ivan Herrera UNDER 0.5 batter_hits (+201, model 41.4%)
  - Michael Soroka OVER 4.5 pitcher_strikeouts (+104, model 58.9%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|

Cumulative graded plays: 7374. Wins: 3031. Hit rate: 41.1%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| BAL @ MIN | 27.2% | +268 | 6.51 | +361 | -361 |
| BOS @ TOR | 24.1% | +315 | 7.12 | +964 | -964 |
| COL @ ARI | 41.5% | +141 | 4.4 | +194 | -194 |
| HOU @ SFG | 52.2% | -109 | 3.45 | +225 | -225 |
| KCR @ LAD | 60.0% | -150 | 2.58 | -224 | +224 |
| MIL @ SDP | 43.6% | +129 | 4.1 | +298 | -298 |
| NYM @ ATL | 49.0% | +104 | 3.56 | +135 | -135 |
| PHI @ STL | 38.4% | +161 | 5.01 | +141 | -141 |
| TBR @ OAK | 23.2% | +330 | 7.46 | +442 | -442 |
| TEX @ LAA | 43.1% | +132 | 4.27 | +230 | -230 |

## Travel / Rest Flags

- **TEX @ LAA** (home): travel + back-to-back (-3h tz shift)
- **TEX @ LAA** (away): travel + back-to-back (-2h tz shift)
- **TBR @ OAK** (home): travel + back-to-back (-3h tz shift)
- **MIL @ SDP** (away): travel + back-to-back (-2h tz shift)
- **KCR @ LAD** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** DET 7-3 (W2, +48), BOS 8-2 (L2, +35), ATL 8-2 (W1, +24), CHC 7-3 (W1, +18), HOU 6-4 (L2, +16)

**Cold:** ATH 2-8 (W2, -36), SEA 3-7 (L4, -26), LAA 3-7 (L2, -23), LAD 2-8 (L1, -18), KC 3-7 (L1, -17)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 9.0 IP across 2 games
- TB: 9.5 IP across 2 games
- TEX: 9.3 IP across 2 games
- TOR: 10.4 IP across 2 games
- PHI: 10.3 IP across 2 games
- CWS: 9.6 IP across 2 games
- MIL: 8.1 IP across 2 games
- LAA: 9.2 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.3**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-08-09._