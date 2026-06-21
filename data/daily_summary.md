# EdgeStat Daily Brief - 2026-06-21

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **DEGRADED** (14/15 artifacts ok; 1 empty, 0 stale)._ 

_Generated at 2026-06-21T22:13:18 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYM @ PHI - UNDER_8.0**
- Market: -110
- Model probability: 60.8%
- Raw edge: +16.14%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | NYM @ PHI | Citizens Bank Park | 72F 3mph | UNDER_8.0 +16.14% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| NYM @ PHI | 35.5% | +181 | 5.24 | +118 | -118 |

## Team Form (last 10)

**Hot:** CHC 6-4 (L1, +22), MIL 5-5 (W1, +15), NYY 6-4 (L2, +13), DET 5-5 (W3, +13), MIN 7-3 (W2, +12)

**Cold:** TEX 4-6 (W1, -25), ATL 3-7 (L1, -23), SEA 3-7 (L2, -18), NYM 5-5 (L1, -15), CWS 4-6 (L3, -13)

## Gassed Bullpens (> 8.0 IP in 2 days)

- ATH: 9.3 IP across 2 games
- SD: 14.7 IP across 3 games
- STL: 9.3 IP across 2 games
- TB: 10.3 IP across 3 games
- TEX: 8.6 IP across 3 games
- TOR: 9.7 IP across 2 games
- MIN: 8.6 IP across 3 games
- ATL: 8.4 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-20._