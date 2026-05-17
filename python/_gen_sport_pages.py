"""One-shot generator: builds an HTML page per ESPN team sport.
Not part of the daily pipeline. Run once after adding/removing sports."""
import os

TEAM_SPORTS = [
    ("wnba",  "WNBA",  "Women's NBA",              "#fa6e21", "🏀"),
    ("mls",   "MLS",   "Major League Soccer",       "#2da748", "⚽"),
    ("epl",   "EPL",   "English Premier League",   "#37003c", "⚽"),
    ("ucl",   "UCL",   "UEFA Champions League",    "#0a247a", "🏆"),
    ("nfl",   "NFL",   "National Football League", "#013369", "🏈"),
    ("ncaaf", "NCAAF", "NCAA Football",            "#bf5700", "🏈"),
    ("ncaab", "NCAAB", "NCAA Mens Basketball",     "#13294b", "🏀"),
    ("cws",   "CWS",   "NCAA Baseball / CWS",      "#cc0033", "⚾"),
]

TPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__LABEL__ Desk | EdgeStat</title>
<link rel="stylesheet" href="css/style.css">
<style>
  .sb-row { display:grid; grid-template-columns: 1.6fr 110px 70px 80px 80px 80px 90px; gap:12px; padding:12px 14px; border-bottom:1px solid rgba(255,255,255,0.04); font-family:'JetBrains Mono',monospace; font-size:12px; align-items:center; }
  .sb-row.head { background:rgba(255,255,255,0.04); color:var(--muted,#888); font-size:10px; text-transform:uppercase; }
  .sb-row.live { background:rgba(212,160,74,0.08); border-left:2px solid #d4a04a; }
  .sb-row.final { opacity:0.65; }
  .pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:10px; font-weight:700; text-transform:uppercase; }
  .pill.live { background:rgba(212,160,74,0.2); color:#d4a04a; }
  .pill.final { background:rgba(150,150,150,0.15); color:#aaa; }
  .pill.sched { background:rgba(80,150,220,0.15); color:#5096dc; }
</style>
</head>
<body class="page-__SPORT__">
<header class="topbar">
  <div class="brand">
    <a href="index.html" class="logo"><span class="logo-mark">⟁</span><span class="logo-text">Edge<span class="accent">Stat</span></span></a>
    <span class="tagline">by bpleone</span>
  </div>
  <nav class="mainnav">
    <a href="index.html">Dashboard</a>
    <a href="live-now.html">Live Now</a>
    <a href="mlb.html">MLB</a>
    <a href="nba.html">NBA</a>
    <a href="nhl.html">NHL</a>
    <a href="nfl.html">NFL</a>
    <a href="wnba.html">WNBA</a>
    <a href="mls.html">MLS</a>
    <a href="epl.html">EPL</a>
    <a href="ucl.html">UCL</a>
    <a href="ncaaf.html">NCAAF</a>
    <a href="ncaab.html">NCAAB</a>
    <a href="cws.html">CWS</a>
    <a href="f1.html">F1</a>
    <a href="ufc.html">UFC</a>
    <a href="best-bets.html">Best Bets</a>
  </nav>
  <div class="topbar-actions"><div class="ticker">LIVE</div></div>
</header>
<main class="container">
  <section class="page-head">
    <h1 id="sb_title">__LABEL__ Desk — Loading…</h1>
    <p id="sb_status" class="muted">Pulling live ESPN scoreboard…</p>
  </section>
  <section class="metric-strip">
    <div class="metric"><span class="metric-num" id="m_games">--</span><span class="metric-label">Games Today</span></div>
    <div class="metric"><span class="metric-num" id="m_live">--</span><span class="metric-label">In Progress</span></div>
    <div class="metric"><span class="metric-num" id="m_final">--</span><span class="metric-label">Final</span></div>
    <div class="metric"><span class="metric-num" id="m_season">--</span><span class="metric-label">Season</span></div>
  </section>
  <section class="card" style="margin-bottom: 24px; border-left: 3px solid __COLOR__;">
    <div class="card-head"><span>__EMOJI__ <strong>__LABEL__ Board</strong></span><span class="muted" id="sb_meta">--</span></div>
    <p class="muted" style="font-size: 11px; padding: 8px 16px 0;">Win probability derived from synthetic ELO of season win-pct + home-field adjustment. Score-aware live update when state is in-progress.</p>
    <div class="sb-row head">
      <span>Matchup</span><span>Records</span><span>Score</span><span>P(home)</span><span>Home Fair</span><span>Away Fair</span><span>Status</span>
    </div>
    <div id="sb_list"><p class="muted" style="padding:14px;">Loading…</p></div>
  </section>
</main>
<script src="js/nav_badge.js"></script>
<script src="js/bet_tracker.js"></script>
<script>
const fmtAmer = (a) => a == null ? "—" : (a >= 0 ? "+" + a : String(a));
fetch("data/__SPORT___state.json?t=" + Date.now(), { cache: "no-cache" })
  .then(r => r.json())
  .then(d => {
    const setText = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };
    setText("sb_title", `__LABEL__ — ${(d.season_status || 'Season').toUpperCase()}`);
    setText("sb_status", d.note || (d.n_games_today === 0 ? "No games today." : `${d.n_games_today} game(s).`));
    const games = d.games || [];
    setText("m_games", d.n_games_today || 0);
    setText("m_live", games.filter(g => g.state === 'in').length);
    setText("m_final", games.filter(g => g.state === 'post').length);
    setText("m_season", (d.season_status || '—').toUpperCase());
    if (!games.length) { document.getElementById("sb_list").innerHTML = '<p class="muted" style="padding:14px;">No games scheduled.</p>'; return; }
    document.getElementById("sb_list").innerHTML = games.map(g => {
      const cls = g.state === 'in' ? 'live' : g.state === 'post' ? 'final' : '';
      const pillCls = g.state === 'in' ? 'live' : g.state === 'post' ? 'final' : 'sched';
      const scoreText = g.state === 'pre' ? '—' : `${g.away_score ?? '?'}-${g.home_score ?? '?'}`;
      const betKey = `__UPPER__|${g.home_team}|ML|${g.fair_home_american}`;
      return `<div class="sb-row ${cls}" data-bet-key="${betKey}" data-bet-label="${g.home_team} ML vs ${g.away_team}" data-bet-play="ML" data-bet-src="__UPPER__">
        <span><strong>${g.matchup}</strong></span>
        <span class="muted" style="font-size:10px;">${g.away_record} / ${g.home_record}</span>
        <span style="font-weight:700;">${scoreText}</span>
        <span style="color:${g.p_home_win >= 0.6 ? '#58c878' : g.p_home_win <= 0.4 ? '#e35a5a' : 'var(--text-2,#aaa)'}; font-weight:700;">${(g.p_home_win * 100).toFixed(1)}%</span>
        <span>${fmtAmer(g.fair_home_american)}</span>
        <span>${fmtAmer(g.fair_away_american)}</span>
        <span class="pill ${pillCls}">${g.status || g.state || '—'}</span>
      </div>`;
    }).join("");
    document.getElementById("sb_meta").textContent = `${games.length} games · refresh: ${(d.generated_at || '').replace('T',' ')} UTC`;
  })
  .catch(err => {
    document.getElementById("sb_list").innerHTML = `<p class="muted" style="padding:14px;">Could not load __SPORT___state.json (${err.message}).</p>`;
  });
setInterval(() => location.reload(), 5 * 60 * 1000);
</script>
</body>
</html>
"""

out_dir = os.path.join(os.path.dirname(__file__), "..")
for sport_key, abbr, label, color, emoji in TEAM_SPORTS:
    html = (TPL.replace("__SPORT__", sport_key)
                .replace("__LABEL__", label)
                .replace("__COLOR__", color)
                .replace("__EMOJI__", emoji)
                .replace("__UPPER__", abbr))
    out_path = os.path.join(out_dir, f"{sport_key}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_path}")
