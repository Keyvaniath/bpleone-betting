# EdgeStat Daily Summary — 2026-11-25

## 🏥 Model Health: 64.0/100 [OK]
- Operational but room to improve - check yellow components
  - 🟢 Calibration Freshness: 100.0/100
  - 🔴 Hit Rate Trend: 53.2/100
  - 🔴 Brier Trend: 17.0/100
  - 🟢 Pipeline Audit: 100.0/100
  - 🟢 Data Health: 100.0/100
  - 🔴 Edge Count: 0/100

## 🌐 Slate Overview
- **Regime today:** HOME_FAVORITE_DAY (avg P(home)=0.594)
- **Total games on board:** 34
- **Strong home favorites:** 18 | **Strong road dogs:** 10

## 🎯 Best Bets (sportsbook-priced only)
- No best bet today: a best bet needs a real sportsbook price — 12 model-only projections excluded (LOL 3, NCAAB 3, UCL 2, NCAAF 2, NBA 1, EPL 1).

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
- No pre-game alerts: an alert needs a game-lines-desk probability whose verdict passed (not NO EDGE / UNPROVEN) and a DraftKings price. NBA: 3 not pre-game; NHL: 1 not pre-game; WNBA: 1 not pre-game; MLS: 1 started or no start time; EPL: 1 no validated model probability (not from the game-lines desk); UCL: 9 not pre-game; NFL: 13 not pre-game; NCAAF: 23 no validated model probability (not from the game-lines desk); NCAAB: 6 started or no start time; CWS: 1 not pre-game

## 🔥/❄️ Heat / Cold Signals
- Hot teams: **7** | Cold teams: **8** | Over-heavy: 0 | Under-heavy: 28
- Heating-up players: **20** | Cooling-down: 20

## ⚠️ Anomaly Detector (78)
- STEAM_MOVE: **78**
  - USC @ UCLA (NCAAF): 2026-11-28: ML/TOTAL line moved since open (pre-game DK): ML -24.7pp toward USC; total -7 (UNDER) (14 snapshots) -- a line move, not a read on who bet
  - NE @ LAC (NFL): 2026-11-29: ML/TOTAL line moved since open (pre-game DK): ML -14.8pp toward NE; total -5 (UNDER) (19 snapshots) -- a line move, not a read on who bet
  - SAC @ HAW (NCAAF): 2026-11-28: TOTAL line moved since open (pre-game DK): ML +1.3pp toward HAW; total -5 (UNDER) (5 snapshots) -- a line move, not a read on who bet
  - COLO @ STAN (NCAAB): 2026-11-24: ML line moved since open (pre-game DK): ML +24.5pp toward STAN (2 snapshots) -- a line move, not a read on who bet
  - DEN @ PIT (NFL): 2026-11-27: ML/TOTAL line moved since open (pre-game DK): ML -3.5pp toward DEN; total -4 (UNDER) (29 snapshots) -- a line move, not a read on who bet

## 💰 Today's Portfolio
- No priced picks: a stake is sized only at an actionable DraftKings quote.

## 🎯 Signal stacking (3 games with 2+ signals) — research, not picks
  - Dallas Mavericks @ Denver Nuggets : 3 signals (HEAT_COLD, HEAT_COLD, HEAT_COLD)
  - Detroit Pistons @ Orlando Magic : 2 signals (HEAT_COLD, ANOMALY)
  - Vegas Golden Knights @ Edmonton Oilers : 2 signals (HEAT_COLD, HEAT_COLD)

## 🏀 NBA Player Heat (0 HOT / 1 COLD)
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
- **NBA**: n=100 games · hit rate 61.0% · bias +4.8pp
- **NHL**: n=93 games · hit rate 51.6% · bias +13.8pp [calibration applied]
- **MLS**: n=24 games · hit rate 50.0% · bias +8.2pp
- **EPL**: n=20 games · hit rate 55.0% · bias -24.7pp
