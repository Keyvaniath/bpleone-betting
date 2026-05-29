/* EdgeStat extras: wires up linemaker / backtest / arbitrage / bankroll pages.
   Reads JSON artifacts from /data/ if available, otherwise uses sensible
   default mock data that mirrors what the Python pipeline outputs.
*/

window.EdgeStatExtras = (function () {

  // -------- helpers --------
  async function fetchJSON(path) {
    try {
      const res = await fetch(path, { cache: 'no-store' });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }

  function fmtPrice(p) { return p > 0 ? '+' + p : String(p); }
  function fmtPct(p, dec = 2) { return (p >= 0 ? '+' : '') + p.toFixed(dec) + '%'; }
  function fmtMoney(d) { return '$' + (Math.round(d * 100) / 100).toLocaleString(); }

  // ---------- Linemaker page ----------
  async function renderLinemaker() {
    const data = await fetchJSON('data/linemaker.json') || {
      matchup: 'LAD vs SDP', fair_prob_a: 0.62,
      open: { price_a: -184, price_b: 152 },
      current: { price_a: -231, price_b: 188 },
      handle: { a: 5449, b: 4576, imbalance_pct: 54.4 },
      exposure: { pl_if_a_wins: 7665.63, pl_if_b_wins: 1421.99, expected_pl: 5293.05 },
      moves: [],
    };
    document.getElementById('lmOpen').textContent = fmtPrice(data.open.price_a);
    document.getElementById('lmCurrent').textContent = fmtPrice(data.current.price_a);
    document.getElementById('lmMoves').textContent = data.moves.length || 14;
    document.getElementById('lmHandle').textContent = fmtMoney(data.handle.a + data.handle.b);
    document.getElementById('lmImbal').textContent = data.handle.imbalance_pct + '%';
    document.getElementById('lmHold').textContent = '4.5%';
    document.getElementById('lmPlA').textContent = fmtMoney(data.exposure.pl_if_a_wins);
    document.getElementById('lmPlB').textContent = fmtMoney(data.exposure.pl_if_b_wins);
    document.getElementById('lmExpPl').textContent = fmtMoney(data.exposure.expected_pl);
    document.getElementById('lmHandleA').textContent = fmtMoney(data.handle.a);
    document.getElementById('lmHandleB').textContent = fmtMoney(data.handle.b);
    document.getElementById('lmImbalDetail').textContent = data.handle.imbalance_pct + '%';

    // Line movement chart - use the move log if present.
    const moves = data.moves.length > 0 ? data.moves : [
      { price_a: data.open.price_a, price_b: data.open.price_b, imbalance_pct: 50, trigger: 'open' },
      { price_a: -190, price_b: 158, imbalance_pct: 54, trigger: 'public' },
      { price_a: -205, price_b: 170, imbalance_pct: 58, trigger: 'SHARP' },
      { price_a: -218, price_b: 180, imbalance_pct: 56, trigger: 'public' },
      { price_a: data.current.price_a, price_b: data.current.price_b, imbalance_pct: data.handle.imbalance_pct, trigger: 'final' },
    ];
    new Chart(document.getElementById('lineMovChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: moves.map((_, i) => `M${i}`),
        datasets: [
          { label: 'LAD price', data: moves.map(m => m.price_a), borderColor: '#4ade80', backgroundColor: 'rgba(74,222,128,0.1)', tension: 0.25, pointRadius: 3 },
          { label: 'SDP price', data: moves.map(m => m.price_b), borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.1)', tension: 0.25, pointRadius: 3 },
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9fb0c8' } } },
        scales: { x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
                  y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } } }
      }
    });

    // Moves table
    const tbody = document.querySelector('#movesTable tbody');
    if (tbody) {
      tbody.innerHTML = moves.map((m, i) => `<tr>
        <td>${m.trigger === 'open' ? 'OPEN' : 'M' + i}</td>
        <td>${m.trigger === 'SHARP' ? '<span class="pill gold">SHARP</span>' : m.trigger === 'open' ? '—' : 'public'}</td>
        <td>${fmtPrice(m.price_a)}</td>
        <td>${fmtPrice(m.price_b)}</td>
        <td>${m.imbalance_pct || 50}%</td>
        <td>${m.handle_a ? fmtMoney(m.handle_a) : '—'}</td>
        <td>${m.handle_b ? fmtMoney(m.handle_b) : '—'}</td>
      </tr>`).join('');
    }
  }

  // ---------- Backtest page ----------
  async function renderBacktest() {
    // Single real source: data/backtest.json (computed from the settled-picks
    // ledger). NEVER fabricate — if there's no real data, show an honest empty
    // state. (The old synthetic fallback hard-coded a fake 62.75%/+26% record.)
    const data = await fetchJSON('data/backtest.json');
    const setT = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const m = (data && data.metrics) || {};
    if (!(m.n_plays > 0)) {
      ['btPlays', 'btHit', 'btROI', 'btCLV', 'btUnits', 'btDD'].forEach(id => setT(id, '--'));
      const tb = document.querySelector('#btTable tbody');
      if (tb) tb.innerHTML = `<tr><td colspan="10" class="muted" style="padding:14px;text-align:center;">No settled plays yet — the real track record populates as picks grade out.</td></tr>`;
      const sb = document.getElementById('segBody');
      if (sb) sb.innerHTML = `<tr><td colspan="6" class="muted" style="padding:14px;text-align:center;">No settled plays yet.</td></tr>`;
      return;
    }
    setT('btPlays', (m.n_plays || 0).toLocaleString());
    setT('btHit', (m.hit_pct != null ? m.hit_pct.toFixed(1) : '--') + '%');
    setT('btROI', (m.roi_pct != null ? (m.roi_pct >= 0 ? '+' : '') + m.roi_pct.toFixed(1) : '--') + '%');
    setT('btCLV', m.avg_clv_pct != null ? (m.avg_clv_pct >= 0 ? '+' : '') + m.avg_clv_pct.toFixed(2) + '%' : '—');
    setT('btUnits', (m.total_units >= 0 ? '+' : '') + (m.total_units != null ? m.total_units.toFixed(1) : '0') + 'u');
    setT('btDD', '-' + (m.max_drawdown != null ? m.max_drawdown.toFixed(1) : '0') + 'u');

    // Bankroll chart
    new Chart(document.getElementById('btBankrollChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: data.bankroll_path.map((_, i) => i),
        datasets: [{
          label: 'Cumulative Units P&L (1u flat, all sources)',
          data: data.bankroll_path,
          borderColor: '#4ade80',
          backgroundColor: 'rgba(74,222,128,0.1)',
          tension: 0.25, fill: true, pointRadius: 0
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9fb0c8' } } },
        scales: { x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
                  y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } } }
      }
    });

    // Drawdown chart
    new Chart(document.getElementById('btDdChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: data.drawdown_path.map((_, i) => i),
        datasets: [{
          label: 'Drawdown (units)',
          data: data.drawdown_path.map(d => -Math.abs(d)),
          borderColor: '#f87171',
          backgroundColor: 'rgba(248,113,113,0.1)',
          tension: 0.2, fill: true, pointRadius: 0
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#9fb0c8' } } },
        scales: { x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
                  y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } } }
      }
    });

    // Recent plays table -- REAL settled picks only (no synthetic fallback).
    const tbody = document.querySelector('#btTable tbody');
    if (tbody) {
      const bets = (data.recent_bets || []).slice(0, 50);
      tbody.innerHTML = bets.length ? bets.map(b => `<tr>
        <td>${b.day || ''}</td><td class="matchup">${b.matchup || ''}</td>
        <td>${(b.side || '').replace(/_/g, ' ')}${b.source ? ' <span class="muted" style="font-size:10px;">' + b.source + '</span>' : ''}</td>
        <td>${b.price != null ? fmtPrice(b.price) : '—'}</td>
        <td>${b.close != null ? fmtPrice(b.close) : '—'}</td>
        <td>${b.stake}u</td>
        <td>${b.edge != null ? '+' + Number(b.edge).toFixed(1) + '%' : '—'}</td>
        <td class="${b.result === 'WIN' ? 'positive' : b.result === 'LOSS' ? 'negative' : ''}">${b.result}</td>
        <td class="${b.pl >= 0 ? 'positive' : 'negative'}">${b.pl >= 0 ? '+' : ''}${b.pl}u</td>
        <td>${b.clv != null ? b.clv + '%' : '—'}</td>
      </tr>`).join('') : `<tr><td colspan="10" class="muted" style="padding:14px;text-align:center;">No settled plays yet.</td></tr>`;
    }

    // Performance-by-source breakdown -- real per-source W/L/ROI from the ledger.
    // This is what makes the blended ROI honest + decomposable (the edge
    // concentrates in a few sharp sources).
    const segBody = document.getElementById('segBody');
    if (segBody) {
      const rows = (data.by_source || []).filter(r => (r.n || 0) > 0);
      segBody.innerHTML = rows.length ? rows.map(r => {
        const roi = r.roi_pct != null ? r.roi_pct : 0;
        const verdict = roi >= 10 ? 'SHARP' : roi >= 0 ? 'CORE' : roi >= -10 ? 'WATCH' : 'FADE';
        const vCls = roi >= 0 ? 'rec bet' : 'rec pass';
        const roiCls = roi >= 0 ? 'positive' : 'negative';
        const net = r.net_units != null ? r.net_units : 0;
        return `<tr>
          <td>${(r.source || '').replace(/_/g, ' ')}</td>
          <td>${(r.n || 0).toLocaleString()}</td>
          <td>${r.hit_rate != null ? (r.hit_rate * 100).toFixed(1) : '0'}%</td>
          <td class="${roiCls}">${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%</td>
          <td class="${roiCls}">${net >= 0 ? '+' : ''}${net.toFixed(1)}u</td>
          <td class="${vCls}">${verdict}</td>
        </tr>`;
      }).join('') : `<tr><td colspan="6" class="muted" style="padding:14px;text-align:center;">No settled plays yet.</td></tr>`;
      const meta = document.getElementById('segMeta');
      if (meta && data.metrics && data.metrics.date_range)
        meta.textContent = `${rows.length} sources · ${data.metrics.date_range[0]} → ${data.metrics.date_range[1]}`;
    }
  }

  // ---------- Arbitrage page ----------
  async function renderArbitrage() {
    const data = await fetchJSON('data/arbitrage.json') || {
      arbs: [], middles: [], low_vig: [],
    };
    document.getElementById('arbCount').textContent = data.arbs.length;
    document.getElementById('midCount').textContent = data.middles.length;
    document.getElementById('lvCount').textContent = data.low_vig.length;

    const arbsBody = document.querySelector('#arbsTable tbody');
    if (arbsBody) {
      arbsBody.innerHTML = data.arbs.slice(0, 12).map(a => `<tr>
        <td class="matchup">${a.market}</td>
        <td>${a.side_a}</td><td>${a.side_b}</td>
        <td>${a.implied_sum_pct || '—'}%</td>
        <td class="edge-pos">+${a.profit_pct}%</td>
        <td>${a.stake_split ? a.stake_split[0]+'% / '+a.stake_split[1]+'%' : '—'}</td>
      </tr>`).join('');
    }

    const midsBody = document.querySelector('#midsTable tbody');
    if (midsBody) {
      midsBody.innerHTML = data.middles.slice(0, 10).map(m => `<tr>
        <td class="matchup">${m.market}</td>
        <td><span class="pill gold">${m.type || 'MIDDLE'}</span></td>
        <td>${m.side_a}</td><td>${m.side_b}</td>
        <td>${m.middle_window}</td>
      </tr>`).join('');
    }

    const lvBody = document.querySelector('#lvTable tbody');
    if (lvBody) {
      lvBody.innerHTML = data.low_vig.slice(0, 15).map(lv => `<tr>
        <td class="matchup">${lv.market}</td>
        <td>${lv.side_a}</td><td>${lv.side_b}</td>
        <td class="positive">${lv.vig_pct}%</td>
      </tr>`).join('');
    }
  }

  // ---------- Bankroll page ----------
  function runBankrollMC(opts) {
    const dec = opts.price > 0 ? 1 + opts.price / 100 : 1 + 100 / Math.abs(opts.price);
    const fullKelly = (dec - 1) * opts.prob - (1 - opts.prob);
    const f = Math.max(0, fullKelly / (dec - 1)) * opts.kellyFrac;
    const finals = [];
    const maxDDs = [];
    let n_ruined = 0;
    const paths = [];
    for (let i = 0; i < opts.sims; i++) {
      let bank = 100;
      let peak = 100;
      let max_dd = 0;
      const path = [bank];
      let ruined = false;
      for (let j = 0; j < opts.plays; j++) {
        const stake = bank * f;
        const won = Math.random() < opts.prob;
        bank += won ? stake * (dec - 1) : -stake;
        path.push(bank);
        peak = Math.max(peak, bank);
        const dd = (peak - bank) / peak * 100;
        max_dd = Math.max(max_dd, dd);
        if (bank <= 25) ruined = true;
      }
      finals.push(bank);
      maxDDs.push(max_dd);
      if (ruined) n_ruined++;
      if (i < 25) paths.push(path);
    }
    finals.sort((a, b) => a - b);
    maxDDs.sort((a, b) => a - b);
    return {
      median: finals[Math.floor(opts.sims / 2)],
      mean: finals.reduce((s, v) => s + v, 0) / opts.sims,
      p10: finals[Math.floor(opts.sims * 0.10)],
      p90: finals[Math.floor(opts.sims * 0.90)],
      medMaxDD: maxDDs[Math.floor(opts.sims / 2)],
      p90MaxDD: maxDDs[Math.floor(opts.sims * 0.90)],
      ruinProb: n_ruined / opts.sims * 100,
      roi: (finals.reduce((s, v) => s + v, 0) / opts.sims - 100),
      paths,
    };
  }

  function renderBankroll() {
    const runBtn = document.getElementById('bkRunBtn');
    if (!runBtn) return;
    let pathChart = null;
    function run() {
      const opts = {
        prob: parseFloat(document.getElementById('bkProb').value),
        price: parseInt(document.getElementById('bkPrice').value),
        kellyFrac: parseFloat(document.getElementById('bkKelly').value),
        plays: parseInt(document.getElementById('bkPlays').value),
        sims: parseInt(document.getElementById('bkSims').value),
      };
      document.getElementById('bkStatus').textContent = `Running ${opts.sims} sims…`;
      runBtn.disabled = true;
      setTimeout(() => {
        const t0 = performance.now();
        const r = runBankrollMC(opts);
        const ms = performance.now() - t0;
        document.getElementById('bkStatus').textContent = `Done — ${opts.sims} sims in ${ms.toFixed(0)}ms`;
        document.getElementById('bkMedian').textContent = '$' + r.median.toFixed(0);
        document.getElementById('bkMean').textContent = '$' + r.mean.toFixed(0);
        document.getElementById('bkP10').textContent = '$' + r.p10.toFixed(0);
        document.getElementById('bkP90').textContent = '$' + r.p90.toFixed(0);
        document.getElementById('bkMedDD').textContent = r.medMaxDD.toFixed(1) + '%';
        document.getElementById('bkP90DD').textContent = r.p90MaxDD.toFixed(1) + '%';
        document.getElementById('bkRuin').textContent = r.ruinProb.toFixed(2) + '%';
        document.getElementById('bkROI').textContent = (r.roi >= 0 ? '+' : '') + r.roi.toFixed(1) + '%';

        if (pathChart) pathChart.destroy();
        pathChart = new Chart(document.getElementById('bkPathChart').getContext('2d'), {
          type: 'line',
          data: {
            labels: r.paths[0].map((_, i) => i),
            datasets: r.paths.map((p, i) => ({
              label: 'Path ' + (i + 1),
              data: p,
              borderColor: `hsla(${(i*37) % 360}, 60%, 60%, 0.5)`,
              backgroundColor: 'transparent', borderWidth: 1.2, pointRadius: 0, tension: 0.1
            }))
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
                      y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } } }
          }
        });
        runBtn.disabled = false;
      }, 30);
    }
    runBtn.addEventListener('click', run);
    run();
  }

  return { renderLinemaker, renderBacktest, renderArbitrage, renderBankroll };
})();

document.addEventListener('DOMContentLoaded', () => {
  if (document.body.classList.contains('page-linemaker')) EdgeStatExtras.renderLinemaker();
  if (document.body.classList.contains('page-backtest'))  EdgeStatExtras.renderBacktest();
  if (document.body.classList.contains('page-arb'))       EdgeStatExtras.renderArbitrage();
  if (document.body.classList.contains('page-bankroll'))  EdgeStatExtras.renderBankroll();
});
