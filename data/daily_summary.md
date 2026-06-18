# EdgeStat Daily Brief - 2026-06-18

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-18T23:39:01 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**LAA @ OAK - OVER_10.0**
- Market: -110
- Model probability: 79.5%
- Raw edge: +51.81%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (2 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:40p ET | STL @ KCR | Kauffman Stadium | 69F 4mph | KCR_ML +7.54% |
| 9:40p ET | LAA @ OAK | Sutter Health Park | 64F 8mph | OVER_10.0 +51.81% |

## Parlays - top 5

- **3-leg @ +485 (prob 25.5%, EV +49.48%)**
  - TOR @ BOS UNDER_9.5 (-110, model 55.3%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)
- **3-leg @ +599 (prob 21.4%, EV +49.35%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - CLE @ MIL MIL_ML (-147, model 71.9%)
  - CLE @ MIL UNDER_7.5 (-110, model 58.7%)
- **3-leg @ +655 (prob 19.8%, EV +49.24%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - MIN @ TEX OVER_7.5 (-110, model 61.0%)
  - MIN @ TEX MIN_ML (-123, model 64.1%)
- **3-leg @ +456 (prob 26.8%, EV +49.17%)**
  - TOR @ BOS UNDER_9.5 (-110, model 55.3%)
  - MIN @ TEX MIN_ML (-123, model 64.1%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)
- **3-leg @ +568 (prob 22.3%, EV +48.88%)**
  - TOR @ BOS TOR_ML (+118, model 50.6%)
  - SFG @ ATL OVER_8.0 (-110, model 58.1%)
  - LAA @ OAK OAK_ML (-165, model 75.7%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| LAA @ OAK | 46.7% | +114 | 10.66 | -763 | +763 |
| STL @ KCR | 42.1% | +138 | 4.42 | +146 | -146 |

## Team Form (last 10)

**Hot:** NYY 8-2 (W4, +29), MIL 7-3 (W3, +27), LAA 6-4 (L1, +20), MIA 7-3 (W1, +18), STL 6-4 (L1, +15)

**Cold:** HOU 5-5 (W2, -17), ATL 3-7 (L4, -17), PIT 4-6 (W2, -17), TEX 4-6 (L2, -16), CLE 3-7 (L2, -15)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.3 IP across 2 games
- SD: 10.5 IP across 2 games
- SF: 17.9 IP across 3 games
- TOR: 10.5 IP across 2 games
- PHI: 8.3 IP across 2 games
- ATL: 18.0 IP across 3 games
- MIL: 8.2 IP across 2 games
- CIN: 8.1 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-17._