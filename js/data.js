/* EdgeStat data layer.
   In production, replace these with calls to a real MLB feed (MLB StatsAPI, Sportradar,
   or your own scraping pipeline) and the major book odds APIs (the-odds-api, OddsJam, etc).
   The shape of the objects below is what the rest of the frontend expects.
*/

window.MLB_TEAMS = {
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
  SFG: { name: 'Giants', city: 'San Francisco', park: 'Oracle Park', parkFactor: 0.89 },
  ARI: { name: 'D-backs', city: 'Arizona', park: 'Chase Field', parkFactor: 1.02 },
  STL: { name: 'Cardinals', city: 'St. Louis', park: 'Busch', parkFactor: 0.98 },
  CIN: { name: 'Reds', city: 'Cincinnati', park: 'Great American', parkFactor: 1.12 },
  COL: { name: 'Rockies', city: 'Colorado', park: 'Coors Field', parkFactor: 1.20 },
};

// Today's slate (May 13, 2026). Sample is a realistic 8-game slate with
// model output, market price, and recommendation.
window.SLATE = [
  {
    time: '6:40p ET', away: 'NYM', home: 'PHI',
    starters: ['Senga', 'Wheeler'],
    modelML: { away: +148, home: -174 },
    marketML: { away: +124, home: -142 },
    modelTotal: 8.4, marketTotal: 8.5,
    edge: { side: 'PHI ML', value: 4.2 },
    rec: 'BET'
  },
  {
    time: '6:45p ET', away: 'BOS', home: 'NYY',
    starters: ['Crochet', 'Cole'],
    modelML: { away: +122, home: -138 },
    marketML: { away: +115, home: -128 },
    modelTotal: 8.7, marketTotal: 9.0,
    edge: { side: 'UNDER 9.0', value: 3.8 },
    rec: 'BET'
  },
  {
    time: '7:05p ET', away: 'SDP', home: 'LAD',
    starters: ['Darvish', 'Yamamoto'],
    modelML: { away: +178, home: -210 },
    marketML: { away: +138, home: -158 },
    modelTotal: 7.6, marketTotal: 8.0,
    edge: { side: 'LAD ML', value: 5.4 },
    rec: 'PLAY OF DAY'
  },
  {
    time: '7:10p ET', away: 'TOR', home: 'TBR',
    starters: ['Berríos', 'McClanahan'],
    modelML: { away: -106, home: +102 },
    marketML: { away: -118, home: +108 },
    modelTotal: 7.8, marketTotal: 8.0,
    edge: { side: 'TBR ML', value: 2.9 },
    rec: 'LEAN'
  },
  {
    time: '7:20p ET', away: 'CHC', home: 'WSH',
    starters: ['Imanaga', 'Gore'],
    modelML: { away: -132, home: +118 },
    marketML: { away: -126, home: +112 },
    modelTotal: 8.2, marketTotal: 8.5,
    edge: { side: 'UNDER 8.5', value: 2.6 },
    rec: 'LEAN'
  },
  {
    time: '8:10p ET', away: 'ATL', home: 'STL',
    starters: ['Strider', 'Pallante'],
    modelML: { away: -176, home: +160 },
    marketML: { away: -148, home: +132 },
    modelTotal: 8.6, marketTotal: 8.5,
    edge: { side: 'ATL ML', value: 4.0 },
    rec: 'BET'
  },
  {
    time: '8:15p ET', away: 'TEX', home: 'HOU',
    starters: ['deGrom', 'Valdez'],
    modelML: { away: +106, home: -114 },
    marketML: { away: +102, home: -108 },
    modelTotal: 7.4, marketTotal: 7.5,
    edge: { side: 'UNDER 7.5', value: 1.4 },
    rec: 'PASS'
  },
  {
    time: '9:40p ET', away: 'CIN', home: 'COL',
    starters: ['Greene', 'Freeland'],
    modelML: { away: -120, home: +110 },
    marketML: { away: -110, home: +100 },
    modelTotal: 11.6, marketTotal: 10.5,
    edge: { side: 'OVER 10.5', value: 6.1 },
    rec: 'BET'
  },
];

