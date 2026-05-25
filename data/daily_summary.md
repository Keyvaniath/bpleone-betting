# EdgeStat Daily Brief - 2026-05-25

**Model Confidence: 73.8/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-05-25T23:01:09 UTC. Game lines source: **placeholder -110 (no real book today)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**COL @ LAD - LAD_ML**
- Market: -110
- Model probability: 84.4%
- Raw edge: +61.07%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (4 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:05p ET | HOU @ TEX | Globe Life Field | indoor | OVER_8.5 +36.25% |
| 7:07p ET | MIA @ TOR | Rogers Centre | indoor | UNDER_8.5 +48.31% |
| 9:10p ET | COL @ LAD | UNIQLO Field at Dodger Stadium | 58F 3mph | LAD_ML +61.07% |
| 9:40p ET | SEA @ OAK | Sutter Health Park | 56F 10mph | OVER_8.5 +16.19% |

## Parlays - top 5

- **3-leg @ +497 (prob 25.1%, EV +49.62%)**
  - MIA @ TOR UNDER_7.0 (-110, model 58.1%)
  - MIA @ TOR TOR_ML (-157, model 67.4%)
  - SEA @ OAK UNDER_10.5 (-110, model 64.0%)
- **3-leg @ +596 (prob 21.5%, EV +49.56%)**
  - WSN @ CLE OVER_8.5 (-110, model 57.8%)
  - MIA @ TOR UNDER_7.0 (-110, model 58.1%)
  - SEA @ OAK UNDER_10.5 (-110, model 64.0%)
- **3-leg @ +467 (prob 26.3%, EV +49.21%)**
  - HOU @ TEX TEX_ML (-123, model 67.3%)
  - MIA @ TOR UNDER_7.0 (-110, model 58.1%)
  - MIA @ TOR TOR_ML (-157, model 67.4%)
- **3-leg @ +561 (prob 22.6%, EV +49.15%)**
  - WSN @ CLE OVER_8.5 (-110, model 57.8%)
  - HOU @ TEX TEX_ML (-123, model 67.3%)
  - MIA @ TOR UNDER_7.0 (-110, model 58.1%)
- **2-leg @ +246 (prob 43.1%, EV +49.11%)**
  - HOU @ TEX TEX_ML (-123, model 67.3%)
  - SEA @ OAK UNDER_10.5 (-110, model 64.0%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 8694 | 38.8% | 41.7% | 1.076 | 0.929 |
| batter total bases | 8694 | 25.4% | 31.9% | 1.255 | 0.797 |
| pitcher strikeouts | 1876 | 34.3% | 38.4% | 1.121 | 0.893 |
| batter singles | 4346 | 42.8% | 44.5% | 1.038 | 0.964 |
| batter rbis | 8692 | 19.4% | 23.2% | 1.200 | 0.833 |
| batter home runs | 4346 | 10.5% | 12.9% | 1.228 | 0.815 |
| batter runs scored | 4346 | 36.1% | 38.8% | 1.072 | 0.933 |
| batter doubles | 4346 | 14.4% | 16.0% | 1.107 | 0.904 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| COL @ LAD | 29.7% | +237 | 6.12 | -306 | +306 |
| HOU @ TEX | 33.6% | +198 | 5.45 | -125 | +125 |
| MIA @ TOR | 33.9% | +195 | 5.42 | -110 | +110 |
| SEA @ OAK | 30.0% | +233 | 6.32 | +153 | -153 |

## Travel / Rest Flags

- **PHI @ SDP** (away): travel + back-to-back (-3h tz shift)
- **HOU @ TEX** (home): travel + back-to-back (+2h tz shift)
- **COL @ LAD** (home): travel + back-to-back (-2h tz shift)
- **SEA @ OAK** (away): travel + back-to-back (-2h tz shift)

## Team Form (last 10)

**Hot:** LAD 8-2 (W2, +43), AZ 8-2 (W2, +32), CLE 8-2 (W1, +19), TB 7-3 (L1, +17), ATL 6-4 (L2, +11)

**Cold:** LAA 4-6 (W3, -30), COL 3-7 (L2, -27), CHC 1-9 (L9, -24), DET 2-8 (L1, -15), BAL 4-6 (W1, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 11.7 IP across 2 games
- PIT: 8.6 IP across 3 games
- SD: 9.1 IP across 2 games
- SF: 9.1 IP across 2 games
- STL: 10.4 IP across 3 games
- MIN: 8.6 IP across 3 games
- CWS: 12.5 IP across 3 games
- MIL: 10.5 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-24._