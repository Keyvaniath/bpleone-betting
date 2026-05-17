# EdgeStat Daily Brief - 2026-05-17

**Model Confidence: 73.7/100 [GREEN-LIGHT]** -- Model is healthy. Use capped Kelly (<=0.5u) until residual variance tightens further.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-05-17T22:58:15 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**SDP @ SEA - UNDER_7.5**
- Market: -110
- Model probability: 70.5%
- Raw edge: +34.52%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | SDP @ SEA | T-Mobile Park | indoor | UNDER_7.5 +34.52% |

## Parlays - top 5

- **3-leg @ +654 (prob 19.9%, EV +49.89%)**
  - BAL @ WSN WSN_ML (+107, model 57.9%)
  - TOR @ DET OVER_7.5 (-110, model 61.1%)
  - NYY @ NYM UNDER_8.5 (-110, model 56.2%)
- **3-leg @ +389 (prob 30.6%, EV +49.61%)**
  - CIN @ CLE CLE_ML (-168, model 70.2%)
  - TOR @ DET OVER_7.5 (-110, model 61.1%)
  - SDP @ SEA SEA_ML (-165, model 71.4%)
- **3-leg @ +586 (prob 21.8%, EV +49.33%)**
  - MIA @ TBR OVER_7.0 (-110, model 57.5%)
  - BAL @ WSN WSN_ML (+107, model 57.9%)
  - PHI @ PIT PIT_ML (-136, model 65.3%)
- **3-leg @ +425 (prob 28.4%, EV +49.12%)**
  - MIA @ TBR OVER_7.0 (-110, model 57.5%)
  - CIN @ CLE CLE_ML (-168, model 70.2%)
  - LAD @ LAA LAD_ML (-138, model 70.3%)
- **3-leg @ +429 (prob 28.2%, EV +49.08%)**
  - NYY @ NYM UNDER_8.5 (-110, model 56.2%)
  - LAD @ LAA LAD_ML (-138, model 70.3%)
  - SDP @ SEA SEA_ML (-165, model 71.4%)

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| batter doubles | 6191 | 14.8% | 15.9% | 1.073 | 0.932 |
| batter home runs | 6191 | 11.0% | 12.8% | 1.162 | 0.861 |
| batter total bases | 12384 | 26.3% | 31.7% | 1.206 | 0.829 |
| batter runs scored | 6191 | 37.0% | 38.7% | 1.047 | 0.955 |
| pitcher strikeouts | 2700 | 32.4% | 38.1% | 1.177 | 0.850 |
| batter rbis | 12382 | 19.7% | 23.1% | 1.173 | 0.853 |
| batter singles | 6191 | 43.8% | 44.5% | 1.016 | 0.984 |
| batter hits | 12384 | 39.8% | 41.6% | 1.047 | 0.955 |

Cumulative graded plays: 118201. Wins: 87361. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| SDP @ SEA | 49.9% | +101 | 3.48 | -130 | +130 |

## Team Form (last 10)

**Hot:** LAD 6-4 (W4, +18), MIL 8-2 (W3, +17), WSH 7-3 (W2, +16), CLE 7-3 (W1, +15), ATH 5-5 (L1, +14)

**Cold:** LAA 3-7 (L5, -30), DET 2-8 (L1, -27), COL 4-6 (W1, -18), HOU 4-6 (W2, -16), KC 2-8 (L6, -12)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 8.4 IP across 2 games
- TB: 11.0 IP across 2 games
- TOR: 10.4 IP across 2 games
- MIL: 8.0 IP across 2 games
- COL: 8.4 IP across 2 games
- DET: 11.3 IP across 2 games
- LAD: 10.0 IP across 2 games
- NYM: 11.4 IP across 2 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 2 parameter tweaks based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `calibration.n_prior_default`** ↓ 8 -> **5**
  - _1 market(s) have n>=200 but |residual|>0.4 -- prior is over-anchoring. Lowering N_PRIOR will let data correct faster._
- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 5.0 -> **3.5**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-05-16._