// Play of the Day deep data
window.PLAY_OF_DAY = {
  date: 'May 13, 2026',
  matchup: 'Los Angeles Dodgers @ San Diego Padres',
  side: 'Dodgers Moneyline',
  modelPrice: -178,
  marketPrice: -148,
  edge: 5.4,
  winProb: 0.640,
  marketImplied: 0.597,
  kelly: 1.7,
  confidence: 'High',
  expectedValue: 0.054,
  factors: [
    { name: 'Starting Pitcher (Yamamoto vs Darvish)', value: '+0.041', impact: 'Yamamoto xFIP 2.89 vs Darvish 4.12' },
    { name: 'Lineup Platoon Split', value: '+0.018', impact: 'LAD +0.067 wRC+ vs RHP, top-3 in MLB' },
    { name: 'Bullpen ERA-FIP', value: '+0.012', impact: 'LAD pen 3.41 ERA vs SDP 4.28' },
    { name: 'Park Factor', value: '-0.006', impact: 'Petco suppresses scoring 9% (HFA muted)' },
    { name: 'Weather (62°F, marine layer)', value: '-0.004', impact: 'Pitcher-friendly conditions' },
    { name: 'Umpire (Carlos Torres)', value: '+0.003', impact: 'Wide zone, helps Yamamoto K rate' },
    { name: 'Recent Form (last 14d)', value: '+0.009', impact: 'LAD +6.8 run diff vs SDP -3.2' },
    { name: 'Rest Differential', value: '0.000', impact: 'Even, both teams off yesterday' },
    { name: 'Injury Report', value: '-0.002', impact: 'Betts day-to-day; expected to play' },
    { name: 'Travel Fatigue', value: '+0.001', impact: 'Negligible, short flight' },
    { name: 'Catcher Framing', value: '+0.007', impact: 'Smith +6 runs framing vs Higashioka -2' },
    { name: 'Public/Sharp Split', value: '+0.005', impact: '64% public on SDP, 71% handle on LAD' },
  ],
  components: {
    'Run Expectancy': 5.1,
    'Win Expectancy': 0.640,
    'Bullpen Adjustment': 0.07,
    'Park-Adjusted ERA+': 118,
    'wOBA vs Pitch Type': 0.341,
  }
};

// 14-day model edge history
window.MODEL_HISTORY = [
  { day: -13, modelEdge: 1.2, clv: 0.8 },
  { day: -12, modelEdge: 2.1, clv: 1.6 },
  { day: -11, modelEdge: -0.4, clv: -0.2 },
  { day: -10, modelEdge: 3.5, clv: 2.4 },
  { day: -9, modelEdge: 1.8, clv: 1.1 },
  { day: -8, modelEdge: 2.9, clv: 2.0 },
  { day: -7, modelEdge: 4.2, clv: 3.1 },
  { day: -6, modelEdge: 1.5, clv: 0.9 },
  { day: -5, modelEdge: 2.8, clv: 1.8 },
  { day: -4, modelEdge: 3.1, clv: 2.5 },
  { day: -3, modelEdge: 2.4, clv: 1.7 },
  { day: -2, modelEdge: 4.0, clv: 3.0 },
  { day: -1, modelEdge: 3.7, clv: 2.8 },
  { day: 0,  modelEdge: 4.1, clv: 2.4 },
];

window.HIT_RATES = [
  { type: 'MLB ML', hit: 56.2 },
  { type: 'MLB Run Line', hit: 53.1 },
  { type: 'MLB Total', hit: 55.4 },
  { type: 'Player Props', hit: 59.1 },
  { type: 'First-5 Totals', hit: 54.7 },
  { type: 'NRFI/YRFI', hit: 57.8 },
];

window.SHARP_FLOW = [
  { ticket: 'YANKEES -1.5', handle: '+78%', tickets: '42%', open: '-110', current: '-105', steam: true },
  { ticket: 'BRAVES ML', handle: '+62%', tickets: '38%', open: '-152', current: '-176', steam: true },
  { ticket: 'CUBS / WSH U8.5', handle: '+54%', tickets: '47%', open: 'O8.5 -110', current: 'U8.5 -115', steam: true },
  { ticket: 'METS ML', handle: '-31%', tickets: '62%', open: '+128', current: '+148', steam: false },
  { ticket: 'ASTROS -1.5', handle: '+44%', tickets: '45%', open: '+115', current: '+108', steam: true },
  { ticket: 'DODGERS ML', handle: '+71%', tickets: '36%', open: '-138', current: '-148', steam: true },
  { ticket: 'RAYS ML', handle: '+22%', tickets: '49%', open: '+112', current: '+108', steam: false },
  { ticket: 'PHILLIES -1.5', handle: '+19%', tickets: '52%', open: '+108', current: '+104', steam: false },
];

