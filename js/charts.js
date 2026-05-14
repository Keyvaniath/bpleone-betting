/* Chart rendering. Uses Chart.js loaded via CDN. */

window.EdgeStatCharts = (function() {

  // Shared styling
  const COLOR = {
    text: '#9fb0c8',
    line: '#1f2a3a',
    green: '#4ade80',
    cyan: '#22d3ee',
    red: '#f87171',
    gold: '#fbbf24',
    blue: '#60a5fa',
    purple: '#a78bfa',
  };

  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: COLOR.text, font: { size: 11 } }, position: 'bottom' },
      tooltip: { backgroundColor: '#0c1118', titleColor: '#e7edf6', bodyColor: '#9fb0c8', borderColor: '#1f2a3a', borderWidth: 1 }
    },
    scales: {
      x: { ticks: { color: COLOR.text, font: { size: 10 } }, grid: { color: COLOR.line } },
      y: { ticks: { color: COLOR.text, font: { size: 10 } }, grid: { color: COLOR.line } }
    }
  };

  function renderHeroChart(ctx) {
    if (!ctx) return;
    // Bell-curve-ish distribution of confidence across slate
    const data = [10, 22, 38, 64, 91, 78, 52, 30, 18, 8];
    const labels = ['<40%','45%','50%','55%','60%','65%','70%','75%','80%','85%+'];
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Model win-probability buckets (slate)',
          data,
          backgroundColor: ctx => {
            const c = ctx.dataIndex;
            return c >= 4 ? 'rgba(74,222,128,0.7)' : 'rgba(96,165,250,0.5)';
          },
          borderColor: COLOR.green,
          borderWidth: 1.2,
          borderRadius: 4
        }]
      },
      options: { ...baseOptions, plugins: { ...baseOptions.plugins, legend: { display: false } } }
    });
  }

  function renderModelMarket(ctx) {
    if (!ctx) return;
    const hist = window.MODEL_HISTORY;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: hist.map(h => 'D' + h.day),
        datasets: [
          { label: 'Model Edge %', data: hist.map(h=>h.modelEdge), borderColor: COLOR.green, backgroundColor: 'rgba(74,222,128,0.1)', tension: 0.3, fill: true, pointRadius: 2 },
          { label: 'Market CLV %', data: hist.map(h=>h.clv), borderColor: COLOR.cyan, backgroundColor: 'rgba(34,211,238,0.05)', tension: 0.3, fill: true, pointRadius: 2 },
        ]
      },
      options: baseOptions
    });
  }

  function renderCLV(ctx) {
    if (!ctx) return;
    const hist = window.MODEL_HISTORY;
    let cum = 0;
    const cumData = hist.map(h => { cum += h.clv; return cum; });
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: hist.map(h => 'D' + h.day),
        datasets: [{
          label: 'Cumulative CLV %',
          data: cumData,
          borderColor: COLOR.gold,
          backgroundColor: 'rgba(251,191,36,0.12)',
          tension: 0.3, fill: true, pointRadius: 2
        }]
      },
      options: baseOptions
    });
  }

  function renderHitRate(ctx) {
    if (!ctx) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: window.HIT_RATES.map(h => h.type),
        datasets: [{
          label: 'Hit %',
          data: window.HIT_RATES.map(h => h.hit),
          backgroundColor: [
            'rgba(74,222,128,0.7)',
            'rgba(96,165,250,0.7)',
            'rgba(34,211,238,0.7)',
            'rgba(167,139,250,0.7)',
            'rgba(251,191,36,0.7)',
            'rgba(248,113,113,0.7)',
          ],
          borderRadius: 4
        }]
      },
      options: {
        ...baseOptions,
        indexAxis: 'y',
        scales: {
          ...baseOptions.scales,
          x: { ...baseOptions.scales.x, min: 50, max: 65 }
        },
        plugins: { ...baseOptions.plugins, legend: { display: false } }
      }
    });
  }

  function renderConfidenceGauge(ctx, confidencePct) {
    if (!ctx) return;
    new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Confidence','Remaining'],
        datasets: [{
          data: [confidencePct, 100 - confidencePct],
          backgroundColor: [COLOR.green, '#1a2230'],
          borderWidth: 0,
          cutout: '78%'
        }]
      },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, legend: { display: false } },
        scales: {},
      }
    });
  }

  function renderRunDistribution(ctx, awayL, homeL) {
    if (!ctx) return;
    const totalDist = new Array(21).fill(0);
    for (let a = 0; a <= 15; a++) {
      for (let h = 0; h <= 15; h++) {
        const idx = a+h;
        if (idx > 20) continue;
        totalDist[idx] += EdgeStat.poisson(a, awayL) * EdgeStat.poisson(h, homeL);
      }
    }
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: totalDist.map((_,i)=>i),
        datasets: [{
          label: 'P(total runs = k)',
          data: totalDist,
          backgroundColor: ctx => ctx.dataIndex >= 8 ? 'rgba(74,222,128,0.7)' : 'rgba(96,165,250,0.5)',
          borderRadius: 3
        }]
      },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, legend: { display: false } }
      }
    });
  }

  function renderPropEdges(ctx) {
    if (!ctx) return;
    const props = window.PROP_PICKS.slice(0, 8);
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: props.map(p => p.player.split(' ').slice(-1)[0]),
        datasets: [{
          label: 'Edge %',
          data: props.map(p => p.edge),
          backgroundColor: 'rgba(74,222,128,0.7)',
          borderRadius: 4
        }]
      },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, legend: { display: false } }
      }
    });
  }

  function renderTrendStreak(ctx) {
    if (!ctx) return;
    const t = window.TEAM_TRENDS.slice(0, 8);
    const wins = t.map(x => parseInt(x.last10.split('-')[0]));
    new Chart(ctx, {
      type: 'radar',
      data: {
        labels: t.map(x => x.team),
        datasets: [{
          label: 'Last 10 wins',
          data: wins,
          backgroundColor: 'rgba(74,222,128,0.15)',
          borderColor: COLOR.green,
          pointBackgroundColor: COLOR.green
        }]
      },
      options: {
        ...baseOptions,
        scales: {
          r: {
            min: 0, max: 10,
            angleLines: { color: COLOR.line },
            grid: { color: COLOR.line },
            pointLabels: { color: COLOR.text, font: { size: 11 } },
            ticks: { color: COLOR.text, backdropColor: 'transparent' }
          }
        }
      }
    });
  }

  function renderBankroll(ctx) {
    if (!ctx) return;
    // Simulate a Kelly-staked bankroll vs flat-staked
    let bankK = 100, bankF = 100;
    const labels = [], dKelly = [], dFlat = [];
    const r = (s => () => { s = (s*9301+49297) % 233280; return s/233280; })(99);
    for (let i = 1; i <= 60; i++) {
      const winProb = 0.55 + (r()-0.5)*0.1;
      const won = r() < winProb;
      const price = -110;
      const dec = 1 + (100/110);
      const kellyStake = Math.max(0, ((dec-1)*winProb - (1-winProb)) / (dec-1)) * 0.25;
      const fStake = 0.02;
      bankK *= 1 + (won ? kellyStake*(dec-1) : -kellyStake);
      bankF *= 1 + (won ? fStake*(dec-1) : -fStake);
      labels.push('G' + i);
      dKelly.push(bankK.toFixed(2));
      dFlat.push(bankF.toFixed(2));
    }
    new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: '¼-Kelly', data: dKelly, borderColor: COLOR.green, backgroundColor: 'rgba(74,222,128,0.1)', fill: true, pointRadius: 0, tension: 0.2 },
          { label: '2% Flat', data: dFlat, borderColor: COLOR.cyan, backgroundColor: 'rgba(34,211,238,0.05)', fill: true, pointRadius: 0, tension: 0.2 }
        ]
      },
      options: baseOptions
    });
  }

  return {
    renderHeroChart,
    renderModelMarket,
    renderCLV,
    renderHitRate,
    renderConfidenceGauge,
    renderRunDistribution,
    renderPropEdges,
    renderTrendStreak,
    renderBankroll
  };
})();
