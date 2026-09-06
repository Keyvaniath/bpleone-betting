# EdgeStat Daily Brief - 2026-09-06

**Model Confidence: 20.0/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-09-06T23:35:23 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**WSN @ LAD - OVER_8.0**
- Market: -110
- Model probability: 72.4%
- Raw edge: +38.12%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 10:10p ET | WSN @ LAD | UNIQLO Field at Dodger Stadium | 70F 2mph | OVER_8.0 +38.12% |

## Parlays - top 5

- **2-leg @ +345 (prob 33.7%, EV +49.99%)**
  - Matt Olson OVER 1.5 batter_total_bases (+118, model 55.8%)
  - TOR @ KCR KCR_ML (+104, model 60.4%)
- **2-leg @ +313 (prob 35.9%, EV +48.29%)**
  - Matt Olson OVER 1.5 batter_total_bases (+118, model 55.8%)
  - NYY @ SDP NYY_ML (-112, model 64.4%)
- **2-leg @ +289 (prob 38.0%, EV +48.1%)**
  - ATL @ PHI ATL_ML (-110, model 62.9%)
  - TOR @ KCR KCR_ML (+104, model 60.4%)
- **2-leg @ +367 (prob 31.5%, EV +47.2%)**
  - Elly De La Cruz OVER 1.5 batter_total_bases (+129, model 52.2%)
  - TOR @ KCR KCR_ML (+104, model 60.4%)
- **2-leg @ +361 (prob 31.8%, EV +46.53%)**
  - Sal Stewart OVER 1.5 batter_total_bases (+126, model 52.6%)
  - TOR @ KCR KCR_ML (+104, model 60.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter hits | 132 | 54.5% | 56.0% | 1.026 | 0.976 |
| batter total bases | 52 | 44.2% | 45.3% | 1.023 | 0.980 |

Cumulative graded plays: 10057. Wins: 3607. Hit rate: 35.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| WSN @ LAD | 34.4% | +191 | 5.3 | +158 | -158 |

## Team Form (last 10)

**Hot:** TOR 8-2 (W4, +24), CHC 5-5 (W3, +18), PHI 7-3 (W1, +15), NYY 6-4 (W1, +14), MIN 4-6 (W1, +12)

**Cold:** DET 3-7 (W1, -22), SEA 2-8 (L3, -22), BOS 5-5 (W3, -17), NYM 4-6 (L1, -11), CLE 5-5 (L1, -10)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 8.1 IP across 2 games
- SD: 10.5 IP across 2 games
- SF: 8.3 IP across 2 games
- TEX: 10.6 IP across 2 games
- TOR: 10.1 IP across 2 games
- CWS: 8.2 IP across 2 games
- MIL: 9.1 IP across 2 games
- CIN: 10.0 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-09-06._