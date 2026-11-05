# EdgeStat Daily Summary — 2026-11-05

## 🏥 Model Health: 59.5/100 [OK]
- Operational but room to improve - check yellow components
  - 🟢 Calibration Freshness: 100.0/100
  - 🔴 Hit Rate Trend: 56.7/100
  - 🔴 Brier Trend: 17.9/100
  - 🟢 Pipeline Audit: 100.0/100
  - 🟡 Data Health: 72.7/100
  - 🔴 Edge Count: 0/100

## 🌐 Slate Overview
- **Regime today:** HOME_FAVORITE_DAY (avg P(home)=0.584)
- **Total games on board:** 67
- **Strong home favorites:** 30 | **Strong road dogs:** 15

## 🎯 Best Bets (sportsbook-priced only)
- No best bet today: a best bet needs a real sportsbook price — 18 model-only projections excluded (LOL 5, MLS 5, NCAAF 4, NFL 2, EPL 1, NHL 1).

## 🔒 Locks of the Day -- Track Record
- Sportsbook-priced: **3-0** (n=3; net +0.05u, ROI +62.0%) -- too few to judge
- PrizePicks (unverified, venue break-even, feed dark since 2026-07-09): 307-59 -- not a sportsbook record

## 🎮 Player projections (cross-sport) — model projection — unvalidated, no sportsbook price, not a recommendation
- **[LOL]** Inspired UNDER 3.5 Kills · model 61.7%
- **[LOL]** ShowMaker OVER 3.5 Kills · model 62.5%
- **[LOL]** Peyz OVER 4.5 Kills · model 61.3%
- **[LOL]** Hope OVER 4.5 Kills · model 61.3%
- **[CS]** torzsi OVER 40.5 Kills (BO3) · model 61.0%

## ⚡ Pre-Game
- No pre-game alerts: an alert needs a game-lines-desk probability whose verdict passed (not NO EDGE / UNPROVEN) and a DraftKings price. NBA: 14 not pre-game; NHL: 11 desk verdict NO EDGE; WNBA: 1 not pre-game; MLS: 15 no validated model probability (not from the game-lines desk); EPL: 1 no validated model probability (not from the game-lines desk); UCL: 9 not pre-game; NFL: 15 desk verdict UNPROVEN; NCAAF: 16 no validated model probability (not from the game-lines desk); NCAAB: 26 not pre-game; CWS: 1 not pre-game

## 🔥/❄️ Heat / Cold Signals
- Hot teams: **9** | Cold teams: **24** | Over-heavy: 0 | Under-heavy: 28
- Heating-up players: **20** | Cooling-down: 20

## ⚠️ Anomaly Detector (80)
- RESIDUAL_DIVERGENCE: **21**
- STREAK_MISMATCH: **1**
- STEAM_MOVE: **58**
  - Orlando Magic (NBA): Orlando Magic UNDERPERFORMING expected margin by 6.1pts in recent games -- model bias may persist
  - Golden State Warriors (NBA): Golden State Warriors OUTPERFORMING expected margin by 8.6pts in recent games -- model bias may persist
  - Montreal Canadiens (NHL): Montreal Canadiens UNDERPERFORMING expected margin by 8.6pts in recent games -- model bias may persist
  - Vegas Golden Knights (NHL): Vegas Golden Knights OUTPERFORMING expected margin by 7.9pts in recent games -- model bias may persist
  - Chicago Blackhawks (NHL): Chicago Blackhawks OUTPERFORMING expected margin by 7.3pts in recent games -- model bias may persist

## 💰 Today's Portfolio
- No priced picks: a stake is sized only at an actionable DraftKings quote.

## 🎯 Signal stacking (14 games with 2+ signals) — research, not picks
  - Utah Jazz @ New Orleans Pelicans : 5 signals (HEAT_COLD, HEAT_COLD, HEAT_COLD, ANOMALY)
  - Dallas Mavericks @ San Antonio Spurs : 4 signals (HEAT_COLD, HEAT_COLD, HEAT_COLD, ANOMALY)
  - New York City FC @ D.C. United : 4 signals (HEAT_COLD, HEAT_COLD, ANOMALY, ANOMALY)
  - Miami Heat @ LA Clippers : 3 signals (HEAT_COLD, HEAT_COLD, HEAT_COLD)
  - Toronto FC @ Philadelphia Union : 3 signals (HEAT_COLD, ANOMALY, ANOMALY)

## 🏀 NBA Player Heat (2 HOT / 0 COLD)
  - 🔥 **Giannis Antetokounmpo** (MIA): L5 28.2/15.2/7.4 vs season 28.0/11.5/5.6 [REB +3.7]
  - 🔥 **Franz Wagner** (ORL): L5 20.4/6.2/8.6 vs season 20.4/5.7/5.8 [AST +2.8]

## 🥊 UFC Fight Matchups (UFC Fight Night: Cortes Acosta vs. Walker) — model projection — unvalidated, no sportsbook price, not a recommendation
  - model favourite **Keiichiro Nakamura** (8-1-0) vs Ollie Schmid
  - model favourite **Nina Milošević** (9-1-0) vs Priscila Cachoeira
  - model favourite **Mantas Kondratavičius** (9-1-0) vs Andre Petroski
  - model favourite **Gabriel Lorenço** (8-1-0) vs Thomas Petersen
  - model favourite **Elijah Smith** (10-1-0) vs Davey Grant

## 📈 Streaks (15) — record facts, not picks
- [NBA] New Orleans Pelicans on W3 L10 3-2
- [NBA] Utah Jazz on L5 L10 0-5
- [NBA] Phoenix Suns on L3 L10 1-3
- [NBA] San Antonio Spurs on W5 L10 5-0
- [NBA] LA Clippers on L6 L10 0-5

## 📉 Walk-Forward Trajectory (n_windows=3d × 8 markets)
- 📈 Improving: **1** · ➖ Flat: 4 · 📉 Degrading: **3**
  - ✅ pitcher_strikeouts (Brier Δ +0.0060)
  - ⚠️ batter_total_bases (Brier Δ -0.0099)
  - ⚠️ batter_home_runs (Brier Δ -0.0086)
  - ⚠️ batter_rbis (Brier Δ -0.0052)

## 🧠 Training Convergence
- ELITE: **0** · HEALTHY: 0 · OK: 1 · DEGRADED: **1**
  - ⚠️ **batter_hits**: DIVERGENT - consistent same-sign moves (structural issue) (cf=0.9911)

## 🤖 Self-Training Status
- **NBA**: n=107 games · hit rate 58.9% · bias +5.8pp
- **NHL**: n=97 games · hit rate 53.6% · bias -3.8pp
- **WNBA**: n=4 games · hit rate 50.0% · bias -15.3pp
- **MLS**: n=60 games · hit rate 43.3% · bias +0.8pp
- **EPL**: n=30 games · hit rate 50.0% · bias +6.7pp
- **MLB**: n=5 games · hit rate 80.0% · bias -25.5pp