// Player props of the day
window.PROP_PICKS = [
  { player: 'Aaron Judge', team: 'NYY', prop: 'Over 1.5 Total Bases', market: '+115', model: -110, edge: 8.4, type: 'OVER' },
  { player: 'Shohei Ohtani', team: 'LAD', prop: 'Over 0.5 HR',         market: '+260', model: +210, edge: 6.1, type: 'OVER' },
  { player: 'Yoshinobu Yamamoto', team: 'LAD', prop: 'Over 6.5 Ks',    market: '-115', model: -160, edge: 5.7, type: 'OVER' },
  { player: 'Mookie Betts', team: 'LAD', prop: 'Over 1.5 H+R+RBI',     market: '+105', model: -115, edge: 4.2, type: 'OVER' },
  { player: 'Bobby Witt Jr',team: 'KCR', prop: 'Over 1.5 Total Bases', market: '+108', model: -108, edge: 4.0, type: 'OVER' },
  { player: 'Garrett Crochet', team: 'BOS', prop: 'Over 7.5 Ks',        market: '+100', model: -120, edge: 3.6, type: 'OVER' },
  { player: 'Juan Soto',    team: 'NYM', prop: 'Over 1.5 Walks',       market: '+220', model: +180, edge: 3.4, type: 'OVER' },
  { player: 'Tarik Skubal', team: 'DET', prop: 'Over 6.5 Ks',          market: '-130', model: -170, edge: 3.1, type: 'OVER' },
];

// Team trends (last 30 days)
window.TEAM_TRENDS = [
  { team: 'Dodgers',  ats: '21-9',  ou: '18-10-2', last10: '8-2',  runDiff: '+42', streak: 'W5' },
  { team: 'Yankees',  ats: '20-12', ou: '15-15-0', last10: '7-3',  runDiff: '+31', streak: 'W2' },
  { team: 'Braves',   ats: '18-14', ou: '14-16-0', last10: '6-4',  runDiff: '+18', streak: 'W1' },
  { team: 'Phillies', ats: '19-11', ou: '17-12-1', last10: '7-3',  runDiff: '+24', streak: 'W3' },
  { team: 'Astros',   ats: '15-15', ou: '12-18-0', last10: '5-5',  runDiff: '+4',  streak: 'L1' },
  { team: 'Padres',   ats: '13-17', ou: '11-19-0', last10: '4-6',  runDiff: '-9',  streak: 'L2' },
  { team: 'Mets',     ats: '14-16', ou: '17-13-0', last10: '5-5',  runDiff: '-2',  streak: 'W1' },
  { team: 'Cubs',     ats: '17-13', ou: '13-17-0', last10: '6-4',  runDiff: '+11', streak: 'W2' },
  { team: 'Red Sox',  ats: '16-14', ou: '15-15-0', last10: '5-5',  runDiff: '+6',  streak: 'L1' },
  { team: 'Rays',     ats: '12-18', ou: '10-20-0', last10: '4-6',  runDiff: '-14', streak: 'L3' },
];

// Track record - last 30 plays
window.TRACK_RECORD = (function() {
  const rng = (s) => { let x = s; return () => { x = (x*9301+49297) % 233280; return x/233280; }; };
  const r = rng(11);
  const teams = ['LAD','NYY','ATL','PHI','HOU','BOS','SDP','NYM','CHC','WSH','TOR','TBR','SFG','STL','ARI'];
  const types = ['ML','RUN LINE -1.5','TOTAL OVER','TOTAL UNDER','F5 ML','F5 UNDER','PROP — Judge O1.5 TB','PROP — Ohtani O0.5 HR'];
  const out = [];
  for (let i = 0; i < 30; i++) {
    const winProb = 0.52 + r()*0.16;
    const won = r() < winProb;
    const price = Math.round((r()*200) - 110);
    const stake = Math.round((r()*1.8 + 0.5)*10)/10;
    const pl = won ? (price > 0 ? stake*(price/100) : stake*(100/Math.abs(price))) : -stake;
    out.push({
      date: `2026-05-${String(13-i).padStart(2,'0')}`,
      play: `${teams[Math.floor(r()*teams.length)]} ${types[Math.floor(r()*types.length)]}`,
      price: price > 0 ? '+'+price : String(price),
      stake: stake.toFixed(1) + 'u',
      result: won ? 'WIN' : 'LOSS',
      pl: (won?'+':'') + pl.toFixed(2) + 'u',
      clv: ((r()*8 - 1.5)).toFixed(1) + '%',
    });
  }
  return out;
})();

window.MARKETS = ['DraftKings','FanDuel','BetMGM','Caesars','Pinnacle','ESPN BET'];
