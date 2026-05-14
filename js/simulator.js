/* EdgeStat - client-side game simulator.
   A faithful JS port of python/simulator.py's logic, but tuned to run in
   the browser fast enough to feel interactive.  Uses a simplified Poisson +
   inning-by-inning state machine.
*/

window.EdgeStatSim = (function () {

  function poissonSample(lambda) {
    // Knuth's algorithm. Good enough for lambda < ~30.
    let L = Math.exp(-lambda), k = 0, p = 1;
    while (true) {
      k++;
      p *= Math.random();
      if (p <= L) return k - 1;
    }
  }

  function teamRunLambda(opts) {
    // opts: {wrc, oppXFIP, park, wind, hand}
    let lam = 4.45;
    lam *= (opts.wrc / 100);
    lam *= 0.55 * (opts.oppXFIP / 4.0) + 0.45;   // starter+bullpen blend
    lam *= opts.park;
    const windMult = 1 + Math.max(Math.min(opts.wind, 18), -18) * 0.006;
    lam *= windMult;
    return Math.max(1.5, Math.min(lam, 9.0));
  }

  function simulateOneGame(awayLambda, homeLambda) {
    // Per-inning lambda is total/9. Add ~3% home boost.
    const perInningAway = awayLambda / 9.0;
    const perInningHome = homeLambda / 9.0 * 1.018;
    let away = 0, home = 0;
    const inningRuns = [];
    for (let i = 0; i < 9; i++) {
      const a = poissonSample(perInningAway);
      const h = poissonSample(perInningHome);
      away += a;
      home += h;
      inningRuns.push(a + h);
    }
    // Extras: 50/50 each half-inning until decided.
    let inning = 10;
    while (away === home && inning <= 15) {
      away += poissonSample(0.5);
      home += poissonSample(0.5);
      inningRuns.push(0);
      inning++;
    }
    return { away, home, inningRuns };
  }

  function monteCarlo(opts) {
    const awayLambda = teamRunLambda({
      wrc: opts.awayWRC, oppXFIP: opts.homeXFIP, park: opts.park, wind: opts.wind
    });
    const homeLambda = teamRunLambda({
      wrc: opts.homeWRC, oppXFIP: opts.awayXFIP, park: opts.park, wind: opts.wind
    });
    let homeWins = 0, awayWins = 0;
    const totals = new Array(25).fill(0);
    let sumTotal = 0, sumHome = 0, sumAway = 0;
    let cover15 = 0;
    let over = 0;
    let push = 0;
    const winPathSamples = [];

    for (let i = 1; i <= opts.n; i++) {
      const { away, home } = simulateOneGame(awayLambda, homeLambda);
      const total = away + home;
      if (home > away) homeWins++; else awayWins++;
      if (home - away >= 2) cover15++;
      if (total > opts.marketTotal) over++;
      if (total === opts.marketTotal) push++;
      totals[Math.min(total, 24)]++;
      sumTotal += total;
      sumHome += home;
      sumAway += away;
      // Sample running win-prob every n/40 sims for convergence chart.
      if (i % Math.max(1, Math.floor(opts.n / 40)) === 0 || i === opts.n) {
        winPathSamples.push({ n: i, p: homeWins / i });
      }
    }
    const pOver = (over + 0.5 * push) / opts.n;
    return {
      awayLambda, homeLambda,
      pHomeWin: homeWins / opts.n,
      pAwayWin: awayWins / opts.n,
      pOver,
      pUnder: 1 - pOver,
      pHomeCover15: cover15 / opts.n,
      pAwayCover15: 1 - cover15 / opts.n,
      avgTotal: sumTotal / opts.n,
      avgHome: sumHome / opts.n,
      avgAway: sumAway / opts.n,
      runDist: totals,
      winPathSamples,
    };
  }

  function probToAmerican(p) {
    if (p <= 0.01 || p >= 0.99) return 0;
    const dec = 1 / p;
    return dec >= 2 ? Math.round((dec - 1) * 100) : -Math.round(100 / (dec - 1));
  }
  function americanToImplied(am) {
    if (am === 0) return 0.5;
    return am > 0 ? 100 / (am + 100) : Math.abs(am) / (Math.abs(am) + 100);
  }

  function recommend(sim, opts) {
    const out = [];
    // Moneyline
    const homeMarket = americanToImplied(opts.marketHomeML);
    const homeEdge = (sim.pHomeWin - homeMarket) * 100;
    const homeKelly = Math.max(0, kellyUnits(sim.pHomeWin, opts.marketHomeML));
    out.push({
      market: "Moneyline", side: "HOME",
      modelProb: sim.pHomeWin, fairPrice: probToAmerican(sim.pHomeWin),
      marketPrice: opts.marketHomeML,
      edge: homeEdge, kelly: homeKelly,
      play: homeEdge >= 3 ? "BET" : homeEdge >= 1.5 ? "LEAN" : "PASS",
    });
    // Total
    const totalMarket = -110;
    const overEdge = (sim.pOver - americanToImplied(totalMarket)) * 100;
    const underEdge = (sim.pUnder - americanToImplied(totalMarket)) * 100;
    out.push({
      market: "Total", side: `OVER ${opts.marketTotal}`,
      modelProb: sim.pOver, fairPrice: probToAmerican(sim.pOver),
      marketPrice: totalMarket, edge: overEdge,
      kelly: Math.max(0, kellyUnits(sim.pOver, totalMarket)),
      play: overEdge >= 3 ? "BET" : overEdge >= 1.5 ? "LEAN" : "PASS",
    });
    out.push({
      market: "Total", side: `UNDER ${opts.marketTotal}`,
      modelProb: sim.pUnder, fairPrice: probToAmerican(sim.pUnder),
      marketPrice: totalMarket, edge: underEdge,
      kelly: Math.max(0, kellyUnits(sim.pUnder, totalMarket)),
      play: underEdge >= 3 ? "BET" : underEdge >= 1.5 ? "LEAN" : "PASS",
    });
    // Run line.
    const rlMarket = 110;
    const rlEdge = (sim.pHomeCover15 - americanToImplied(rlMarket)) * 100;
    out.push({
      market: "Run Line", side: "HOME -1.5",
      modelProb: sim.pHomeCover15, fairPrice: probToAmerican(sim.pHomeCover15),
      marketPrice: rlMarket, edge: rlEdge,
      kelly: Math.max(0, kellyUnits(sim.pHomeCover15, rlMarket)),
      play: rlEdge >= 3 ? "BET" : rlEdge >= 1.5 ? "LEAN" : "PASS",
    });
    return out;
  }

  function kellyUnits(p, am) {
    const b = (am > 0 ? am / 100 : 100 / Math.abs(am));
    if (b <= 0) return 0;
    const f = (b * p - (1 - p)) / b;
    return Math.min(Math.max(0, f) * 0.25 * 100, 3.0);
  }

  return { monteCarlo, recommend, teamRunLambda };
})();

