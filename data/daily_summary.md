# EdgeStat Daily Brief - 2026-06-27

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-27T22:02:52 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ MIN - OVER_9.5**
- Market: -110
- Model probability: 81.0%
- Raw edge: +54.73%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (9 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 6:10p ET | ARI @ TBR | Tropicana Field | indoor | UNDER_8.5 +50.46% |
| 7:05p ET | WSN @ BAL | Oriole Park at Camden Yards | 72F 1mph | OVER_9.0 +29.39% |
| 7:10p ET | SEA @ CLE | Progressive Field | 69F 3mph | UNDER_7.5 +10.3% |
| 7:10p ET | COL @ MIN | Target Field | 75F 6mph | OVER_9.5 +54.73% |
| 7:10p ET | CHC @ MIL | American Family Field | indoor | OVER_8.0 +11.54% |
| 7:15p ET | MIA @ STL | Busch Stadium | 76F 3mph | MIA_ML +3.44% |
| 8:40p ET | LAD @ SDP | Petco Park | 65F 3mph | UNDER_8.0 +42.19% |
| 9:05p ET | ATL @ SFG | Oracle Park | 57F 10mph | UNDER_8.0 +12.08% |
| 9:38p ET | OAK @ LAA | Angel Stadium | 64F 6mph | OVER_8.5 +6.69% |

## Parlays - top 5

- **3-leg @ +684 (prob 18.5%, EV +44.91%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +684 (prob 18.3%, EV +43.3%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - SEA @ CLE UNDER_7.5 (-110, model 57.8%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +510 (prob 23.4%, EV +42.74%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - LAD @ SDP LAD_ML (-206, model 74.0%)
  - ATL @ SFG UNDER_8.0 (-110, model 58.7%)
- **3-leg @ +684 (prob 18.2%, EV +42.62%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - SEA @ CLE UNDER_7.5 (-110, model 57.8%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
- **3-leg @ +510 (prob 23.3%, EV +42.06%)**
  - ARI @ TBR ARI_ML (+115, model 53.9%)
  - CHC @ MIL OVER_8.0 (-110, model 58.4%)
  - LAD @ SDP LAD_ML (-206, model 74.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| ARI @ TBR | 52.4% | -110 | 3.23 | +220 | -220 |
| ATL @ SFG | 41.5% | +141 | 4.68 | +175 | -175 |
| CHC @ MIL | 27.2% | +267 | 6.5 | -102 | +102 |
| COL @ MIN | 37.5% | +167 | 4.82 | +128 | -128 |
| LAD @ SDP | 56.6% | -131 | 2.84 | +568 | -568 |
| MIA @ STL | 42.3% | +136 | 4.26 | +160 | -160 |
| OAK @ LAA | 34.6% | +189 | 5.5 | +166 | -166 |
| SEA @ CLE | 53.9% | -117 | 3.05 | +284 | -284 |
| WSN @ BAL | 59.2% | -145 | 2.62 | +159 | -159 |

## Team Form (last 10)

**Hot:** CHC 7-3 (L1, +24), PHI 7-3 (W4, +21), BOS 6-4 (W3, +16), MIL 7-3 (W5, +15), MIN 6-4 (W1, +14)

**Cold:** NYM 2-8 (L7, -25), NYY 3-7 (L3, -20), ATL 3-7 (W1, -18), KC 5-5 (L3, -17), STL 4-6 (L3, -17)

## Gassed Bullpens (> 8.0 IP in 2 days)

- TB: 10.3 IP across 2 games
- CHC: 8.1 IP across 2 games
- HOU: 13.1 IP across 3 games
- KC: 8.5 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-26._