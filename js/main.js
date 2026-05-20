/* EdgeStat main entry point. Renders pages, fills tables, animates ticker. */

(function() {

  // ---- Live ticker (reads today.json + all_picks_ledger.json for REAL settled picks) ----
  function startTicker() {
    const el = document.getElementById('liveTicker');
    if (!el) return;
    el.textContent = '\u{1F7E2} LIVE - connecting feeds...';

    Promise.all([
      fetch('data/today.json', { cache: 'no-cache' }).then(r => r.json()).catch(() => ({})),
      fetch('data/all_picks_ledger.json', { cache: 'no-cache' }).then(r => r.json()).catch(() => ({})),
    ]).then(([today, ledger]) => {
      const lines = [];
      const pod = today.play_of_day;
      if (pod) {
        lines.push(`\u{1F7E2} LIVE - ${pod.matchup} ${pod.label} - model ${(pod.model_prob*100).toFixed(1)}%`);
      }
      (today.games || []).forEach(g => {
        const top = (g.recommendations || []).sort((a,b) => (b.edge_pct||0) - (a.edge_pct||0))[0];
        if (top) {
          const rawEdge = Number(top.edge_pct) || 0;
          const isPreCal = rawEdge >= 15;
          const tag = isPreCal ? 'CALIBRATING' : 'EDGE';
          const edgeStr = isPreCal ? '+25%+' : '+' + rawEdge.toFixed(1) + '%';
          lines.push(`\u{1F4CA} ${tag} - ${g.matchup} ${top.label} ${edgeStr}`);
        }
      });
      // REAL settled records from unified ledger (no 118k synthetic backfill)
      const settled = ((ledger.picks || []).filter(p => p.settled)).slice(-5);
      settled.forEach(p => {
        const tag = p.result === 'won' ? 'WON' : p.result === 'lost' ? 'LOST' : p.result.toUpperCase();
        const emoji = p.result === 'won' ? '\u{2705}' : p.result === 'lost' ? '\u{274C}' : '\u{1F9FE}';
        lines.push(`${emoji} SETTLED - ${p.player_or_matchup} ${p.market} - ${tag}`);
      });
      if (!lines.length) lines.push('\u{1F7E2} LIVE - no slate data yet');
      let i = 0;
      el.textContent = lines[0];
      setInterval(() => {
        i = (i+1) % lines.length;
        el.style.opacity = '0';
        setTimeout(() => { el.textContent = lines[i]; el.style.opacity = '1'; }, 200);
      }, 3500);
    }).catch(() => {
      el.textContent = '\u{1F7E2} LIVE - data feed unavailable';
    });
  }

  // ---- Last refresh stamp ----
  function setRefreshStamp() {
    const el = document.getElementById('lastRefresh');
    if (!el) return;
    const now = new Date();
    const fmt = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    el.textContent = fmt;
  }

  // ---- Slate table renderer ----
  // window.SLATE is now EMPTY by default (was full of mock data). Real
  // slate loaded into the same DOM via today.json fetch elsewhere; this
  // function gracefully no-ops if seed is empty.
  function renderSlate() {
    const tbody = document.querySelector('#slateTable tbody');
    if (!tbody) return;
    if (!window.SLATE || window.SLATE.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="muted" style="padding:14px; text-align:center;">Slate loads from data/today.json -- see MLB page or Tonight view for the live slate.</td></tr>`;
      return;
    }
    const html = window.SLATE.map(g => {
      const recClass = g.rec === 'BET' || g.rec === 'PLAY OF DAY' ? 'bet' : g.rec === 'LEAN' ? 'lean' : 'pass';
      const edgeSign = g.edge.value >= 0 ? '+' : '';
      const teamA = window.MLB_TEAMS[g.away]?.name || g.away;
      const teamH = window.MLB_TEAMS[g.home]?.name || g.home;
      return `<tr>
        <td>${g.time}</td>
        <td class="matchup">${teamA} @ ${teamH}</td>
        <td>${g.starters.join(' / ')}</td>
        <td>${fmtML(g.modelML.away)} / ${fmtML(g.modelML.home)}</td>
        <td>${fmtML(g.marketML.away)} / ${fmtML(g.marketML.home)}</td>
        <td class="edge-pos">${edgeSign}${g.edge.value.toFixed(1)}% ${g.edge.side}</td>
        <td>${g.modelTotal.toFixed(1)}</td>
        <td>${g.marketTotal.toFixed(1)}</td>
        <td class="rec ${recClass}">${g.rec}</td>
      </tr>`;
    }).join('');
    tbody.innerHTML = html;
  }
  function fmtML(v) { return v > 0 ? '+' + v : String(v); }

  // ---- Newsletter (mock) ----
  window.subscribe = function(form) {
    const msg = document.getElementById('subMsg');
    if (msg) msg.textContent = '✓ Subscribed. Check your inbox in the morning.';
    form.reset();
  };

  // ---- Run on load ----
  document.addEventListener('DOMContentLoaded', () => {
    startTicker();
    setRefreshStamp();

    // Charts (dashboard page)
    const hero = document.getElementById('heroChart');
    if (hero) EdgeStatCharts.renderHeroChart(hero.getContext('2d'));
    const mm = document.getElementById('modelMarketChart');
    if (mm) EdgeStatCharts.renderModelMarket(mm.getContext('2d'));
    const clv = document.getElementById('clvChart');
    if (clv) EdgeStatCharts.renderCLV(clv.getContext('2d'));
    const hit = document.getElementById('hitChart');
    if (hit) EdgeStatCharts.renderHitRate(hit.getContext('2d'));

    // Slate table
    renderSlate();

    // Play of the day page renderer
    if (document.body.classList.contains('page-play')) renderPlayPage();

    // MLB page renderer
    if (document.body.classList.contains('page-mlb')) renderMLBPage();

    // Models page renderer
    if (document.body.classList.contains('page-models')) renderModelsPage();

    // Trends page renderer
    if (document.body.classList.contains('page-trends')) renderTrendsPage();

    // Props page
    if (document.body.classList.contains('page-props')) renderPropsPage();

    // Track record page
    if (document.body.classList.contains('page-track')) renderTrackPage();
  });

  // ---- Play of the Day deep-dive renderer ----
  // Guarded against null seed -- real factor decomp loads from
  // data/pod_factor_decomp.json elsewhere, hero stats from today.json.
  function renderPlayPage() {
    // Real confidence gauge + run distribution from today.json (was hardcoded 3.6 / 4.0 lambdas)
    fetch('data/today.json', { cache: 'no-cache' })
      .then(r => r.json())
      .then(d => {
        const pod = d.play_of_day || {};
        const podGame = (d.games || []).find(g => g.matchup === pod.matchup);
        if (!podGame) return;
        const model = podGame.model || {};
        const T = model.fair_total || 8.5;
        const P = model.p_home_win || 0.5;
        const D = T * (P - 0.5) * 1.6;
        const home_lam = Math.max(1.5, (T + D) / 2);
        const away_lam = Math.max(1.5, (T - D) / 2);
        const conf = document.getElementById('confDonut');
        if (conf) EdgeStatCharts.renderConfidenceGauge(conf.getContext('2d'), Math.round((pod.model_prob || 0)*100));
        const dist = document.getElementById('runDistChart');
        if (dist) EdgeStatCharts.renderRunDistribution(dist.getContext('2d'), away_lam, home_lam);
      })
      .catch(() => {});

    const p = window.PLAY_OF_DAY;
    if (!p) return;   // No seed; real loaders above already painted real charts

    // factors bars
    const factorsHost = document.getElementById('factorBars');
    if (factorsHost) {
      const max = Math.max(...p.factors.map(f => Math.abs(parseFloat(f.value))));
      factorsHost.innerHTML = p.factors.map(f => {
        const v = parseFloat(f.value);
        const pct = Math.min(100, Math.abs(v)/max*100);
        const cls = v >= 0 ? 'pos' : 'neg';
        return `<div class="bar-row">
          <span class="bar-label">${f.name}</span>
          <span class="bar-track"><span class="bar-fill ${cls}" style="width:${pct}%; background:${v>=0?'linear-gradient(90deg,#4ade80,#22d3ee)':'linear-gradient(90deg,#f87171,#fbbf24)'}"></span></span>
          <span class="bar-val ${v>=0?'positive':'negative'}">${v>=0?'+':''}${v.toFixed(3)}</span>
        </div>`;
      }).join('');
    }
  }

  // ---- MLB page ----
  function renderMLBPage() {
    renderSlate();
    const propEdges = document.getElementById('propEdgesChart');
    if (propEdges) EdgeStatCharts.renderPropEdges(propEdges.getContext('2d'));

    const trendStreak = document.getElementById('trendStreakChart');
    if (trendStreak) EdgeStatCharts.renderTrendStreak(trendStreak.getContext('2d'));

    // Team trends table
    const tbody = document.querySelector('#trendsTable tbody');
    if (tbody) {
      tbody.innerHTML = window.TEAM_TRENDS.map(t => `<tr>
        <td class="matchup">${t.team}</td>
        <td>${t.ats}</td>
        <td>${t.ou}</td>
        <td>${t.last10}</td>
        <td>${t.runDiff}</td>
        <td class="${t.streak.startsWith('W')?'positive':'negative'}">${t.streak}</td>
      </tr>`).join('');
    }
  }

  // ---- Models page ----
  function renderModelsPage() {
    const bk = document.getElementById('bankrollChart');
    if (bk) EdgeStatCharts.renderBankroll(bk.getContext('2d'));

    // Live Kelly calculator
    const recalc = () => {
      const p = parseFloat(document.getElementById('calcProb').value)/100;
      const price = parseInt(document.getElementById('calcPrice').value);
      const bk = parseFloat(document.getElementById('calcBankroll').value);
      const frac = parseFloat(document.getElementById('calcFrac').value);
      const ev = EdgeStat.expectedValue(p, price);
      const kelly = EdgeStat.kellyStake(p, price, frac, 100);
      const dollars = bk * (kelly/100);
      document.getElementById('calcEV').textContent = (ev*100).toFixed(2) + '%';
      document.getElementById('calcEV').className = ev > 0 ? 'positive' : 'negative';
      document.getElementById('calcKelly').textContent = kelly.toFixed(2) + '%';
      document.getElementById('calcDollars').textContent = '$' + dollars.toFixed(2);
      document.getElementById('calcDecimal').textContent = EdgeStat.americanToDecimal(price).toFixed(3);
      document.getElementById('calcImplied').textContent = (EdgeStat.americanToImplied(price)*100).toFixed(2) + '%';
      document.getElementById('calcFair').textContent = EdgeStat.probToAmerican(p);
    };
    ['calcProb','calcPrice','calcBankroll','calcFrac'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', recalc);
    });
    if (document.getElementById('calcProb')) recalc();
  }

  // ---- Trends page ----
  // SHARP_FLOW + TEAM_TRENDS are now empty by default; live data loaded
  // via fetch elsewhere. Render empty state if no seed.
  function renderTrendsPage() {
    const flow = document.querySelector('#flowTable tbody');
    if (flow) {
      if (!window.SHARP_FLOW || window.SHARP_FLOW.length === 0) {
        flow.innerHTML = '<tr><td colspan="6" class="muted" style="padding:14px; text-align:center;">Sharp money flow loads from data/sharp_action_radar.json — visit /tonight for live signals.</td></tr>';
      } else {
        flow.innerHTML = window.SHARP_FLOW.map(f => `<tr>
          <td class="matchup">${f.ticket}</td>
          <td class="${f.handle.startsWith('+')?'positive':'negative'}">${f.handle}</td>
          <td>${f.tickets}</td>
          <td>${f.open}</td>
          <td>${f.current}</td>
          <td>${f.steam ? '<span class="pill green">STEAM</span>' : '<span class="muted">—</span>'}</td>
        </tr>`).join('');
      }
    }
    const trendStreak = document.getElementById('trendStreakChart');
    if (trendStreak) EdgeStatCharts.renderTrendStreak(trendStreak.getContext('2d'));

    const tbody = document.querySelector('#trendsTable tbody');
    if (tbody) {
      if (!window.TEAM_TRENDS || window.TEAM_TRENDS.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="muted" style="padding:14px; text-align:center;">Team trends load from historical_*.json after the daily pipeline accumulates a season of data.</td></tr>';
      } else {
        tbody.innerHTML = window.TEAM_TRENDS.map(t => `<tr>
          <td class="matchup">${t.team}</td>
          <td>${t.ats}</td>
          <td>${t.ou}</td>
          <td>${t.last10}</td>
          <td>${t.runDiff}</td>
          <td class="${t.streak.startsWith('W')?'positive':'negative'}">${t.streak}</td>
        </tr>`).join('');
      }
    }
  }

  // ---- Props page ----
  // Live props come from real_player_props_mlb.json -- the seed PROP_PICKS
  // is empty by default. Real loader is elsewhere.
  function renderPropsPage() {
    const tbody = document.querySelector('#propsTable tbody');
    if (tbody) {
      if (!window.PROP_PICKS || window.PROP_PICKS.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="muted" style="padding:14px; text-align:center;">Player props load from real_player_props_mlb.json — see /tonight for tonight\'s top picks.</td></tr>';
      } else {
        tbody.innerHTML = window.PROP_PICKS.map(p => `<tr>
          <td class="matchup">${p.player}</td>
          <td>${p.team}</td>
          <td>${p.prop}</td>
          <td>${typeof p.market === 'number' ? (p.market>0?'+':'')+p.market : p.market}</td>
          <td>${typeof p.model === 'number' ? (p.model>0?'+':'')+p.model : p.model}</td>
          <td class="edge-pos">+${p.edge.toFixed(1)}%</td>
          <td><span class="pill green">${p.type}</span></td>
        </tr>`).join('');
      }
    }
    const pe = document.getElementById('propEdgesChart');
    if (pe) EdgeStatCharts.renderPropEdges(pe.getContext('2d'));
  }

  // ---- Track record page ----
  // Real data overlay in track-record.html reads pod_pl.json. The seed
  // TRACK_RECORD here is empty by default -- legacy renderer no-ops.
  function renderTrackPage() {
    const tbody = document.querySelector('#trackTable tbody');
    if (tbody && (!window.TRACK_RECORD || window.TRACK_RECORD.length === 0)) {
      // The dedicated overlay in track-record.html populates from pod_pl.json
      // so we don't need to render a fake seed row here.
      return;
    }
    if (tbody) {
      tbody.innerHTML = window.TRACK_RECORD.map(t => `<tr>
        <td>${t.date}</td>
        <td class="matchup">${t.play}</td>
        <td>${t.price}</td>
        <td>${t.stake}</td>
        <td class="${t.result==='WIN'?'positive':'negative'}">${t.result}</td>
        <td class="${t.pl.startsWith('+')?'positive':'negative'}">${t.pl}</td>
        <td>${t.clv}</td>
      </tr>`).join('');
    }

    // P&L line chart
    const ctxEl = document.getElementById('plChart');
    if (ctxEl && window.TRACK_RECORD && window.TRACK_RECORD.length > 0) {
      let cum = 0;
      const data = [...window.TRACK_RECORD].reverse().map(t => {
        cum += parseFloat(t.pl);
        return cum;
      });
      new Chart(ctxEl.getContext('2d'), {
        type: 'line',
        data: {
          labels: data.map((_,i) => 'P' + (i+1)),
          datasets: [{
            label: 'Cumulative P&L (units)',
            data, borderColor: '#4ade80',
            backgroundColor: 'rgba(74,222,128,0.1)',
            tension: 0.25, fill: true, pointRadius: 0
          }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { labels: { color: '#9fb0c8' } } },
          scales: {
            x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
            y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } }
          }
        }
      });
    }
  }

})();