// --- Page wiring ---
document.addEventListener('DOMContentLoaded', () => {
  const runBtn = document.getElementById('runBtn');
  if (!runBtn) return;

  let distChartRef = null;
  let convChartRef = null;

  function getOpts() {
    return {
      awayWRC: parseFloat(document.getElementById('awayWRC').value),
      homeWRC: parseFloat(document.getElementById('homeWRC').value),
      awayXFIP: parseFloat(document.getElementById('awayXFIP').value),
      homeXFIP: parseFloat(document.getElementById('homeXFIP').value),
      park: parseFloat(document.getElementById('parkFactor').value),
      wind: parseFloat(document.getElementById('wind').value),
      marketTotal: parseFloat(document.getElementById('marketTotal').value),
      marketHomeML: parseInt(document.getElementById('marketHomeML').value),
      n: Math.min(50000, Math.max(100, parseInt(document.getElementById('nSims').value))),
    };
  }

  function render(sim, opts) {
    document.getElementById('resHomeWin').textContent = (sim.pHomeWin * 100).toFixed(1) + '%';
    document.getElementById('resAwayWin').textContent = (sim.pAwayWin * 100).toFixed(1) + '%';
    document.getElementById('resAvgTotal').textContent = sim.avgTotal.toFixed(2);
    document.getElementById('resAvgHome').textContent = sim.avgHome.toFixed(2);
    document.getElementById('resPOver').textContent = (sim.pOver * 100).toFixed(1) + '%';
    document.getElementById('resCover15').textContent = (sim.pHomeCover15 * 100).toFixed(1) + '%';

    // Distribution chart
    const labels = sim.runDist.map((_, i) => i).filter(i => sim.runDist[i] > 0 || (i >= 3 && i <= 18));
    const data = labels.map(i => sim.runDist[i]);
    const lineIdx = Math.round(opts.marketTotal);
    if (distChartRef) distChartRef.destroy();
    distChartRef = new Chart(document.getElementById('distChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'P(total runs = k)',
          data,
          backgroundColor: labels.map(i => i > opts.marketTotal ? 'rgba(74,222,128,0.7)' : 'rgba(96,165,250,0.5)'),
          borderRadius: 3
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

    // Convergence chart
    if (convChartRef) convChartRef.destroy();
    convChartRef = new Chart(document.getElementById('convergenceChart').getContext('2d'), {
      type: 'line',
      data: {
        labels: sim.winPathSamples.map(s => s.n),
        datasets: [{
          label: 'Running home win %',
          data: sim.winPathSamples.map(s => (s.p * 100).toFixed(2)),
          borderColor: '#4ade80',
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

    // Recommendations table
    const recs = EdgeStatSim.recommend(sim, opts);
    document.querySelector('#pricesTable tbody').innerHTML = recs.map(r => `<tr>
      <td>${r.market}</td>
      <td class="matchup">${r.side}</td>
      <td>${(r.modelProb * 100).toFixed(1)}%</td>
      <td>${r.fairPrice > 0 ? '+' + r.fairPrice : r.fairPrice}</td>
      <td>${r.marketPrice > 0 ? '+' + r.marketPrice : r.marketPrice}</td>
      <td class="${r.edge >= 0 ? 'edge-pos' : 'edge-neg'}">${r.edge >= 0 ? '+' : ''}${r.edge.toFixed(2)}%</td>
      <td>${r.kelly.toFixed(2)}u</td>
      <td class="rec ${r.play === 'BET' ? 'bet' : r.play === 'LEAN' ? 'lean' : 'pass'}">${r.play}</td>
    </tr>`).join('');
  }

  function run() {
    const opts = getOpts();
    const status = document.getElementById('simStatus');
    status.textContent = `Simulating ${opts.n.toLocaleString()} games…`;
    runBtn.disabled = true;
    runBtn.textContent = "Simulating…";
    // Defer to next frame for UI update.
    setTimeout(() => {
      const t0 = performance.now();
      const sim = EdgeStatSim.monteCarlo(opts);
      const ms = performance.now() - t0;
      status.textContent = `Done — ${opts.n.toLocaleString()} sims in ${ms.toFixed(0)}ms`;
      render(sim, opts);
      runBtn.disabled = false;
      runBtn.textContent = "▶ Run Simulation";
    }, 50);
  }

  runBtn.addEventListener('click', run);

  // Auto-run on first load.
  run();
});
