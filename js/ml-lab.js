/* EdgeStat - ML Lab + Live page wiring.
   Loads JSON artifacts produced by the Python training pipeline and renders
   the visualization layer on top.
*/

(function () {

  async function fetchJSON(path) {
    try {
      const r = await fetch(path, { cache: 'no-store' });
      if (!r.ok) return null;
      return await r.json();
    } catch { return null; }
  }

  function fmtPrice(p) { return p > 0 ? '+' + p : String(p); }

  // ============================================================
  // ML LAB PAGE
  // ============================================================
  async function renderMLLab() {
    // Pull artifacts (with sensible fallbacks)
    const [ensemble, nn, calib, features] = await Promise.all([
      fetchJSON('data/ensemble.json'),
      fetchJSON('data/neural_net.json'),
      fetchJSON('data/calibration.json'),
      fetchJSON('data/features.json'),
    ]);

    // ---- Ensemble meta-weights bar chart ----
    const weights = (ensemble && ensemble.base_weights) || {
      BAYESIAN: 0.25, GBM: 0.29, MC_SIM: 0.21, NN: 0.25
    };
    new Chart(document.getElementById('mlWeightsChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: Object.keys(weights),
        datasets: [{
          label: 'Weight in ensemble',
          data: Object.values(weights),
          backgroundColor: ['#4ade80', '#60a5fa', '#a78bfa', '#fbbf24'],
          borderRadius: 4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
          y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } }
        }
      }
    });

    // ---- Feature importance bar chart ----
    const featImp = (nn && nn.metrics && nn.metrics.feature_importance) || [
      { feature: 'wrc_diff', loss_delta: 0.047 },
      { feature: 'elo_diff', loss_delta: 0.027 },
      { feature: 'wind_mph', loss_delta: 0.008 },
      { feature: 'xfip_diff', loss_delta: 0.006 },
      { feature: 'form_diff', loss_delta: 0.002 },
    ];
    new Chart(document.getElementById('mlFeatChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: featImp.map(f => f.feature),
        datasets: [{
          label: 'Loss bump when feature shuffled',
          data: featImp.map(f => f.loss_delta),
          backgroundColor: featImp.map(f => f.loss_delta > 0 ? 'rgba(74,222,128,0.7)' : 'rgba(248,113,113,0.5)'),
          borderRadius: 3
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
          y: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } }
        }
      }
    });

    // ---- NN training curve ----
    const history = (nn && nn.metrics && nn.metrics.history) || [];
    if (history.length > 0) {
      new Chart(document.getElementById('mlLossChart').getContext('2d'), {
        type: 'line',
        data: {
          labels: history.map(h => 'Ep ' + h.epoch),
          datasets: [
            { label: 'Train loss', data: history.map(h => h.train_loss), borderColor: '#4ade80', backgroundColor: 'rgba(74,222,128,0.1)', tension: 0.25, pointRadius: 2, fill: true },
            { label: 'Val loss',   data: history.map(h => h.val_loss),   borderColor: '#fbbf24', backgroundColor: 'rgba(251,191,36,0.05)', tension: 0.25, pointRadius: 2, fill: false }
          ]
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

    // ---- Reliability diagram ----
    const buckets = (calib && calib.reliability) || [];
    new Chart(document.getElementById('mlReliabilityChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: buckets.map(b => b.bucket),
        datasets: [
          {
            label: 'Predicted',
            data: buckets.map(b => b.predicted),
            borderColor: '#60a5fa',
            backgroundColor: 'transparent',
            pointRadius: 4, tension: 0
          },
          {
            label: 'Observed',
            data: buckets.map(b => b.observed),
            borderColor: '#4ade80',
            backgroundColor: 'transparent',
            pointRadius: 4, tension: 0
          },
          {
            label: 'Perfect',
            data: buckets.map((_, i) => 0.05 + i * 0.1),
            borderColor: '#6a7a93',
            borderDash: [3, 3],
            pointRadius: 0, tension: 0
          }
        ]
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

    // ---- Feature vector table ----
    if (features && features.schema && features.example_game) {
      const tbody = document.querySelector('#mlFeatTable tbody');
      if (tbody) {
        const schema = features.schema;
        const vals = features.example_game.features;
        tbody.innerHTML = schema.map((s, i) => `<tr>
          <td>${i + 1}</td>
          <td class="matchup">${s.name}</td>
          <td><span class="pill blue">${s.family}</span></td>
          <td>${vals[s.name] !== undefined ? vals[s.name].toFixed(4) : '—'}</td>
          <td>${s.description}</td>
        </tr>`).join('');
      }
    }
  }

  // ============================================================
  // LIVE PAGE
  // ============================================================
  async function renderLive() {
    const data = await fetchJSON('data/live_game.json');
    if (!data) return;

    // Metric strip
    const pre = data.pregame_p_home_win || data.timeline[0].p_home_win;
    const last = data.timeline[data.timeline.length - 1].p_home_win;
    document.getElementById('liveCurrent').textContent = (last * 100).toFixed(1) + '%';
    document.getElementById('livePreGame').textContent = (pre * 100).toFixed(1) + '%';
    document.getElementById('liveSwing').textContent = ((last - pre) * 100).toFixed(1) + 'pp';
    // biggest single event by abs delta
    let biggest = 0;
    for (let i = 1; i < data.timeline.length; i++) {
      const d = Math.abs(data.timeline[i].p_home_win - data.timeline[i - 1].p_home_win);
      if (d > biggest) biggest = d;
    }
    document.getElementById('liveBigEvent').textContent = (biggest * 100).toFixed(1) + 'pp';

    // Win expectancy chart
    new Chart(document.getElementById('liveWPChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: data.timeline.map((_, i) => 'E' + i),
        datasets: [{
          label: 'P(home win)',
          data: data.timeline.map(t => (t.p_home_win * 100).toFixed(2)),
          borderColor: '#4ade80',
          backgroundColor: 'rgba(74,222,128,0.15)',
          tension: 0.2, fill: true, pointRadius: 3, pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#9fb0c8' } },
          tooltip: {
            callbacks: {
              afterLabel: (ctx) => data.timeline[ctx.dataIndex].event
            }
          }
        },
        scales: {
          x: { ticks: { color: '#9fb0c8' }, grid: { color: '#1f2a3a' } },
          y: { min: 0, max: 100, ticks: { color: '#9fb0c8', callback: v => v + '%' }, grid: { color: '#1f2a3a' } }
        }
      }
    });

    // PBP table
    const pbpTbody = document.querySelector('#livePbpTable tbody');
    if (pbpTbody) {
      pbpTbody.innerHTML = data.timeline.map(t => {
        const parts = t.state.split('/');
        const inning = parts[0] + parts[1];
        return `<tr>
          <td class="matchup">${inning}</td>
          <td>${parts.slice(2).join(' / ')}</td>
          <td><strong>${(t.p_home_win * 100).toFixed(1)}%</strong></td>
          <td>${fmtPrice(t.fair_home_price)}</td>
          <td>${fmtPrice(t.fair_away_price)}</td>
          <td style="white-space: normal;">${t.event}</td>
        </tr>`;
      }).join('');
    }

    // RE24 table
    const reBody = document.querySelector('#liveRe24Table tbody');
    if (reBody && data.re24_table) {
      // Pivot to rows by bases.
      const bases = {};
      for (const row of data.re24_table) {
        if (!bases[row.bases]) bases[row.bases] = {};
        bases[row.bases][row.outs] = row.re24;
      }
      const baseLabels = {
        '000': 'Empty', '100': '1B', '010': '2B', '001': '3B',
        '110': '1B,2B', '101': '1B,3B', '011': '2B,3B', '111': 'Loaded'
      };
      reBody.innerHTML = Object.keys(bases).map(b => `<tr>
        <td class="matchup">${baseLabels[b] || b}</td>
        <td>${(bases[b][0] || 0).toFixed(3)}</td>
        <td>${(bases[b][1] || 0).toFixed(3)}</td>
        <td>${(bases[b][2] || 0).toFixed(3)}</td>
      </tr>`).join('');
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (document.body.classList.contains('page-ml'))   renderMLLab();
    if (document.body.classList.contains('page-live')) renderLive();
  });
})();
