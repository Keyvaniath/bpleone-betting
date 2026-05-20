/* EdgeStat data layer.
   PRODUCTION MODE: all seed arrays are EMPTY. Pages must fetch real data
   from data/*.json (today.json, matchups.json, props.json, etc).

   Previously this file contained 200+ lines of mock data (hardcoded
   Yamamoto/Darvish pitching matchup, fake Aaron Judge props, fake
   "Yankees -1.5 +78% handle" sharp flow, fake "Dodgers 21-9 ATS" team
   trends, etc) that leaked into the dashboard whenever real data
   wasn't loaded. Replaced with empty stubs so any seed-driven UI
   renders "no data" honestly instead of showing 2024-vintage demo
   players as tonight's slate.

   Real data flow:
     window.SLATE         <-  data/today.json (games + recommendations)
     window.PLAY_OF_DAY   <-  data/today.json.play_of_day
     window.PROP_PICKS    <-  data/real_player_props_mlb.json
     window.SHARP_FLOW    <-  data/sharp_action_radar.json + steam_alerts.json
     window.TEAM_TRENDS   <-  data/historical_*.json rollup
     window.HIT_RATES     <-  data/all_picks_ledger.json by_market
     window.TRACK_RECORD  <-  data/pod_pl.json.history
*/

window.MLB_TEAMS = {
  // Park factors kept as static reference data (these don't change night-to-night)
  LAD: { name: 'Dodgers', city: 'Los Angeles', park: 'Dodger Stadium', parkFactor: 0.96 },
  SDP: { name: 'Padres', city: 'San Diego', park: 'Petco Park', parkFactor: 0.91 },
  NYY: { name: 'Yankees', city: 'New York', park: 'Yankee Stadium', parkFactor: 1.08 },
  BOS: { name: 'Red Sox', city: 'Boston', park: 'Fenway Park', parkFactor: 1.05 },
  ATL: { name: 'Braves', city: 'Atlanta', park: 'Truist Park', parkFactor: 1.02 },
  PHI: { name: 'Phillies', city: 'Philadelphia', park: 'Citizens Bank Park', parkFactor: 1.06 },
  HOU: { name: 'Astros', city: 'Houston', park: 'Minute Maid', parkFactor: 1.01 },
  TEX: { name: 'Rangers', city: 'Texas', park: 'Globe Life', parkFactor: 1.04 },
  NYM: { name: 'Mets', city: 'New York', park: 'Citi Field', parkFactor: 0.95 },
  CHC: { name: 'Cubs', city: 'Chicago', park: 'Wrigley', parkFactor: 1.00 },
  WSH: { name: 'Nationals', city: 'Washington', park: 'Nationals Park', parkFactor: 0.99 },
  TOR: { name: 'Blue Jays', city: 'Toronto', park: 'Rogers Centre', parkFactor: 1.03 },
  TBR: { name: 'Rays', city: 'Tampa Bay', park: 'Tropicana', parkFactor: 0.93 },
  SFG: { name: 'Giants', city: 'San Francisco', park: 'Oracle Park', parkFactor: 0.94 },
  STL: { name: 'Cardinals', city: 'St. Louis', park: 'Busch Stadium', parkFactor: 0.97 },
  ARI: { name: 'Diamondbacks', city: 'Arizona', park: 'Chase Field', parkFactor: 1.02 },
  KCR: { name: 'Royals', city: 'Kansas City', park: 'Kauffman', parkFactor: 1.00 },
  COL: { name: 'Rockies', city: 'Colorado', park: 'Coors Field', parkFactor: 1.18 },
  DET: { name: 'Tigers', city: 'Detroit', park: 'Comerica Park', parkFactor: 0.95 },
  CHW: { name: 'White Sox', city: 'Chicago', park: 'Guaranteed Rate', parkFactor: 1.02 },
  SEA: { name: 'Mariners', city: 'Seattle', park: 'T-Mobile', parkFactor: 0.92 },
  ATH: { name: 'Athletics', city: 'Athletics', park: 'Sutter Health', parkFactor: 1.00 },
  LAA: { name: 'Angels', city: 'Los Angeles', park: 'Angel Stadium', parkFactor: 0.97 },
  CIN: { name: 'Reds', city: 'Cincinnati', park: 'Great American', parkFactor: 1.10 },
  PIT: { name: 'Pirates', city: 'Pittsburgh', park: 'PNC Park', parkFactor: 0.97 },
  MIL: { name: 'Brewers', city: 'Milwaukee', park: 'American Family', parkFactor: 1.00 },
  CLE: { name: 'Guardians', city: 'Cleveland', park: 'Progressive Field', parkFactor: 0.98 },
  MIN: { name: 'Twins', city: 'Minnesota', park: 'Target Field', parkFactor: 0.99 },
  MIA: { name: 'Marlins', city: 'Miami', park: 'loanDepot Park', parkFactor: 0.90 },
  BAL: { name: 'Orioles', city: 'Baltimore', park: 'Camden Yards', parkFactor: 1.04 },
};

// ALL OF THE BELOW ARE EMPTY -- pages must fetch from data/*.json
window.SLATE = [];          // populated from data/today.json by main.js
window.PLAY_OF_DAY = null;   // populated from data/today.json.play_of_day
window.MODEL_HISTORY = [];  // populated from data/all_picks_ledger.json
window.HIT_RATES = [];       // populated from data/all_picks_ledger.json by_market
window.SHARP_FLOW = [];      // populated from data/sharp_action_radar.json
window.PROP_PICKS = [];      // populated from data/real_player_props_mlb.json
window.TEAM_TRENDS = [];     // populated from data/historical_*.json rollup
window.TRACK_RECORD = [];    // populated from data/pod_pl.json.history
window.MARKETS = ['DraftKings','FanDuel','BetMGM','Caesars','Pinnacle','ESPN BET'];
