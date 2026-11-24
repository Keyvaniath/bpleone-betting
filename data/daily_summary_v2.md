# EdgeStat Daily Summary — 2026-11-24

## 🏥 Model Health: 66.3/100 [OK]
- Operational but room to improve - check yellow components
  - 🟢 Calibration Freshness: 100.0/100
  - 🟡 Hit Rate Trend: 66.9/100
  - 🔴 Brier Trend: 27.3/100
  - 🟢 Pipeline Audit: 100.0/100
  - 🟢 Data Health: 87.5/100
  - 🔴 Edge Count: 0/100

## 🌐 Slate Overview
- **Regime today:** HOME_FAVORITE_DAY (avg P(home)=0.595)
- **Total games on board:** 30
- **Strong home favorites:** 16 | **Strong road dogs:** 9

## 🎯 Best Bets (sportsbook-priced only)
- No best bet today: a best bet needs a real sportsbook price — 11 model-only projections excluded (UCL 4, LOL 3, NCAAF 2, NBA 1, EPL 1).

## 🔒 Locks of the Day -- Track Record
- Sportsbook-priced: **3-0** (n=3; net +0.05u, ROI +60.8%) -- too few to judge
- PrizePicks (unverified, venue break-even, feed dark since 2026-07-09): 307-59 -- not a sportsbook record

## 🎮 Player projections (cross-sport) — model projection — unvalidated, no sportsbook price, not a recommendation
- **[LOL]** Inspired UNDER 3.5 Kills · model 61.7%
- **[LOL]** ShowMaker OVER 3.5 Kills · model 62.5%
- **[LOL]** Peyz OVER 4.5 Kills · model 61.3%
- **[LOL]** Hope OVER 4.5 Kills · model 61.3%
- **[CS]** torzsi OVER 40.5 Kills (BO3) · model 61.0%

## ⚡ Pre-Game
- No pre-game alerts: an alert needs a game-lines-desk probability whose verdict passed (not NO EDGE / UNPROVEN) and a DraftKings price. NBA: 3 desk verdict NO EDGE; NHL: 1 desk verdict NO EDGE; WNBA: 1 not pre-game; MLS: 1 no validated model probability (not from the game-lines desk); EPL: 1 no validated model probability (not from the game-lines desk); UCL: 7 no validated model probability (not from the game-lines desk); NFL: 13 not pre-game; NCAAF: 23 no validated model probability (not from the game-lines desk); NCAAB: 4 not pre-game; CWS: 1 not pre-game

## 🔥/❄️ Heat / Cold Signals
- Hot teams: **8** | Cold teams: **9** | Over-heavy: 0 | Under-heavy: 26
- Heating-up players: **20** | Cooling-down: 20

## ⚠️ Anomaly Detector (124)
- RESIDUAL_DIVERGENCE: **1**
- STEAM_MOVE: **123**
  - Orlando Magic (NBA): Orlando Magic UNDERPERFORMING expected margin by 8.4pts in recent games -- model bias may persist
  - USC @ UCLA (NCAAF): 2026-11-28: ML/TOTAL line moved since open (pre-game DK): ML -24.7pp toward USC; total -7 (UNDER) (13 snapshots) -- a line move, not a read on who bet
  - NE @ LAC (NFL): 2026-11-29: ML/TOTAL line moved since open (pre-game DK): ML -14.5pp toward NE; total -5 (UNDER) (18 snapshots) -- a line move, not a read on who bet
  - SAC @ HAW (NCAAF): 2026-11-28: TOTAL line moved since open (pre-game DK): ML +1.3pp toward HAW; total -5 (UNDER) (5 snapshots) -- a line move, not a read on who bet
  - CHSO @ JMU (NCAAB): 2026-11-24: TOTAL line moved since open (pre-game DK): ML +0.4pp toward JMU; total +5 (OVER) (3 snapshots) -- a line move, not a read on who bet

## 💰 Today's Portfolio
- No priced picks: a stake is sized only at an actionable DraftKings quote.

## 🎯 Signal stacking (10 games with 2+ signals) — research, not picks
  - Dallas Mavericks @ Denver Nuggets : 3 signals (HEAT_COLD, HEAT_COLD, HEAT_COLD)
  - Brooklyn Nets @ Minnesota Timberwolves : 2 signals (HEAT_COLD, HEAT_COLD)
  - Phoenix Suns @ New Orleans Pelicans : 2 signals (HEAT_COLD, HEAT_COLD)
  - Utah Jazz @ Los Angeles Lakers : 2 signals (HEAT_COLD, HEAT_COLD)
  - Detroit Pistons @ Orlando Magic : 2 signals (HEAT_COLD, ANOMALY)

## 🏀 NBA Player Heat (0 HOT / 2 COLD)
  - ❄️ **Trae Young** (WSH): L5 10.2 vs season 17.3 [PTS -7.1]
  - ❄️ **Santi Aldama** (DAL): L5 3.8 vs season 9.1 [PTS -5.3, REB -2.8]

## 🥊 UFC Fight Matchups (UFC Fight Night: Adesanya vs Magomedov) — model projection — unvalidated, no sportsbook price, not a recommendation
  - model favourite **Magomed Tuchalov** (7-0-0) vs Ion Cutelaba
  - model favourite **Mario Pinto** (13-0-0) vs Serghei Spivac
  - model favourite **Jafel Filho** (17-5-0) vs Bruno Silva
  - model favourite **Yaroslav Amosov** (30-1-0) vs Ian Machado Garry
  - model favourite **Luke Riley** (14-0-0) vs Gabriel Santos

## 📈 Streaks (5) — record facts, not picks
- [NBA] Washington Wizards on W3 L10 3-2
- [NBA] Boston Celtics on L4 L10 1-4
- [NBA] Denver Nuggets on W3 L10 4-1
- [NBA] Dallas Mavericks on W3 L10 3-2
- [NHL] Edmonton Oilers on L3 L10 2-3

## 📉 Walk-Forward Trajectory (n_windows=3d × 8 markets)
- 📈 Improving: **1** · ➖ Flat: 4 · 📉 Degrading: **3**
  - ✅ pitcher_strikeouts (Brier Δ +0.0060)
  - ⚠️ batter_total_bases (Brier Δ -0.0099)
  - ⚠️ batter_home_runs (Brier Δ -0.0086)
  - ⚠️ batter_rbis (Brier Δ -0.0052)

## 🧠 Training Convergence
- ELITE: **0** · HEALTHY: 0 · OK: 0 · DEGRADED: **2**

## 🤖 Self-Training Status
- **NBA**: n=104 games · hit rate 63.5% · bias +1.8pp
- **NHL**: n=99 games · hit rate 51.5% · bias +12.8pp [calibration applied]
- **MLS**: n=24 games · hit rate 50.0% · bias +8.2pp
- **EPL**: n=20 games · hit rate 55.0% · bias -24.7pp
