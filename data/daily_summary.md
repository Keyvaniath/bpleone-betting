# EdgeStat Daily Brief - 2026-06-28

**Model Confidence: 27.4/100 [RED]** -- Calibration warming up. Research signal only; no real-money sizing yet.

_Pipeline health: **WARNING** (13/15 artifacts ok; 2 empty, 0 stale)._ 

_Generated at 2026-06-28T23:13:27 UTC. Game lines source: **Bovada (fallback -- DK primary unavailable)**. Pick-em opportunities from PrizePicks._

## Play of the Day

**NYY @ BOS - NYY_ML**
- Market: -109
- Model probability: 69.3%
- Raw edge: +32.88%
- Recommended stake: <= 0.5u (model calibrating)

> _Edge >= 15% is well above what a properly-calibrated baseball model produces. Treat this as a research signal until 30+ outcomes have flowed through the calibration loop._

## Full Slate (1 games)

| Time | Matchup | Park | Weather | Top edge |
|---|---|---|---|---|
| 7:20p ET | NYY @ BOS | Fenway Park | 69F 5mph | NYY_ML +32.88% |

## Self-Learning Loop

| Market | n settled | Hit rate | Model implied | Bias | Correction |
|---|---|---|---|---|---|
| pitcher strikeouts | 1 | 100.0% | 33.4% | 0.556 | 1.032 |
| batter hits | 45 | 64.4% | 40.2% | 0.631 | 1.309 |

Cumulative graded plays: 118214. Wins: 87366. Hit rate: 73.9%.

## Auxiliary Markets (Model Fair Prices)

| Matchup | NRFI % | NRFI fair | F5 total | RL home -1.5 fair | RL away +1.5 fair |
|---|---|---|---|---|---|
| NYY @ BOS | 44.0% | +127 | 4.24 | +398 | -398 |

## Team Form (last 10)

**Hot:** CHC 8-2 (W2, +33), MIA 8-2 (L1, +23), PIT 5-5 (W1, +22), CWS 5-5 (L1, +21), PHI 7-3 (W1, +20)

**Cold:** NYM 2-8 (L1, -28), STL 3-7 (W1, -24), NYY 3-7 (L3, -20), KC 5-5 (W1, -19), TOR 3-7 (L6, -19)

## Gassed Bullpens (> 8.0 IP in 2 days)

- PIT: 10.4 IP across 3 games
- SD: 9.5 IP across 2 games
- TB: 12.4 IP across 3 games
- TEX: 8.6 IP across 3 games
- TOR: 11.5 IP across 3 games
- PHI: 11.5 IP across 3 games
- ATL: 9.3 IP across 2 games
- CWS: 10.6 IP across 3 games

## Loop Activity (since last refresh)

- Confidence delta: **+0.0**

## Model Recommendations (operator review)

_The model is suggesting 1 parameter tweak based on its own performance. Apply via `data/runtime_config.json` on `/config`._

- **[MEDIUM] `live_edges.edge_threshold_pp`** ↓ 3.5 -> **2.0**
  - _Zero live edge alerts in last 24h despite live props being priced. Threshold may be too tight to surface anything actionable._

---

_EdgeStat is a research desk. Bet responsibly. 21+. 1-800-GAMBLER._
_Source: github.com/Keyvaniath/bpleone-betting - last settled 2026-06-27._